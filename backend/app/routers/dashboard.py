from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import DashboardSummaryRead
from app.services.dashboard import build_dashboard_summary

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummaryRead)
def get_dashboard(
    db: Session = Depends(get_db),
    sector: str | None = None,
    region: str | None = None,
    stage: str | None = None,
    risk_rating: str | None = None,
    owner: str | None = None,
    search: str | None = None,
) -> DashboardSummaryRead:
    return build_dashboard_summary(
        db,
        sector=sector,
        region=region,
        stage=stage,
        risk_rating=risk_rating,
        owner=owner,
        search=search,
    )

