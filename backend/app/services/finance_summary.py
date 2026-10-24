from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import FinanceForecast, Opportunity
from app.schemas.finance_forecast import (
    FinanceForecastPoint,
    FinanceForecastSummaryRead,
    FinanceReviewItem,
    FinanceWarning,
    OpenForecastItem,
    SecuredWorkItem,
)

FORECAST_CATEGORIES = {
    "Committed",
    "Best case",
    "Likely",
    "Stretch",
    "At risk",
    "Excluded",
}
MARGIN_WARNING_THRESHOLD = 25.0
RISK_REVIEW_THRESHOLD = 0.15
WON_STAGES = {"won"}
CLOSED_STAGES = {"lost", "qualified out"}


def financial_year_for_date(as_of: date) -> tuple[int, int]:
    if as_of.month >= 4:
        return as_of.year, as_of.year + 1
    return as_of.year - 1, as_of.year


def financial_year_months(financial_year_start: int) -> list[str]:
    months = []
    for index in range(12):
        month_number = index + 4
        year = financial_year_start
        if month_number > 12:
            month_number -= 12
            year += 1
        months.append(f"{year}-{month_number:02d}")
    return months


def build_finance_forecast_summary(
    db: Session,
    *,
    as_of: date | None = None,
    financial_year_start: int | None = None,
) -> FinanceForecastSummaryRead:
    active_as_of = as_of or date.today()
    fy_start, fy_end = (
        (financial_year_start, financial_year_start + 1)
        if financial_year_start is not None
        else financial_year_for_date(active_as_of)
    )
    fy_months = financial_year_months(fy_start)

    monthly_revenue = {month: 0.0 for month in fy_months}
    monthly_margin = {month: 0.0 for month in fy_months}
    secured_work: list[SecuredWorkItem] = []
    open_opportunities: list[OpenForecastItem] = []
    margin_warnings: list[FinanceWarning] = []
    finance_review_items: list[FinanceReviewItem] = []

    forecasts = list(
        db.scalars(
            select(FinanceForecast)
            .options(joinedload(FinanceForecast.opportunity))
            .order_by(FinanceForecast.start_month, FinanceForecast.id)
        )
    )
    forecasts_in_year = [
        forecast for forecast in forecasts if forecast.start_month in fy_months
    ]
    forecasted_won_opportunity_ids: set[int] = set()

    for forecast in forecasts_in_year:
        opportunity = forecast.opportunity
        if _is_won(opportunity):
            forecasted_won_opportunity_ids.add(opportunity.id)
            item = _secured_item_from_forecast(forecast)
            secured_work.append(item)
            _add_phased_value(
                monthly_revenue,
                item.won_revenue,
                start_month=item.delivery_start_month,
                financial_year_months=fy_months,
            )
            _add_phased_value(
                monthly_margin,
                item.won_gross_margin,
                start_month=item.delivery_start_month,
                financial_year_months=fy_months,
            )
            _add_margin_warning(
                item.opportunity_id,
                item.opportunity_name,
                item.client,
                item.margin_percentage,
                margin_warnings,
                finance_review_items,
            )
            continue

        if _is_closed(opportunity):
            continue

        item = _open_item_from_forecast(forecast)
        open_opportunities.append(item)
        _add_phased_value(
            monthly_revenue,
            item.risk_adjusted_revenue,
            start_month=item.forecast_start_month,
            financial_year_months=fy_months,
        )
        _add_phased_value(
            monthly_margin,
            item.risk_adjusted_margin,
            start_month=item.forecast_start_month,
            financial_year_months=fy_months,
        )
        _add_margin_warning(
            item.opportunity_id,
            item.opportunity_name,
            item.client,
            item.margin_percentage,
            margin_warnings,
            finance_review_items,
        )
        _add_risk_review_item(item, finance_review_items)

    for opportunity in _won_opportunities_without_forecast(
        db,
        fy_months=fy_months,
        forecasted_won_opportunity_ids=forecasted_won_opportunity_ids,
    ):
        item = _secured_item_from_opportunity(opportunity, financial_year_months=fy_months)
        secured_work.append(item)
        _add_phased_value(
            monthly_revenue,
            item.won_revenue,
            start_month=item.delivery_start_month,
            financial_year_months=fy_months,
        )
        _add_phased_value(
            monthly_margin,
            item.won_gross_margin,
            start_month=item.delivery_start_month,
            financial_year_months=fy_months,
        )
        _add_margin_warning(
            item.opportunity_id,
            item.opportunity_name,
            item.client,
            item.margin_percentage,
            margin_warnings,
            finance_review_items,
        )

    secured_revenue = sum(item.won_revenue for item in secured_work)
    secured_gross_margin = sum(item.won_gross_margin for item in secured_work)
    open_weighted_revenue = sum(item.weighted_revenue for item in open_opportunities)
    open_weighted_margin = sum(item.weighted_margin for item in open_opportunities)
    risk_adjusted_revenue = sum(
        item.risk_adjusted_revenue for item in open_opportunities
    )
    risk_adjusted_margin = sum(item.risk_adjusted_margin for item in open_opportunities)

    return FinanceForecastSummaryRead(
        financial_year=f"{fy_start}/{str(fy_end)[-2:]}",
        financial_year_start=fy_start,
        financial_year_end=fy_end,
        financial_year_months=fy_months,
        monthly_revenue=_forecast_points(monthly_revenue),
        monthly_margin=_forecast_points(monthly_margin),
        secured_revenue=_round_money(secured_revenue),
        secured_gross_margin=_round_money(secured_gross_margin),
        secured_margin_percentage=_margin_percentage(
            secured_revenue,
            secured_gross_margin,
        ),
        open_weighted_revenue=_round_money(open_weighted_revenue),
        open_weighted_margin=_round_money(open_weighted_margin),
        risk_adjusted_revenue=_round_money(risk_adjusted_revenue),
        risk_adjusted_margin=_round_money(risk_adjusted_margin),
        forecast_to_financial_year_end=_round_money(
            secured_revenue + risk_adjusted_revenue
        ),
        forecast_margin_to_financial_year_end=_round_money(
            secured_gross_margin + risk_adjusted_margin
        ),
        secured_work=secured_work,
        open_opportunities=open_opportunities,
        margin_warnings=margin_warnings,
        finance_review_items=finance_review_items,
    )


