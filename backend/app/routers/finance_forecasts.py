from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FinanceForecast
from app.routers.query import Limit
from app.schemas import FinanceForecastRead, FinanceForecastSummaryRead
from app.services.finance_summary import build_finance_forecast_summary

router = APIRouter(prefix="/api/finance-forecast", tags=["finance forecasts"])


@router.get("/summary", response_model=FinanceForecastSummaryRead)
def get_finance_forecast_summary(
    db: Session = Depends(get_db),
    as_of: date | None = None,
    financial_year_start: int | None = None,
) -> FinanceForecastSummaryRead:
    return build_finance_forecast_summary(
        db,
        as_of=as_of,
        financial_year_start=financial_year_start,
    )


@router.get("", response_model=list[FinanceForecastRead])
def list_finance_forecasts(
    db: Session = Depends(get_db),
    limit: Limit = 100,
    opportunity_id: int | None = None,
    forecast_category: str | None = None,
    start_month: str | None = None,
) -> list[FinanceForecast]:
    statement = select(FinanceForecast).order_by(FinanceForecast.start_month, FinanceForecast.id)

    if opportunity_id is not None:
        statement = statement.where(FinanceForecast.opportunity_id == opportunity_id)
    if forecast_category:
        statement = statement.where(FinanceForecast.forecast_category == forecast_category)
    if start_month:
        statement = statement.where(FinanceForecast.start_month == start_month)

    return list(db.scalars(statement.limit(limit)))
