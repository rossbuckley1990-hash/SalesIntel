from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExecutiveAction, Opportunity
from app.schemas import ExecutiveActionRead, OpportunityRead
from app.schemas.report import (
    ExecutiveSummaryReportRead,
    ReportAggregate,
    ReportRiskRecommendation,
    SelfDeliveryReportOpportunity,
    SelfDeliveryReportSummary,
)
from app.services.dashboard import build_dashboard_summary
from app.services.finance_summary import build_finance_forecast_summary
from app.services.opportunity_intelligence import enrich_opportunities

REPORT_AUDIENCE = [
    "Managing Director",
    "Finance Director",
    "Group Sales Director",
    "Bid Manager",
    "Commercial Manager",
]
ACTIVE_ACTION_STATUSES = {"open", "in_progress"}
DECLINED_STAGES = {"lost", "qualified out"}
WON_STAGES = {"won"}
STRONG_SELF_DELIVERY_FITS = {"high", "strong"}
MODERATE_SELF_DELIVERY_FITS = {"medium", "moderate"}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

DISCIPLINE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Gas Suppression", ("gas suppression", "suppression", "vesda")),
    ("Fire Risk Assessments", ("fire risk assessment", "fra ")),
    ("Emergency Lighting", ("emergency lighting",)),
    ("Disabled Refuge", ("disabled refuge", "refuge")),
    ("Access Control", ("access control",)),
    ("Intruder Alarms", ("intruder alarm",)),
    ("Fire Dampers", ("fire damper", "dampers")),
    ("Smoke Control", ("smoke control",)),
    ("Extinguishers", ("extinguishers", "extinguisher")),
    ("Dry Risers", ("dry riser",)),
    ("Sprinklers", ("sprinkler",)),
    ("Fire Doors", ("fire door",)),
    ("Passive Fire", ("passive fire", "remediation", "remedials")),
    ("PAVA", ("pava",)),
    ("CCTV", ("cctv",)),
    ("Fire Alarms", ("fire alarm", "fire detection", "alarm")),
)

SUPPLIER_BY_DISCIPLINE = {
    "Fire Alarms": "Incumbent Fire Alarm Specialist",
    "Emergency Lighting": "Regional Electrical Compliance Partner",
    "Extinguishers": "National Extinguisher Service",
    "Intruder Alarms": "Security Systems Subcontractor",
    "CCTV": "CCTV Integration Partner",
    "Access Control": "Access Control Integrator",
    "PAVA": "Voice Alarm Specialist",
    "Disabled Refuge": "Life Safety Communications Partner",
    "Fire Doors": "Passive Fire Door Contractor",
    "Dry Risers": "Dry Riser Testing Contractor",
    "Sprinklers": "Sprinkler Inspection Partner",
    "Fire Dampers": "Airside Fire Damper Contractor",
    "Smoke Control": "Smoke Control Specialist",
    "Gas Suppression": "Specialist Suppression Partner",
    "Fire Risk Assessments": "Independent FRA Bureau",
    "Passive Fire": "Passive Fire Remedials Contractor",
}


def build_executive_summary_report(
    db: Session,
    *,
    as_of: date | None = None,
) -> ExecutiveSummaryReportRead:
    reporting_date = as_of or date.today()
    dashboard = build_dashboard_summary(db, today=reporting_date)
    finance_forecast = build_finance_forecast_summary(db, as_of=reporting_date)
    opportunities = enrich_opportunities(
        list(db.scalars(select(Opportunity).order_by(Opportunity.id))),
        today=reporting_date,
    )
    executive_actions = _get_report_actions(db)
    self_delivery_summary = _build_self_delivery_summary(opportunities)
    leadership_summary = _build_leadership_summary(
        dashboard=dashboard,
        finance=finance_forecast,
        self_delivery=self_delivery_summary,
    )

    return ExecutiveSummaryReportRead(
        report_name="MiSi Executive Summary",
        generated_at=datetime.now(UTC),
        reporting_date=reporting_date,
        audience=REPORT_AUDIENCE,
        data_note=(
            "MVP report generated from current MiSi local data. Treat as commercially "
            "sensitive and validate against source systems before external use."
        ),
        dashboard_kpis=dashboard,
        leadership_summary=leadership_summary,
        top_opportunities=dashboard.top_opportunities,
        finance_forecast=finance_forecast,
        self_delivery_summary=self_delivery_summary,
        executive_actions=executive_actions,
        risks_and_recommendations=_build_risks_and_recommendations(
            dashboard=dashboard,
            finance=finance_forecast,
            self_delivery=self_delivery_summary,
            executive_actions=executive_actions,
        ),
    )


