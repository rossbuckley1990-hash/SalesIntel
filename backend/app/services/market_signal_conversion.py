from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    EnrichmentRun,
    ExecutiveAction,
    FieldIntelligence,
    FinanceForecast,
    MarketSignal,
    Opportunity,
    OpportunityEnrichment,
)
from app.schemas import (
    EnrichmentRunRead,
    ExecutiveActionRead,
    FieldIntelligenceRead,
    FinanceForecastRead,
    MarketSignalConversionResponse,
    MarketSignalRead,
    OpportunityEnrichmentRead,
)
from app.services.opportunity_intelligence import enrich_opportunity


KEY_OPPORTUNITY_FIELDS = [
    "name",
    "buyer_name",
    "sector",
    "region",
    "source_type",
    "stage",
    "estimated_annual_revenue",
    "estimated_total_contract_value",
    "estimated_gross_margin",
    "margin_percentage",
    "probability",
    "weighted_value",
    "submission_deadline",
    "forecast_start_month",
    "self_delivery_fit",
    "risk_rating",
    "strategic_fit_score",
    "bid_no_bid_recommendation",
    "recommended_action",
]


DISCIPLINE_KEYWORDS = {
    "fire alarm": "Fire Alarms",
    "pava": "PAVA",
    "emergency lighting": "Emergency Lighting",
    "extinguisher": "Extinguishers",
    "intruder": "Intruder Alarms",
    "cctv": "CCTV",
    "access control": "Access Control",
    "disabled refuge": "Disabled Refuge",
    "fire door": "Fire Doors",
    "dry riser": "Dry Risers",
    "sprinkler": "Sprinklers",
    "fire damper": "Fire Dampers",
    "smoke control": "Smoke Control",
    "gas suppression": "Gas Suppression",
    "risk assessment": "Fire Risk Assessments",
    "passive fire": "Passive Fire",
    "suppression": "Gas Suppression",
    "security": "CCTV",
}


def enrich_market_signal(signal: MarketSignal) -> MarketSignal:
    disciplines = _disciplines_for_signal(signal)
    signal.potential_disciplines = disciplines
    signal.likely_mitie_fit = _mitie_fit(signal, disciplines)
    signal.ai_rationale = _market_signal_rationale(signal, disciplines)
    return signal


def convert_market_signal_to_opportunity(
    signal: MarketSignal,
    *,
    db: Session,
) -> MarketSignalConversionResponse:
    enrich_market_signal(signal)
    opportunity, created_opportunity = _create_or_update_opportunity(signal, db=db)
    db.flush()

    run = EnrichmentRun(
        run_type="market_signal_conversion",
        status="completed",
        user_query=_signal_query(signal),
        opportunity_id=opportunity.id,
        finished_at=datetime.now(UTC),
        model_used="rule-based-market-signal-enrichment",
        search_performed=False,
        sources_checked=[_source_payload(signal)],
    )
    db.add(run)
    db.flush()

    field_records = _create_field_intelligence(signal, opportunity)
    db.add_all(field_records)
    enrichment = _create_opportunity_enrichment(signal, opportunity, run.id)
    db.add(enrichment)
    finance_forecast = _create_finance_forecast(signal, opportunity)
    if finance_forecast is not None:
        db.add(finance_forecast)
    executive_action = _create_executive_action_if_priority(signal, opportunity)
    if executive_action is not None:
        db.add(executive_action)

    run.records_created = (
        len(field_records)
        + 1
        + (1 if finance_forecast is not None else 0)
        + (1 if executive_action is not None else 0)
    )
    run.records_updated = 0 if created_opportunity else 1
    db.commit()

    db.refresh(signal)
    db.refresh(opportunity)
    db.refresh(run)
    db.refresh(enrichment)
    for record in field_records:
        db.refresh(record)
    if finance_forecast is not None:
        db.refresh(finance_forecast)
    if executive_action is not None:
        db.refresh(executive_action)

    unknown_count = sum(1 for field in field_records if field.value_type == "unknown")
    return MarketSignalConversionResponse(
        market_signal=MarketSignalRead.model_validate(signal),
        opportunity=enrich_opportunity(opportunity),
        enrichment_run=EnrichmentRunRead.model_validate(run),
        field_intelligence=[
            FieldIntelligenceRead.model_validate(field) for field in field_records
        ],
        opportunity_enrichment=OpportunityEnrichmentRead.model_validate(enrichment),
        executive_action=(
            ExecutiveActionRead.model_validate(executive_action)
            if executive_action is not None
            else None
        ),
        finance_forecast=(
            FinanceForecastRead.model_validate(finance_forecast)
            if finance_forecast is not None
            else None
        ),
        created_opportunity=created_opportunity,
        fields_filled=sum(1 for field in field_records if field.value_type != "unknown"),
        fields_still_unknown=unknown_count,
        conversion_summary=(
            f"Converted market signal into a source-backed opportunity with "
            f"{signal.likely_mitie_fit.lower()} Mitie fit, "
            f"{len(signal.potential_disciplines)} likely disciplines and "
            f"{unknown_count} fields requiring confirmation."
        ),
    )