def _secured_item_from_forecast(forecast: FinanceForecast) -> SecuredWorkItem:
    opportunity = forecast.opportunity
    return SecuredWorkItem(
        opportunity_id=opportunity.id,
        opportunity_name=opportunity.name,
        client=opportunity.buyer_name,
        won_revenue=_round_money(forecast.revenue_to_year_end),
        won_gross_margin=_round_money(forecast.estimated_margin),
        margin_percentage=forecast.margin_percentage,
        delivery_start_month=forecast.start_month,
        business_unit=_optional_text_attr(opportunity, "business_unit"),
        discipline=_optional_text_attr(opportunity, "discipline"),
        confidence=1.0,
    )


def _secured_item_from_opportunity(
    opportunity: Opportunity,
    *,
    financial_year_months: list[str],
) -> SecuredWorkItem:
    delivery_start_month = opportunity.forecast_start_month or financial_year_months[0]
    active_month_count = len(
        _active_financial_year_months(
            start_month=delivery_start_month,
            financial_year_months=financial_year_months,
        )
    )
    won_revenue = (opportunity.estimated_annual_revenue / 12) * active_month_count
    won_margin = won_revenue * (_normalise_percentage(opportunity.margin_percentage))

    return SecuredWorkItem(
        opportunity_id=opportunity.id,
        opportunity_name=opportunity.name,
        client=opportunity.buyer_name,
        won_revenue=_round_money(won_revenue),
        won_gross_margin=_round_money(won_margin),
        margin_percentage=opportunity.margin_percentage,
        delivery_start_month=delivery_start_month,
        business_unit=_optional_text_attr(opportunity, "business_unit"),
        discipline=_optional_text_attr(opportunity, "discipline"),
        confidence=1.0,
    )