def _get_report_actions(db: Session) -> list[ExecutiveActionRead]:
    actions = list(
        db.scalars(
            select(ExecutiveAction).where(
                ExecutiveAction.status.in_(ACTIVE_ACTION_STATUSES)
            )
        )
    )
    sorted_actions = sorted(
        actions,
        key=lambda action: (
            PRIORITY_RANK.get(action.priority, 99),
            action.due_date or date.max,
            action.id,
        ),
    )
    return [ExecutiveActionRead.model_validate(action) for action in sorted_actions[:10]]


def _build_leadership_summary(
    *,
    dashboard,
    finance,
    self_delivery: SelfDeliveryReportSummary,
):
    headline = (
        f"Protect {dashboard.live_opportunity_count} live pursuits and convert "
        f"the highest-quality weighted pipeline with finance discipline."
    )
    summary = (
        f"MiSi is showing {dashboard.live_opportunity_count} live opportunities, "
        f"{dashboard.strategic_must_win_count} strategic must-wins and "
        f"{dashboard.high_risk_count} red risks. Weighted pipeline is "
        f"GBP {dashboard.weighted_pipeline_value:,.0f}; LE1 risk-adjusted revenue is "
        f"GBP {finance.risk_adjusted_revenue:,.0f}; self-delivery value at risk is "
        f"GBP {self_delivery.value_at_risk:,.0f}."
    )

    return {
        "headline": headline,
        "summary": summary,
        "md_attention": [
            (
                "Sponsor strategic must-wins and remove executive blockers before "
                "final submission or negotiation."
            ),
            (
                "Hold owners to named next actions on high-value opportunities rather "
                "than accepting generic pipeline commentary."
            ),
        ],
        "finance_attention": [
            (
                f"Review {len(finance.margin_warnings)} margin warning"
                f"{'' if len(finance.margin_warnings) == 1 else 's'} before pricing "
                "is locked."
            ),
            (
                f"Validate the GBP {finance.forecast_to_financial_year_end:,.0f} "
                "forecast to financial year end against LE1 assumptions."
            ),
        ],
        "sales_attention": [
            (
                "Confirm buyer access, decision criteria and competitive position for "
                "the top five priority opportunities."
            ),
            (
                f"Convert the GBP {dashboard.weighted_pipeline_value:,.0f} weighted "
                "pipeline into named weekly deal actions."
            ),
        ],
        "bid_team_attention": [
            (
                f"Focus bid capacity on {dashboard.live_tender_count} live tenders "
                "and escalate weak-margin submissions early."
            ),
            "Keep clarification, pricing and final review activity visible to leadership.",
        ],
        "risk_warnings": [
            f"{dashboard.high_risk_count} red-risk opportunity/opportunities need sponsor control.",
            f"{dashboard.urgent_deadline_count} urgent deadline(s) need bid ownership confirmation.",
            f"{len(finance.finance_review_items)} finance review item(s) need FD or bid governance.",
        ],
        "next_best_actions": [
            "Run a 30-minute MD/FD/GSD pipeline review on the top opportunities.",
            "Confirm finance guardrails for every margin warning before submission.",
            "Route self-delivery opportunities to Mitie Fire & Security before third-party leakage.",
        ],
    }