def _create_or_update_opportunity(
    signal: MarketSignal,
    *,
    db: Session,
) -> tuple[Opportunity, bool]:
    opportunity = db.scalar(
        select(Opportunity)
        .where(Opportunity.name == signal.title)
        .where(Opportunity.buyer_name == signal.buyer_name)
    )
    created = opportunity is None
    if opportunity is None:
        opportunity = Opportunity(name=signal.title, buyer_name=signal.buyer_name)
        db.add(opportunity)

    value = float(signal.estimated_value or 0)
    margin_percentage = _margin_assumption(signal)
    probability = _probability_assumption(signal)
    annual_revenue = _annual_revenue(value)
    gross_margin = round(value * margin_percentage / 100, 2) if value else 0
    weighted_value = round(value * probability, 2) if value else 0

    opportunity.sector = signal.sector or "Unknown sector - confirmation required"
    opportunity.region = signal.region or "Unknown region - confirmation required"
    opportunity.source_type = signal.source_type or "Market signal"
    opportunity.stage = _stage_from_signal(signal)
    opportunity.owner = "Commercial Intelligence"
    opportunity.estimated_annual_revenue = annual_revenue
    opportunity.estimated_total_contract_value = value
    opportunity.estimated_gross_margin = gross_margin
    opportunity.margin_percentage = margin_percentage if value else 0
    opportunity.probability = probability
    opportunity.weighted_value = weighted_value
    opportunity.submission_deadline = None
    opportunity.forecast_start_month = _forecast_start_month(signal.expected_tender_date)
    opportunity.self_delivery_fit = signal.likely_mitie_fit
    opportunity.risk_rating = _risk_rating(signal)
    opportunity.strategic_fit_score = _strategic_fit_score(signal)
    opportunity.bid_no_bid_recommendation = _bid_recommendation(signal)
    opportunity.recommended_action = (
        signal.suggested_action
        or "Qualify source evidence, buyer route to market and likely scope."
    )
    return opportunity, created


def _create_field_intelligence(
    signal: MarketSignal,
    opportunity: Opportunity,
) -> list[FieldIntelligence]:
    source_urls = [signal.source_url] if signal.source_url else []
    source_titles = [signal.title] if signal.source_url else []
    records: list[FieldIntelligence] = []
    for field_name in KEY_OPPORTUNITY_FIELDS:
        value = getattr(opportunity, field_name, None)
        if isinstance(value, date):
            value = value.isoformat()
        value_type = _field_value_type(signal, field_name, value)
        records.append(
            FieldIntelligence(
                entity_type="opportunity",
                entity_id=opportunity.id,
                field_name=field_name,
                field_value=value,
                value_type=value_type,
                confidence_score=_field_confidence(signal, field_name, value_type),
                rationale=_field_rationale(signal, field_name, value_type),
                source_urls=source_urls,
                source_titles=source_titles,
                recommended_next_step=_field_next_step(field_name, value_type),
                needs_user_confirmation=value_type != "known",
            )
        )
    return records


