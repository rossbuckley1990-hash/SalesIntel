"""Cross-entity 360 intelligence service.

Joins buyers, opportunities, market signals and competitors into one
server-authored intelligence pack. The synthesis is deterministic and rule-based
so it is fully unit-testable and never requires an OpenAI key. An optional
AI overlay on ``commercial_synthesis`` is a clean future extension point.

The aggregation pattern mirrors ``services/dashboard.py``: separate per-entity
queries resolved against the focal entity in Python, then summarised.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.entity_resolution import (
    ResolvedEntity,
    resolve_buyers_for_competitor,
    resolve_competitors_for_sector,
    resolve_opportunities_for_buyer,
    resolve_signals_for_buyer,
)
from app.models import BuyerProfile, CompetitorProfile, MarketSignal, Opportunity
from app.schemas.entity_360 import (
    Buyer360,
    Competitor360,
    ContestedBuyer,
    EvidenceItem,
    IncumbentCompetitor,
    MarginSummary,
    RenewalWindow,
    RiskDistribution,
)
from app.services.opportunity_intelligence import calculate_for_opportunity, enrich_opportunity

MARGIN_THRESHOLD_PERCENTAGE = 25.0
RENEWAL_WINDOW_DAYS = 90
THREAT_PRESSURE = {
    "high": "High pressure",
    "medium": "Moderate pressure",
    "low": "Low pressure",
    "unknown": "Pressure unclear",
}


def build_buyer_360(
    db: Session,
    buyer_id: int,
    *,
    today: date | None = None,
) -> Buyer360:
    buyer = db.get(BuyerProfile, buyer_id)
    if buyer is None:
        raise _not_found("Buyer profile")

    active_today = today or date.today()
    opportunities = list(db.scalars(select(Opportunity).order_by(Opportunity.id)))
    signals = list(db.scalars(select(MarketSignal).order_by(MarketSignal.id)))
    competitors = list(db.scalars(select(CompetitorProfile).order_by(CompetitorProfile.id)))

    resolved_opportunities = resolve_opportunities_for_buyer(buyer.buyer_name, opportunities)
    resolved_signals = resolve_signals_for_buyer(buyer.buyer_name, signals)
    resolved_competitors = resolve_competitors_for_sector(buyer.sector, competitors)

    evidence: list[EvidenceItem] = []
    evidence.extend(_opportunity_evidence(resolved_opportunities))
    evidence.extend(_signal_evidence(resolved_signals))
    evidence.extend(_competitor_evidence(resolved_competitors))

    intelligence_by_id = {
        opp.id: calculate_for_opportunity(opp, today=active_today)
        for opp, _confidence, _method in resolved_opportunities
    }
    linked_reads = [
        enrich_opportunity(opp, today=active_today) for opp, _c, _m in resolved_opportunities
    ]
    risk_distribution = _risk_distribution_from(linked_reads)
    margin_summary = _margin_summary_from(resolved_opportunities)

    pipeline_exposure = round(
        sum(opp.estimated_total_contract_value for opp, _c, _m in resolved_opportunities), 2
    )
    weighted_exposure = round(
        sum(intelligence_by_id[opp.id].weighted_pipeline_value for opp, _c, _m in resolved_opportunities),
        2,
    )

    renewal_windows = _renewal_windows(resolved_opportunities, resolved_signals, active_today)
    active_signals = _active_signals(resolved_signals, active_today)
    active_tender_value = round(sum(signal.estimated_value or 0 for signal in active_signals), 2)

    incumbent_competitors = [
        _incumbent_competitor(resolved) for resolved in resolved_competitors
    ]

    risk_level = _buyer_risk_level(
        risk_distribution=risk_distribution,
        margin_summary=margin_summary,
        incumbent_competitors=incumbent_competitors,
    )
    confidence = _buyer_confidence(resolved_opportunities, resolved_signals, resolved_competitors)

    synthesis = _buyer_synthesis(
        buyer=buyer,
        opportunity_count=len(resolved_opportunities),
        pipeline_exposure=pipeline_exposure,
        weighted_exposure=weighted_exposure,
        margin_summary=margin_summary,
        risk_distribution=risk_distribution,
        active_tender_value=active_tender_value,
        incumbent_competitors=incumbent_competitors,
        renewal_windows=renewal_windows,
    )
    recommended_next_action = _buyer_next_action(
        buyer=buyer,
        margin_summary=margin_summary,
        incumbent_competitors=incumbent_competitors,
        renewal_windows=renewal_windows,
        opportunity_count=len(resolved_opportunities),
    )

    return Buyer360(
        buyer=_buyer_read(buyer),
        opportunity_count=len(resolved_opportunities),
        active_tender_count=len(active_signals),
        pipeline_exposure=pipeline_exposure,
        weighted_exposure=weighted_exposure,
        active_tender_value=active_tender_value,
        margin_summary=margin_summary,
        risk_distribution=risk_distribution,
        incumbent_competitors=incumbent_competitors,
        renewal_windows=renewal_windows,
        linked_opportunities=linked_reads,
        commercial_synthesis=synthesis,
        recommended_next_action=recommended_next_action,
        risk_level=risk_level,
        confidence=confidence,
        evidence=evidence,
    )


def build_competitor_360(
    db: Session,
    competitor_id: int,
    *,
    today: date | None = None,
) -> Competitor360:
    competitor = db.get(CompetitorProfile, competitor_id)
    if competitor is None:
        raise _not_found("Competitor profile")

    active_today = today or date.today()
    opportunities = list(db.scalars(select(Opportunity).order_by(Opportunity.id)))
    buyers = list(db.scalars(select(BuyerProfile).order_by(BuyerProfile.id)))

    contested_opportunities = [
        opp
        for opp in opportunities
        if _opp_sector_in(opp, competitor.sectors)
    ]
    resolved_buyers = resolve_buyers_for_competitor(competitor, buyers)

    evidence: list[EvidenceItem] = []
    evidence.extend(_contested_opportunity_evidence(contested_opportunities, competitor))
    evidence.extend(_affected_buyer_evidence(resolved_buyers, competitor))

    contested_reads = [
        enrich_opportunity(opp, today=active_today) for opp in contested_opportunities
    ]
    contested_value = round(
        sum(opp.estimated_total_contract_value for opp in contested_opportunities), 2
    )

    affected_buyers = _affected_buyers(resolved_buyers, contested_opportunities)

    confidence = _competitor_confidence(len(contested_opportunities), len(resolved_buyers))

    synthesis = _competitor_synthesis(
        competitor=competitor,
        contested_opportunity_count=len(contested_opportunities),
        contested_value=contested_value,
        affected_buyer_count=len(affected_buyers),
    )
    recommended_next_action = _competitor_next_action(
        competitor=competitor,
        contested_value=contested_value,
        contested_opportunity_count=len(contested_opportunities),
    )

    return Competitor360(
        competitor=_competitor_read(competitor),
        contested_opportunity_count=len(contested_opportunities),
        contested_value=contested_value,
        affected_buyer_count=len(affected_buyers),
        sectors_present=list(competitor.sectors),
        contested_opportunities=contested_reads,
        affected_buyers=affected_buyers,
        commercial_synthesis=synthesis,
        recommended_next_action=recommended_next_action,
        threat_level=competitor.threat_level or "unknown",
        confidence=confidence,
        evidence=evidence,
    )


# --------------------------------------------------------------------------- #
# Aggregation helpers
# --------------------------------------------------------------------------- #


def _risk_distribution_from(linked_reads: list) -> RiskDistribution:
    distribution = RiskDistribution()
    for opp_read in linked_reads:
        rating = (opp_read.calculated_risk_rating or "").lower()
        if rating == "red":
            distribution.red += 1
        elif rating == "amber":
            distribution.amber += 1
        elif rating == "green":
            distribution.green += 1
    return distribution


def _margin_summary_from(
    resolved_opportunities: list[tuple[Opportunity, float, str]],
) -> MarginSummary:
    margins = [
        opp.margin_percentage
        for opp, _confidence, _method in resolved_opportunities
        if opp.margin_percentage
    ]
    if not margins:
        return MarginSummary(threshold_percentage=MARGIN_THRESHOLD_PERCENTAGE)
    below = sum(1 for margin in margins if margin < MARGIN_THRESHOLD_PERCENTAGE)
    return MarginSummary(
        average_margin_percentage=round(sum(margins) / len(margins), 2),
        lowest_margin_percentage=round(min(margins), 2),
        highest_margin_percentage=round(max(margins), 2),
        below_threshold_count=below,
        threshold_percentage=MARGIN_THRESHOLD_PERCENTAGE,
    )


def _active_signals(
    resolved_signals: list[tuple[MarketSignal, float, str]],
    today: date,
) -> list[MarketSignal]:
    return [
        signal
        for signal, _confidence, _method in resolved_signals
        if signal.expected_tender_date and signal.expected_tender_date >= today
    ]


def _renewal_windows(
    resolved_opportunities: list[tuple[Opportunity, float, str]],
    resolved_signals: list[tuple[MarketSignal, float, str]],
    today: date,
) -> list[RenewalWindow]:
    horizon = today + timedelta(days=RENEWAL_WINDOW_DAYS)
    windows: list[RenewalWindow] = []

    for opp, _confidence, _method in resolved_opportunities:
        month = opp.forecast_start_month
        if not month:
            continue
        window_date = _month_to_date(month, today.year)
        if window_date and today <= window_date <= horizon:
            windows.append(
                RenewalWindow(
                    label=opp.name,
                    month=month,
                    value=opp.estimated_total_contract_value,
                    source_entity_type="opportunity",
                    source_entity_id=opp.id,
                )
            )

    for signal, _confidence, _method in resolved_signals:
        tender_date = signal.expected_tender_date
        if not tender_date or not (today <= tender_date <= horizon):
            continue
        windows.append(
            RenewalWindow(
                label=signal.title,
                date_value=tender_date.isoformat(),
                value=signal.estimated_value,
                source_entity_type="market_signal",
                source_entity_id=signal.id,
            )
        )

    windows.sort(key=lambda window: window.month or window.date_value or "")
    return windows


def _incumbent_competitor(resolved: ResolvedEntity) -> IncumbentCompetitor:
    competitor = resolved.entity
    threat = (competitor.threat_level or "unknown").lower()
    return IncumbentCompetitor(
        competitor=_competitor_read(competitor),
        threat_level=competitor.threat_level or "unknown",
        pressure_label=THREAT_PRESSURE.get(threat, THREAT_PRESSURE["unknown"]),
        match_method=resolved.match_method,
    )


def _affected_buyers(
    resolved_buyers: list[ResolvedEntity],
    contested_opportunities: list[Opportunity],
) -> list[ContestedBuyer]:
    opportunity_counts: dict[int, int] = {}
    value_by_buyer: dict[int, float] = {}
    for opp in contested_opportunities:
        for resolved in resolved_buyers:
            buyer = resolved.entity
            if buyer.sector.strip().lower() == opp.sector.strip().lower():
                opportunity_counts[buyer.id] = opportunity_counts.get(buyer.id, 0) + 1
                value_by_buyer[buyer.id] = (
                    value_by_buyer.get(buyer.id, 0) + opp.estimated_total_contract_value
                )

    affected: list[ContestedBuyer] = []
    for resolved in resolved_buyers:
        buyer = resolved.entity
        affected.append(
            ContestedBuyer(
                buyer=_buyer_read(buyer),
                opportunity_count=opportunity_counts.get(buyer.id, 0),
                contested_value=round(value_by_buyer.get(buyer.id, 0), 2),
                match_method=resolved.match_method,
            )
        )
    affected.sort(key=lambda item: item.contested_value, reverse=True)
    return affected


def _opp_sector_in(opportunity: Opportunity, sectors: list[str]) -> bool:
    target = {sector.strip().lower() for sector in sectors if sector and sector.strip()}
    return bool(target) and opportunity.sector.strip().lower() in target


def _month_to_date(month: str | None, fallback_year: int) -> date | None:
    if not month or len(month) < 7 or month[4] != "-":
        return None
    try:
        year_part = int(month[:4])
        month_part = int(month[5:7])
    except ValueError:
        return None
    return date(year_part, month_part, 1)


# --------------------------------------------------------------------------- #
# Synthesis (rule-based narratives)
# --------------------------------------------------------------------------- #


def _buyer_synthesis(
    *,
    buyer: BuyerProfile,
    opportunity_count: int,
    pipeline_exposure: float,
    weighted_exposure: float,
    margin_summary: MarginSummary,
    risk_distribution: RiskDistribution,
    active_tender_value: float,
    incumbent_competitors: list[IncumbentCompetitor],
    renewal_windows: list[RenewalWindow],
) -> str:
    if opportunity_count == 0 and active_tender_value == 0:
        return (
            f"No live opportunities or active tenders are currently linked to "
            f"{buyer.buyer_name}. Treat this as a target account to develop rather "
            f"than an active pursuit, and confirm whether pipeline data is missing."
        )

    parts: list[str] = []
    if opportunity_count > 0:
        parts.append(
            f"{buyer.buyer_name} carries GBP {_millions(pipeline_exposure)} open pipeline "
            f"exposure across {opportunity_count} pursuit"
            f"{'s' if opportunity_count != 1 else ''} "
            f"(GBP {_millions(weighted_exposure)} weighted)"
        )
        if margin_summary.below_threshold_count > 0:
            parts.append(
                f"{margin_summary.below_threshold_count} of {opportunity_count} pursuits "
                f"sit below the {MARGIN_THRESHOLD_PERCENTAGE:.0f}% margin floor "
                f"(lowest {margin_summary.lowest_margin_percentage:.0f}%)"
            )
        if risk_distribution.red > 0:
            parts.append(f"{risk_distribution.red} rated Red risk")
    else:
        parts.append(
            f"{buyer.buyer_name} has no live opportunities yet, but has "
            f"GBP {_millions(active_tender_value)} in active tender signals"
        )

    high_pressure = [
        competitor for competitor in incumbent_competitors
        if (competitor.threat_level or "").lower() == "high"
    ]
    if high_pressure:
        names = ", ".join(c.competitor.name for c in high_pressure[:2])
        parts.append(f"{names} {'is' if len(high_pressure) == 1 else 'are'} incumbent in this sector with High threat")

    if renewal_windows:
        next_window = renewal_windows[0]
        when = next_window.month or next_window.date_value or "soon"
        parts.append(f"next renewal window opens {when}")

    return ". ".join(parts) + "."


def _buyer_next_action(
    *,
    buyer: BuyerProfile,
    margin_summary: MarginSummary,
    incumbent_competitors: list[IncumbentCompetitor],
    renewal_windows: list[RenewalWindow],
    opportunity_count: int,
) -> str:
    if buyer.next_best_action:
        return buyer.next_best_action
    if opportunity_count == 0:
        return (
            f"Develop {buyer.buyer_name} as a target account: confirm the buyer owner and "
            "schedule a discovery meeting before the next tender window."
        )
    if margin_summary.below_threshold_count > 0:
        return (
            f"Reprice or descope the {margin_summary.below_threshold_count} below-margin "
            f"pursuit(s) before committing bid resources."
        )
    if any((c.threat_level or "").lower() == "high" for c in incumbent_competitors):
        return (
            "Build an incumbent displacement plan before the renewal window opens."
        )
    if renewal_windows:
        return "Confirm capture plan ownership before the next renewal window opens."
    return (
        f"Maintain the {buyer.relationship_status or 'current'} relationship and "
        "confirm the next commercial action with the opportunity owner."
    )


def _buyer_risk_level(
    *,
    risk_distribution: RiskDistribution,
    margin_summary: MarginSummary,
    incumbent_competitors: list[IncumbentCompetitor],
) -> str:
    if risk_distribution.red > 0 or margin_summary.below_threshold_count > 1:
        return "Red"
    high_pressure = any(
        (c.threat_level or "").lower() == "high" for c in incumbent_competitors
    )
    if (
        risk_distribution.amber > 0
        or margin_summary.below_threshold_count > 0
        or high_pressure
    ):
        return "Amber"
    return "Green"


def _buyer_confidence(
    resolved_opportunities: list[tuple[Opportunity, float, str]],
    resolved_signals: list[tuple[MarketSignal, float, str]],
    resolved_competitors: list[ResolvedEntity],
) -> float:
    """Weighted confidence: exact links raise it, fuzzy/sector links lower it."""
    weights: list[float] = []
    for _entity, confidence, method in [*resolved_opportunities, *resolved_signals]:
        weights.append(1.0 if method == "exact" else confidence)
    # Sector-based competitor links are inferred, so they cap the confidence.
    for _entity in resolved_competitors:
        weights.append(0.6)
    if not weights:
        return 0.0
    return round(sum(weights) / len(weights), 2)


def _competitor_synthesis(
    *,
    competitor: CompetitorProfile,
    contested_opportunity_count: int,
    contested_value: float,
    affected_buyer_count: int,
) -> str:
    threat = (competitor.threat_level or "unknown").lower()
    threat_label = THREAT_PRESSURE.get(threat, THREAT_PRESSURE["unknown"])
    if contested_opportunity_count == 0:
        return (
            f"{competitor.name} is not currently contesting any live Mitie opportunities, "
            f"but operates in {', '.join(competitor.sectors) or 'these sectors'} and remains "
            f"a {threat_label.lower()} competitor to monitor."
        )
    buyer_word = "buyer" if affected_buyer_count == 1 else "buyers"
    return (
        f"{competitor.name} is contesting {contested_opportunity_count} live "
        f"opportunity{'s' if contested_opportunity_count == 1 else ''} worth "
        f"GBP {_millions(contested_value)} across {affected_buyer_count} {buyer_word}. "
        f"Assessed threat: {threat_label}. {_counter_summary(competitor)}"
    )


def _competitor_next_action(
    *,
    competitor: CompetitorProfile,
    contested_value: float,
    contested_opportunity_count: int,
) -> str:
    if competitor.counter_strategy:
        return competitor.counter_strategy
    if contested_opportunity_count == 0:
        return f"Maintain a watching brief on {competitor.name} in its active sectors."
    return (
        f"Pre-empt {competitor.name} on the GBP {_millions(contested_value)} of "
        "contested pipeline before renewal decisions are locked."
    )


def _competitor_confidence(
    contested_opportunity_count: int,
    affected_buyer_count: int,
) -> float:
    # Sector-based linkage is inherently inferred, so confidence is capped.
    if contested_opportunity_count == 0 and affected_buyer_count == 0:
        return 0.3
    return round(min(0.4 + 0.1 * (contested_opportunity_count + affected_buyer_count), 0.7), 2)


def _counter_summary(competitor: CompetitorProfile) -> str:
    if competitor.counter_strategy:
        return f"Counter: {competitor.counter_strategy}"
    if competitor.weaknesses:
        return f"Exploit: {competitor.weaknesses[0]}."
    return "Build a sector-specific counter-strategy."


def _millions(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"
    if value >= 1_000:
        return f"{value / 1_000:.0f}k"
    return f"{value:.0f}"


# --------------------------------------------------------------------------- #
# Evidence + read-shape helpers
# --------------------------------------------------------------------------- #


def _opportunity_evidence(
    resolved: list[tuple[Opportunity, float, str]],
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for opp, confidence, method in resolved:
        evidence.append(
            EvidenceItem(
                source_entity_type="opportunity",
                source_entity_id=opp.id,
                source_entity_label=opp.name,
                claim=(
                    f"{opp.buyer_name} pursuit worth GBP {opp.estimated_total_contract_value:,.0f} "
                    f"in {opp.stage} stage."
                ),
                match_method=method,
                confidence=confidence,
            )
        )
    return evidence


def _signal_evidence(
    resolved: list[tuple[MarketSignal, float, str]],
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for signal, confidence, method in resolved:
        value_text = (
            f" worth GBP {signal.estimated_value:,.0f}" if signal.estimated_value else ""
        )
        evidence.append(
            EvidenceItem(
                source_entity_type="market_signal",
                source_entity_id=signal.id,
                source_entity_label=signal.title,
                claim=(
                    f"Tender signal{value_text} attributed to {signal.buyer_name} "
                    f"via {signal.source_type}."
                ),
                match_method=method,
                confidence=confidence,
            )
        )
    return evidence


def _competitor_evidence(resolved: list[ResolvedEntity]) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for item in resolved:
        competitor = item.entity
        evidence.append(
            EvidenceItem(
                source_entity_type="competitor",
                source_entity_id=competitor.id,
                source_entity_label=competitor.name,
                claim=(
                    f"{competitor.name} operates in this buyer's sector and is assessed "
                    f"{competitor.threat_level or 'unknown'} threat."
                ),
                match_method=item.match_method,
                confidence=item.confidence,
            )
        )
    return evidence


def _contested_opportunity_evidence(
    opportunities: list[Opportunity],
    competitor: CompetitorProfile,
) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            source_entity_type="opportunity",
            source_entity_id=opp.id,
            source_entity_label=opp.name,
            claim=(
                f"{opp.buyer_name} ({opp.sector}) pursuit worth GBP "
                f"{opp.estimated_total_contract_value:,.0f} is in {competitor.name}'s sector."
            ),
            match_method="sector",
            confidence=0.6,
        )
        for opp in opportunities
    ]


def _affected_buyer_evidence(
    resolved_buyers: list[ResolvedEntity],
    competitor: CompetitorProfile,
) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            source_entity_type="buyer",
            source_entity_id=resolved.entity.id,
            source_entity_label=resolved.entity.buyer_name,
            claim=(
                f"{resolved.entity.buyer_name} operates in a sector {competitor.name} contests."
            ),
            match_method=resolved.match_method,
            confidence=resolved.confidence,
        )
        for resolved in resolved_buyers
    ]


def _buyer_read(buyer: BuyerProfile):
    from app.schemas.buyer_profile import BuyerProfileRead

    return BuyerProfileRead.model_validate(buyer)


def _competitor_read(competitor: CompetitorProfile):
    from app.schemas.competitor_profile import CompetitorProfileRead

    return CompetitorProfileRead.model_validate(competitor)


def _not_found(label: str) -> Exception:
    from fastapi import HTTPException

    return HTTPException(status_code=404, detail=f"{label} not found")
