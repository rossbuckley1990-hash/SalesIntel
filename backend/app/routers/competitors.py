from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CompetitorProfile
from app.routers.query import Limit, contains_text
from app.schemas import CompetitorProfileRead

router = APIRouter(prefix="/api/competitors", tags=["competitors"])


@router.get("", response_model=list[CompetitorProfileRead])
def list_competitors(
    db: Session = Depends(get_db),
    limit: Limit = 100,
    sector: str | None = None,
    search: str | None = None,
) -> list[CompetitorProfile]:
    statement = select(CompetitorProfile).order_by(CompetitorProfile.id)

    if sector:
        statement = statement.where(contains_text(CompetitorProfile.sectors, search=sector))

    search_clause = contains_text(
        CompetitorProfile.name,
        CompetitorProfile.sectors,
        CompetitorProfile.strengths,
        CompetitorProfile.weaknesses,
        CompetitorProfile.counter_strategy,
        search=search,
    )
    if search_clause is not None:
        statement = statement.where(search_clause)

    return list(db.scalars(statement.limit(limit)))

