from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExecutiveAction, FinanceForecast, MarketSignal, Opportunity
from app.routers.query import contains_text
from app.schemas.dashboard import DashboardSummaryRead, ForecastPoint
from app.services.opportunity_intelligence import calculate_for_opportunity, enrich_opportunity

LIVE_EXCLUDED_STAGES = {"Won", "Lost", "Qualified out"}
LIVE_TENDER_STAGES = {
    "PQQ",
    "ITT live",
    "Clarification",
    "Pricing",
    "Final review",
    "Submitted",
    "Presentation",
    "Negotiation",
}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def build_dashboard_summary(
    db: Session,
    *,
    sector: str | None = None,
    region: str | None = None,
    stage: str | None = None,
    risk_rating: str | None = None,
    owner: str | None = None,
    search: str | None = None,
    today: date | None = None,
) -> DashboardSummaryRead:
    active_today = today or date.today()
    opportunities = _get_filtered_opportunities(
        db,
        sector=sector,
        region=region,
        stage=stage,
        owner=owner,
        search=search,
    )
    all_intelligence_by_id = {
        opportunity.id: calculate_for_opportunity(opportunity, today=active_today)
        for opportunity in opportunities
    }
    if risk_rating:
        expected_risk = _normalise_risk_filter(risk_rating)
        opportunities = [
            opportunity
            for opportunity in opportunities
            if _normalise_risk_filter(all_intelligence_by_id[opportunity.id].risk_rating)
            == expected_risk
        ]
    market_signals = _get_filtered_market_signals(
        db,
        sector=sector,
        region=region,
        search=search,
    )

    live_opportunities = [
        opportunity
        for opportunity in opportunities
        if opportunity.stage not in LIVE_EXCLUDED_STAGES
    ]
    opportunity_ids = {opportunity.id for opportunity in opportunities}
    live_opportunity_ids = {opportunity.id for opportunity in live_opportunities}
    intelligence_by_id = {
        opportunity.id: all_intelligence_by_id[opportunity.id]
        for opportunity in live_opportunities
    }

    total_pipeline_value = sum(
        opportunity.estimated_total_contract_value for opportunity in live_opportunities
    )
    weighted_pipeline_value = sum(
        intelligence_by_id[opportunity.id].weighted_pipeline_value
        for opportunity in live_opportunities
    )
    estimated_gross_margin = sum(
        opportunity.estimated_gross_margin for opportunity in live_opportunities
    )
    average_margin_percentage = (
        round((estimated_gross_margin / total_pipeline_value) * 100, 2)
        if total_pipeline_value
        else 0
    )

    top_opportunities = sorted(
        live_opportunities,
        key=lambda opportunity: (
            intelligence_by_id[opportunity.id].priority_score,
            intelligence_by_id[opportunity.id].weighted_pipeline_value,
        ),
        reverse=True,
    )[:5]
    top_executive_actions = _get_top_executive_actions(db, live_opportunity_ids)
    revenue_forecast, margin_forecast = _get_monthly_forecasts(db, opportunity_ids)

    live_opportunity_count = len(live_opportunities)
    strategic_must_win_count = sum(
        1
        for opportunity in live_opportunities
        if intelligence_by_id[opportunity.id].strategic_must_win
    )
    live_tender_count = sum(
        1 for opportunity in live_opportunities if opportunity.stage in LIVE_TENDER_STAGES
    )
    high_risk_count = sum(
        1
        for opportunity in live_opportunities
        if intelligence_by_id[opportunity.id].risk_rating == "Red"
    )
    urgent_deadline_count = sum(
        1
        for opportunity in live_opportunities
        if intelligence_by_id[opportunity.id].deadline_warning
    )

    return DashboardSummaryRead(
        total_pipeline_value=round(total_pipeline_value, 2),
        weighted_pipeline_value=round(weighted_pipeline_value, 2),
        estimated_gross_margin=round(estimated_gross_margin, 2),
        average_margin_percentage=average_margin_percentage,
        live_opportunity_count=live_opportunity_count,
        strategic_must_win_count=strategic_must_win_count,
        live_tender_count=live_tender_count,
        market_signal_count=len(market_signals),
        high_risk_count=high_risk_count,
        urgent_deadline_count=urgent_deadline_count,
        executive_summary_text=_build_executive_summary_text(
            weighted_pipeline_value=weighted_pipeline_value,
            live_opportunity_count=live_opportunity_count,
            high_risk_count=high_risk_count,
            urgent_deadline_count=urgent_deadline_count,
            top_executive_actions=top_executive_actions,
        ),
        monthly_revenue_forecast=revenue_forecast,
        monthly_margin_forecast=margin_forecast,
        top_opportunities=[
            enrich_opportunity(opportunity, today=active_today)
            for opportunity in top_opportunities
        ],
        top_executive_actions=top_executive_actions,
    )