def _build_self_delivery_summary(
    opportunities: list[OpportunityRead],
) -> SelfDeliveryReportSummary:
    insights = [_to_self_delivery_opportunity(opportunity) for opportunity in opportunities]
    accepted = [
        insight
        for insight, opportunity in zip(insights, opportunities, strict=True)
        if _is_accepted_self_delivery(opportunity)
    ]
    declined = [
        insight
        for insight, opportunity in zip(insights, opportunities, strict=True)
        if _is_declined_self_delivery(opportunity)
    ]
    route_opportunities = sorted(
        [
            insight
            for insight, opportunity in zip(insights, opportunities, strict=True)
            if _is_route_candidate(opportunity)
        ],
        key=_self_delivery_sort_key,
    )[:8]
    leakage_risks = sorted(
        [
            insight
            for insight, opportunity in zip(insights, opportunities, strict=True)
            if _is_leakage_risk(opportunity)
        ],
        key=_self_delivery_sort_key,
    )[:8]
    decision_count = len(accepted) + len(declined)

    return SelfDeliveryReportSummary(
        opportunity_value=round(sum(item.estimated_value for item in insights), 2),
        value_captured=round(sum(_captured_value(item) for item in accepted), 2),
        value_at_risk=round(sum(item.estimated_value for item in leakage_risks), 2),
        accepted_count=len(accepted),
        declined_count=len(declined),
        conversion_rate=round(len(accepted) / decision_count, 4)
        if decision_count
        else 0,
        top_displaced_suppliers=_aggregate(
            insights,
            lambda item: SUPPLIER_BY_DISCIPLINE.get(
                item.discipline,
                "Specialist Fire & Security Supplier",
            ),
        )[:5],
        disciplines_with_highest_opportunity=_aggregate(
            insights,
            lambda item: item.discipline,
        )[:8],
        route_opportunities=route_opportunities,
        leakage_risks=leakage_risks,
    )


def _to_self_delivery_opportunity(
    opportunity: OpportunityRead,
) -> SelfDeliveryReportOpportunity:
    discipline = _infer_discipline(opportunity)
    return SelfDeliveryReportOpportunity(
        opportunity_id=opportunity.id,
        name=opportunity.name,
        buyer_name=opportunity.buyer_name,
        discipline=discipline,
        estimated_value=opportunity.estimated_total_contract_value,
        weighted_value=opportunity.weighted_pipeline_value,
        risk_rating=opportunity.calculated_risk_rating or opportunity.risk_rating,
        recommended_action=(
            opportunity.calculated_recommended_action
            or opportunity.recommended_action
            or "Confirm whether the scope should be routed through Mitie Fire & Security."
        ),
    )


def _is_accepted_self_delivery(opportunity: OpportunityRead) -> bool:
    if _is_declined_self_delivery(opportunity):
        return False

    return (
        opportunity.self_delivery_capture
        or _normalise(opportunity.self_delivery_fit) in STRONG_SELF_DELIVERY_FITS
        or _normalise(opportunity.stage) in WON_STAGES
    )


def _is_declined_self_delivery(opportunity: OpportunityRead) -> bool:
    recommendation = _normalise(opportunity.calculated_bid_no_bid_recommendation)
    return (
        _normalise(opportunity.stage) in DECLINED_STAGES
        or recommendation in {"no bid", "qualify out"}
        or _normalise(opportunity.self_delivery_fit) == "weak"
    )


def _is_route_candidate(opportunity: OpportunityRead) -> bool:
    if _is_declined_self_delivery(opportunity):
        return False
    return (
        opportunity.self_delivery_capture
        or _normalise(opportunity.self_delivery_fit) in STRONG_SELF_DELIVERY_FITS
    )