def _open_item_from_forecast(forecast: FinanceForecast) -> OpenForecastItem:
    opportunity = forecast.opportunity
    probability = _normalise_factor(
        forecast.probability_weighting or opportunity.probability
    )
    risk_adjustment = _normalise_factor(forecast.risk_adjustment)
    forecast_category = _normalise_forecast_category(
        forecast.forecast_category,
        opportunity=opportunity,
        probability_weighting=probability,
        risk_adjustment=risk_adjustment,
    )

    if forecast_category == "Excluded":
        weighted_revenue = 0.0
        weighted_margin = 0.0
    else:
        weighted_revenue = forecast.revenue_to_year_end * probability
        weighted_margin = forecast.estimated_margin * probability

    risk_adjusted_revenue = weighted_revenue * (1 - risk_adjustment)
    risk_adjusted_margin = weighted_margin * (1 - risk_adjustment)

    return OpenForecastItem(
        opportunity_id=opportunity.id,
        opportunity_name=opportunity.name,
        client=opportunity.buyer_name,
        forecast_start_month=forecast.start_month,
        revenue_to_financial_year_end=_round_money(forecast.revenue_to_year_end),
        estimated_margin=_round_money(forecast.estimated_margin),
        margin_percentage=forecast.margin_percentage,
        probability_weighting=probability,
        risk_adjustment=risk_adjustment,
        forecast_category=forecast_category,
        weighted_revenue=_round_money(weighted_revenue),
        weighted_margin=_round_money(weighted_margin),
        risk_adjusted_revenue=_round_money(risk_adjusted_revenue),
        risk_adjusted_margin=_round_money(risk_adjusted_margin),
    )


def _won_opportunities_without_forecast(
    db: Session,
    *,
    fy_months: list[str],
    forecasted_won_opportunity_ids: set[int],
) -> list[Opportunity]:
    final_month_key = _month_key(fy_months[-1])
    opportunities = list(
        db.scalars(select(Opportunity).where(Opportunity.stage == "Won").order_by(Opportunity.id))
    )
    return [
        opportunity
        for opportunity in opportunities
        if opportunity.id not in forecasted_won_opportunity_ids
        and final_month_key is not None
        and _month_key(opportunity.forecast_start_month or fy_months[0]) is not None
        and _month_key(opportunity.forecast_start_month or fy_months[0]) <= final_month_key
    ]


def _normalise_forecast_category(
    forecast_category: str,
    *,
    opportunity: Opportunity,
    probability_weighting: float,
    risk_adjustment: float,
) -> str:
    raw_category = _normalise(forecast_category)
    alias_map = {
        "committed": "Committed",
        "best case": "Best case",
        "best_case": "Best case",
        "likely": "Likely",
        "stretch": "Stretch",
        "at risk": "At risk",
        "at_risk": "At risk",
        "excluded": "Excluded",
    }
    if _is_won(opportunity):
        return "Committed"
    if raw_category in alias_map:
        return alias_map[raw_category]
    return _derived_forecast_category(
        opportunity,
        probability_weighting=probability_weighting,
        risk_adjustment=risk_adjustment,
    )


def _derived_forecast_category(
    opportunity: Opportunity,
    *,
    probability_weighting: float,
    risk_adjustment: float,
) -> str:
    if _is_closed(opportunity):
        return "Excluded"
    if _normalise(opportunity.bid_no_bid_recommendation) in {"no bid", "no_bid"}:
        return "Excluded"
    if _normalise(opportunity.risk_rating) in {"high", "red", "high risk"}:
        return "At risk"
    if risk_adjustment >= RISK_REVIEW_THRESHOLD:
        return "At risk"
    if probability_weighting >= 0.75:
        return "Committed"
    if probability_weighting >= 0.6:
        return "Likely"
    if probability_weighting >= 0.4:
        return "Best case"
    return "Stretch"