def _create_opportunity_enrichment(
    signal: MarketSignal,
    opportunity: Opportunity,
    run_id: int,
) -> OpportunityEnrichment:
    disciplines = signal.potential_disciplines or _disciplines_for_signal(signal)
    unknowns = [
        "Submission deadline",
        "Incumbent supplier",
        "Asset volumes and contract term",
    ]
    next_steps = [
        signal.suggested_action
        or "Confirm buyer procurement route and expected tender timetable.",
        "Validate asset schedule, contract term and incumbent supplier.",
        "Decide whether the signal warrants sales owner assignment this week.",
    ]
    return OpportunityEnrichment(
        opportunity_id=opportunity.id,
        enrichment_run_id=run_id,
        buyer_summary=(
            f"{signal.buyer_name} is a {signal.sector} buyer in {signal.region}. "
            "MiSi has a market signal, not a confirmed tender pack."
        ),
        opportunity_summary=(
            f"{signal.title} is a source-attributed market signal with "
            f"{round(signal.confidence_score * 100)}% confidence."
        ),
        likely_scope="; ".join(disciplines),
        estimated_contract_value_rationale=(
            "Estimated value is taken from the market signal where present; "
            "annual revenue assumes a four-year commercial planning shape."
        ),
        likely_buyer_drivers=_buyer_drivers(signal),
        compliance_drivers=_compliance_drivers(signal),
        competitor_assessment=(
            "Incumbent supplier is unknown from the current signal. Treat competitor "
            "position as an early qualification item."
        ),
        commercial_assessment=(
            f"Potential {signal.likely_mitie_fit.lower()}-fit opportunity. "
            "Use as pipeline only after source validation and buyer route confirmation."
        ),
        mobilisation_assessment=(
            "Mobilisation risk depends on asset data, access windows and regional "
            "engineering capacity."
        ),
        self_delivery_assessment=(
            f"Likely disciplines: {', '.join(disciplines)}. Route through Mitie Fire "
            "& Security before third-party pricing becomes embedded."
        ),
        finance_assessment=(
            f"Forecast category: {_forecast_category(signal)}. Value remains estimated "
            "until contract term, award date and scope are confirmed."
        ),
        executive_recommendation=opportunity.recommended_action,
        unknowns=unknowns,
        recommended_next_steps=next_steps,
        overall_confidence=round(min(max(signal.confidence_score, 0), 1), 2),
    )


def _create_finance_forecast(
    signal: MarketSignal,
    opportunity: Opportunity,
) -> FinanceForecast | None:
    if not opportunity.forecast_start_month:
        return None
    return FinanceForecast(
        opportunity_id=opportunity.id,
        forecast_category=_forecast_category(signal),
        start_month=opportunity.forecast_start_month,
        revenue_to_year_end=opportunity.estimated_annual_revenue,
        estimated_margin=opportunity.estimated_gross_margin,
        margin_percentage=opportunity.margin_percentage,
        probability_weighting=opportunity.probability,
        risk_adjustment=_risk_adjustment(opportunity.risk_rating),
        notes=(
            "Created from market signal conversion. Validate source value, expected "
            "tender date and contract term before LE1 use."
        ),
    )


def _create_executive_action_if_priority(
    signal: MarketSignal,
    opportunity: Opportunity,
) -> ExecutiveAction | None:
    if not _is_priority_signal(signal, opportunity):
        return None
    return ExecutiveAction(
        priority="high",
        category="Market Signal Conversion",
        owner="Sales Director",
        due_date=date.today() + timedelta(days=7),
        related_opportunity_id=opportunity.id,
        commercial_value=opportunity.estimated_total_contract_value,
        reason=(
            f"{signal.title} has {signal.likely_mitie_fit.lower()} Mitie fit and "
            f"estimated value of £{opportunity.estimated_total_contract_value:,.0f}."
        ),
        recommended_action=(
            signal.suggested_action
            or "Assign sales owner and validate buyer route to market."
        ),
        status="open",
    )