def _is_leakage_risk(opportunity: OpportunityRead) -> bool:
    if _is_declined_self_delivery(opportunity):
        return False

    return (
        not opportunity.self_delivery_capture
        or _normalise(opportunity.self_delivery_fit) in MODERATE_SELF_DELIVERY_FITS
        or opportunity.calculated_risk_rating == "Red"
        or opportunity.calculated_bid_no_bid_recommendation == "Watch"
    )


def _captured_value(item: SelfDeliveryReportOpportunity) -> float:
    return item.estimated_value if item.risk_rating == "Green" else item.weighted_value


def _infer_discipline(opportunity: OpportunityRead) -> str:
    haystack = f"{opportunity.name} {opportunity.recommended_action}".lower()
    for discipline, patterns in DISCIPLINE_PATTERNS:
        if any(pattern in haystack for pattern in patterns):
            return discipline
    if opportunity.sector == "Facilities Management":
        return "Passive Fire"
    return "Fire Alarms"


def _aggregate(
    items: list[SelfDeliveryReportOpportunity],
    get_label,
) -> list[ReportAggregate]:
    totals: dict[str, ReportAggregate] = {}
    for item in items:
        label = get_label(item)
        current = totals.get(label) or ReportAggregate(label=label, value=0, count=0)
        current.value = round(current.value + item.estimated_value, 2)
        current.count += 1
        totals[label] = current
    return sorted(totals.values(), key=lambda item: (-item.value, item.label))


def _self_delivery_sort_key(item: SelfDeliveryReportOpportunity) -> tuple[int, float]:
    return (-_risk_priority(item.risk_rating), -item.estimated_value)


def _risk_priority(risk_rating: str) -> int:
    normalised = _normalise(risk_rating)
    if normalised == "red":
        return 3
    if normalised == "amber":
        return 2
    if normalised == "green":
        return 1
    return 0


def _build_risks_and_recommendations(
    *,
    dashboard,
    finance,
    self_delivery: SelfDeliveryReportSummary,
    executive_actions: list[ExecutiveActionRead],
) -> list[ReportRiskRecommendation]:
    risks = [
        ReportRiskRecommendation(
            priority="high" if dashboard.high_risk_count else "medium",
            category="Pipeline risk",
            summary=(
                f"{dashboard.high_risk_count} red-risk pursuit(s) and "
                f"{dashboard.urgent_deadline_count} urgent deadline(s) require leadership control."
            ),
            commercial_value=dashboard.weighted_pipeline_value,
            owner="Group Sales Director",
            recommended_action=(
                "Confirm executive sponsors, bid ownership and close dates for the "
                "highest-risk live opportunities this week."
            ),
        ),
        ReportRiskRecommendation(
            priority="high" if finance.margin_warnings else "medium",
            category="Finance governance",
            summary=(
                f"{len(finance.margin_warnings)} margin warning(s) and "
                f"{len(finance.finance_review_items)} finance review item(s) are visible in LE1."
            ),
            commercial_value=finance.forecast_to_financial_year_end,
            owner="Finance Director",
            recommended_action=(
                "Review pricing, delivery assumptions and risk adjustments before "
                "final bid sign-off."
            ),
        ),
        ReportRiskRecommendation(
            priority="medium",
            category="Self-delivery capture",
            summary=(
                f"GBP {self_delivery.value_at_risk:,.0f} of self-delivery value is "
                "at risk of third-party leakage."
            ),
            commercial_value=self_delivery.value_at_risk,
            owner="Commercial Manager",
            recommended_action=(
                "Route strong-fit fire and security scopes to Mitie Fire & Security "
                "before commercial close."
            ),
        ),
    ]

    for action in executive_actions[:3]:
        risks.append(
            ReportRiskRecommendation(
                priority=action.priority,
                category=action.category,
                summary=action.reason,
                commercial_value=action.commercial_value,
                owner=action.owner,
                recommended_action=action.recommended_action,
            )
        )

    return risks


def _normalise(value: str) -> str:
    return value.strip().lower().replace("_", " ")
