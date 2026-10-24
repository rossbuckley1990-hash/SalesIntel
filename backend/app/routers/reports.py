from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.report import ExecutiveSummaryReportRead
from app.services.reports import build_executive_summary_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/executive-summary", response_model=ExecutiveSummaryReportRead)
def get_executive_summary_report(
    db: Session = Depends(get_db),
    as_of: date | None = None,
) -> ExecutiveSummaryReportRead:
    return build_executive_summary_report(db, as_of=as_of)