def _add_phased_value(
    monthly_values: dict[str, float],
    total_value: float,
    *,
    start_month: str,
    financial_year_months: list[str],
) -> None:
    active_months = _active_financial_year_months(
        start_month=start_month,
        financial_year_months=financial_year_months,
    )
    if not active_months:
        return

    monthly_value = total_value / len(active_months)
    for month in active_months:
        monthly_values[month] += monthly_value


def _active_financial_year_months(
    *,
    start_month: str,
    financial_year_months: list[str],
) -> list[str]:
    start_key = _month_key(start_month)
    if start_key is None:
        return []
    return [
        month
        for month in financial_year_months
        if (month_key := _month_key(month)) is not None and month_key >= start_key
    ]


def _add_margin_warning(
    opportunity_id: int,
    opportunity_name: str,
    client: str,
    margin_percentage: float,
    margin_warnings: list[FinanceWarning],
    finance_review_items: list[FinanceReviewItem],
) -> None:
    if margin_percentage >= MARGIN_WARNING_THRESHOLD:
        return

    margin_warnings.append(
        FinanceWarning(
            opportunity_id=opportunity_id,
            opportunity_name=opportunity_name,
            client=client,
            margin_percentage=margin_percentage,
            threshold_percentage=MARGIN_WARNING_THRESHOLD,
            reason="Forecast margin is below the 25% finance review threshold.",
        )
    )
    finance_review_items.append(
        FinanceReviewItem(
            opportunity_id=opportunity_id,
            opportunity_name=opportunity_name,
            client=client,
            priority="high" if margin_percentage < 20 else "medium",
            category="Margin warning",
            reason="Forecast margin is below the target threshold.",
            recommended_action="Review pricing, delivery assumptions and recovery options before LE1 submission.",
        )
    )


def _add_risk_review_item(
    item: OpenForecastItem,
    finance_review_items: list[FinanceReviewItem],
) -> None:
    if item.forecast_category == "At risk":
        finance_review_items.append(
            FinanceReviewItem(
                opportunity_id=item.opportunity_id,
                opportunity_name=item.opportunity_name,
                client=item.client,
                priority="high",
                category="Risk adjustment",
                reason="Open forecast is categorised as At risk.",
                recommended_action="Confirm risk adjustment, owner action and latest bid/no-bid position.",
            )
        )
        return

    if item.risk_adjustment >= RISK_REVIEW_THRESHOLD:
        finance_review_items.append(
            FinanceReviewItem(
                opportunity_id=item.opportunity_id,
                opportunity_name=item.opportunity_name,
                client=item.client,
                priority="medium",
                category="Risk adjustment",
                reason="Risk adjustment is 15% or higher.",
                recommended_action="Validate the LE1 downside scenario with commercial and operations leads.",
            )
        )


def _forecast_points(monthly_values: dict[str, float]) -> list[FinanceForecastPoint]:
    return [
        FinanceForecastPoint(month=month, value=_round_money(value))
        for month, value in monthly_values.items()
    ]


def _margin_percentage(revenue: float, margin: float) -> float:
    if revenue == 0:
        return 0
    return round((margin / revenue) * 100, 2)


def _normalise_factor(value: float) -> float:
    if value <= 0:
        return 0
    if value <= 1:
        return min(value, 1)
    return min(value / 100, 1)


def _normalise_percentage(value: float) -> float:
    return _normalise_factor(value)


def _round_money(value: float) -> float:
    return round(value, 2)


def _month_key(month: str) -> int | None:
    try:
        year_text, month_text = month.split("-", 1)
        year = int(year_text)
        month_number = int(month_text)
    except ValueError:
        return None
    if month_number < 1 or month_number > 12:
        return None
    return year * 12 + month_number


def _is_won(opportunity: Opportunity) -> bool:
    return _normalise(opportunity.stage) in WON_STAGES


def _is_closed(opportunity: Opportunity) -> bool:
    return _normalise(opportunity.stage) in CLOSED_STAGES


def _normalise(value: str) -> str:
    return value.strip().lower().replace("_", " ")


def _optional_text_attr(opportunity: Opportunity, attribute_name: str) -> str | None:
    value = getattr(opportunity, attribute_name, None)
    return value if isinstance(value, str) and value else None