def _get_filtered_opportunities(
    db: Session,
    *,
    sector: str | None,
    region: str | None,
    stage: str | None,
    owner: str | None,
    search: str | None,
) -> list[Opportunity]:
    statement = select(Opportunity).order_by(Opportunity.id)

    if sector:
        statement = statement.where(Opportunity.sector == sector)
    if region:
        statement = statement.where(Opportunity.region == region)
    if stage:
        statement = statement.where(Opportunity.stage == stage)
    if owner:
        statement = statement.where(Opportunity.owner == owner)

    search_clause = contains_text(
        Opportunity.name,
        Opportunity.buyer_name,
        Opportunity.sector,
        Opportunity.region,
        Opportunity.owner,
        search=search,
    )
    if search_clause is not None:
        statement = statement.where(search_clause)

    return list(db.scalars(statement))


def _get_filtered_market_signals(
    db: Session,
    *,
    sector: str | None,
    region: str | None,
    search: str | None,
) -> list[MarketSignal]:
    statement = select(MarketSignal).order_by(MarketSignal.id)

    if sector:
        statement = statement.where(MarketSignal.sector == sector)
    if region:
        statement = statement.where(MarketSignal.region == region)

    search_clause = contains_text(
        MarketSignal.title,
        MarketSignal.buyer_name,
        MarketSignal.sector,
        MarketSignal.region,
        MarketSignal.source_type,
        MarketSignal.source_attribution,
        search=search,
    )
    if search_clause is not None:
        statement = statement.where(search_clause)

    return list(db.scalars(statement))


def _get_top_executive_actions(
    db: Session,
    live_opportunity_ids: set[int],
) -> list[ExecutiveAction]:
    if not live_opportunity_ids:
        return []

    actions = list(
        db.scalars(
            select(ExecutiveAction)
            .where(ExecutiveAction.related_opportunity_id.in_(live_opportunity_ids))
            .where(ExecutiveAction.status.in_(["open", "in_progress"]))
        )
    )
    return sorted(
        actions,
        key=lambda action: (
            PRIORITY_RANK.get(action.priority, 99),
            action.due_date or date.max,
            action.id,
        ),
    )[:5]


def _get_monthly_forecasts(
    db: Session,
    live_opportunity_ids: set[int],
) -> tuple[list[ForecastPoint], list[ForecastPoint]]:
    if not live_opportunity_ids:
        return [], []

    forecasts = list(
        db.scalars(
            select(FinanceForecast)
            .where(FinanceForecast.opportunity_id.in_(live_opportunity_ids))
            .order_by(FinanceForecast.start_month)
        )
    )
    revenue_by_month: dict[str, float] = {}
    margin_by_month: dict[str, float] = {}

    for forecast in forecasts:
        revenue_by_month[forecast.start_month] = (
            revenue_by_month.get(forecast.start_month, 0) + forecast.revenue_to_year_end
        )
        margin_by_month[forecast.start_month] = (
            margin_by_month.get(forecast.start_month, 0) + forecast.estimated_margin
        )

    return (
        [
            ForecastPoint(month=month, value=round(value, 2))
            for month, value in sorted(revenue_by_month.items())
        ],
        [
            ForecastPoint(month=month, value=round(value, 2))
            for month, value in sorted(margin_by_month.items())
        ],
    )


def _build_executive_summary_text(
    *,
    weighted_pipeline_value: float,
    live_opportunity_count: int,
    high_risk_count: int,
    urgent_deadline_count: int,
    top_executive_actions: list[ExecutiveAction],
) -> str:
    if live_opportunity_count == 0:
        return "No live opportunities match the selected filters."

    action_text = (
        top_executive_actions[0].recommended_action
        if top_executive_actions
        else "Review the highest weighted opportunities and confirm next actions."
    )
    weighted_millions = weighted_pipeline_value / 1_000_000
    return (
        f"SalesIntel is tracking GBP {weighted_millions:.1f}m weighted pipeline across "
        f"{live_opportunity_count} live opportunities, with {high_risk_count} Red-risk "
        f"pursuits and {urgent_deadline_count} deadline warnings. Recommended next action: "
        f"{action_text}"
    )


def _normalise_risk_filter(value: str) -> str:
    normalised = value.strip().lower()
    if normalised in {"red", "high"}:
        return "red"
    if normalised in {"amber", "medium"}:
        return "amber"
    if normalised in {"green", "low"}:
        return "green"
    return normalised