def _signal_query(signal: MarketSignal) -> str:
    return " | ".join(
        part
        for part in [
            signal.title,
            f"buyer: {signal.buyer_name}",
            f"sector: {signal.sector}",
            f"region: {signal.region}",
            signal.source_url or "",
        ]
        if part
    )


def _source_payload(signal: MarketSignal) -> dict[str, Any]:
    return {
        "title": signal.title,
        "url": signal.source_url,
        "source_type": signal.source_type,
        "source_attribution": signal.source_attribution,
        "confidence_score": signal.confidence_score,
    }


def _disciplines_for_signal(signal: MarketSignal) -> list[str]:
    haystack = f"{signal.title} {signal.suggested_action}".lower()
    disciplines = [
        discipline
        for keyword, discipline in DISCIPLINE_KEYWORDS.items()
        if keyword in haystack
    ]
    if "security" in haystack and "Access Control" not in disciplines:
        disciplines.append("Access Control")
    if disciplines:
        return list(dict.fromkeys(disciplines))
    return ["Fire Alarms", "Emergency Lighting", "Fire Risk Assessments"]


def _mitie_fit(signal: MarketSignal, disciplines: list[str]) -> str:
    value = float(signal.estimated_value or 0)
    strong_disciplines = {
        "Fire Alarms",
        "Emergency Lighting",
        "CCTV",
        "Access Control",
        "Fire Doors",
        "Fire Risk Assessments",
        "Passive Fire",
    }
    if signal.confidence_score >= 0.72 and value >= 750000 and set(disciplines) & strong_disciplines:
        return "High"
    if signal.confidence_score >= 0.55 or value >= 500000:
        return "Medium"
    return "Low"


def _market_signal_rationale(signal: MarketSignal, disciplines: list[str]) -> str:
    value = (
        f"estimated at £{signal.estimated_value:,.0f}"
        if signal.estimated_value is not None
        else "with value still unknown"
    )
    return (
        f"{signal.buyer_name} signal is {value}, maps to "
        f"{', '.join(disciplines[:3])}, and has "
        f"{round(signal.confidence_score * 100)}% source confidence. "
        "Confirm route to market before committing bid cost."
    )


def _stage_from_signal(signal: MarketSignal) -> str:
    if signal.expected_tender_date is None:
        return "Market signal"
    if signal.expected_tender_date <= date.today():
        return "Pre-tender"
    return "Market signal"


def _annual_revenue(total_value: float) -> float:
    if total_value <= 0:
        return 0
    return round(total_value / 4, 2)


def _margin_assumption(signal: MarketSignal) -> float:
    if signal.likely_mitie_fit == "High":
        return 30
    if signal.likely_mitie_fit == "Medium":
        return 26
    return 22


def _probability_assumption(signal: MarketSignal) -> float:
    base = min(max(signal.confidence_score, 0.15), 0.75)
    if signal.likely_mitie_fit == "High":
        base += 0.05
    if signal.expected_tender_date is None:
        base -= 0.08
    return round(min(max(base, 0.15), 0.8), 4)


def _forecast_start_month(expected_tender_date: date | None) -> str | None:
    if expected_tender_date is None:
        return None
    month = expected_tender_date.month + 3
    year = expected_tender_date.year + ((month - 1) // 12)
    month = ((month - 1) % 12) + 1
    return f"{year:04d}-{month:02d}"


def _risk_rating(signal: MarketSignal) -> str:
    value = float(signal.estimated_value or 0)
    if signal.confidence_score < 0.55 or value >= 2_500_000:
        return "Red"
    if signal.confidence_score < 0.75:
        return "Amber"
    return "Green"


def _strategic_fit_score(signal: MarketSignal) -> float:
    value = float(signal.estimated_value or 0)
    score = 45 + (signal.confidence_score * 25)
    if value >= 1_000_000:
        score += 12
    if signal.likely_mitie_fit == "High":
        score += 12
    elif signal.likely_mitie_fit == "Medium":
        score += 6
    return round(min(score, 100), 2)


def _bid_recommendation(signal: MarketSignal) -> str:
    if signal.likely_mitie_fit == "High" and signal.confidence_score >= 0.72:
        return "Pursue"
    if signal.confidence_score < 0.5:
        return "Watch"
    return "Pursue with executive sponsor" if _is_priority_value(signal) else "Watch"


def _field_value_type(signal: MarketSignal, field_name: str, value: Any) -> str:
    if field_name in {"submission_deadline"}:
        return "unknown"
    if value in (None, "", 0):
        return "unknown"
    if field_name in {
        "estimated_annual_revenue",
        "estimated_gross_margin",
        "margin_percentage",
        "probability",
        "weighted_value",
        "forecast_start_month",
        "self_delivery_fit",
        "risk_rating",
        "strategic_fit_score",
        "bid_no_bid_recommendation",
        "recommended_action",
        "stage",
    }:
        return "estimated" if field_name.startswith("estimated") else "inferred"
    return "known"


def _field_confidence(signal: MarketSignal, field_name: str, value_type: str) -> float:
    if value_type == "unknown":
        return 0
    if value_type == "known":
        return round(min(max(signal.confidence_score, 0.1), 1), 2)
    if field_name in {"estimated_annual_revenue", "estimated_gross_margin", "margin_percentage"}:
        return round(min(signal.confidence_score, 0.58), 2)
    return round(min(max(signal.confidence_score * 0.85, 0.35), 0.75), 2)


def _field_rationale(signal: MarketSignal, field_name: str, value_type: str) -> str:
    label = field_name.replace("_", " ")
    if value_type == "unknown":
        return f"{label} is not available from this market signal."
    if value_type == "known":
        return f"{label} is taken directly from the source-attributed market signal."
    if value_type == "estimated":
        return f"{label} is estimated from signal value, likely term and Mitie fit."
    return f"{label} is inferred from source confidence, sector, value and discipline fit."


def _field_next_step(field_name: str, value_type: str) -> str:
    label = field_name.replace("_", " ")
    if value_type == "unknown":
        return f"Confirm {label} from tender notice, buyer portal or approved CRM source."
    if value_type == "estimated":
        return f"Validate {label} before bid governance or LE1 forecast use."
    if value_type == "inferred":
        return f"Confirm inferred {label} with the opportunity owner."
    return f"Keep {label} aligned with source updates."


def _buyer_drivers(signal: MarketSignal) -> list[str]:
    sector = signal.sector.lower()
    if "health" in sector:
        return ["Patient safety", "Compliance assurance", "Minimal clinical disruption"]
    if "police" in sector or "government" in sector:
        return ["Secure estate resilience", "Audit trail", "Supplier assurance"]
    if "retail" in sector:
        return ["Estate uptime", "Brand protection", "Predictable compliance cost"]
    if "housing" in sector:
        return ["Resident safety", "Building safety compliance", "Remedial certainty"]
    return ["Compliance assurance", "Operational continuity", "Cost control"]


def _compliance_drivers(signal: MarketSignal) -> list[str]:
    disciplines = signal.potential_disciplines or _disciplines_for_signal(signal)
    drivers = ["Fire safety compliance", "Statutory evidence and auditability"]
    if any("Security" in discipline or discipline in {"CCTV", "Access Control"} for discipline in disciplines):
        drivers.append("Security resilience and access governance")
    return drivers


def _forecast_category(signal: MarketSignal) -> str:
    if signal.confidence_score >= 0.75 and signal.likely_mitie_fit == "High":
        return "Likely"
    if signal.confidence_score >= 0.6:
        return "Best case"
    return "Stretch"


def _risk_adjustment(risk_rating: str) -> float:
    if risk_rating == "Red":
        return 0.4
    if risk_rating == "Amber":
        return 0.2
    return 0.05


def _is_priority_value(signal: MarketSignal) -> bool:
    return float(signal.estimated_value or 0) >= 1_000_000


def _is_priority_signal(signal: MarketSignal, opportunity: Opportunity) -> bool:
    return (
        _is_priority_value(signal)
        and signal.likely_mitie_fit in {"High", "Medium"}
        and opportunity.strategic_fit_score >= 70
    )
