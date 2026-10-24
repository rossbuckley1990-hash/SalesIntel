from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Opportunity
from app.routers.query import Limit, contains_text
from app.schemas import OpportunityRead
from app.services.opportunity_intelligence import enrich_opportunities, enrich_opportunity

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("", response_model=list[OpportunityRead])
def list_opportunities(
    db: Session = Depends(get_db),
    limit: Limit = 100,
    sector: str | None = None,
    region: str | None = None,
    stage: str | None = None,
    risk_rating: str | None = None,
    owner: str | None = None,
    search: str | None = None,
) -> list[OpportunityRead]:
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

    opportunities = enrich_opportunities(list(db.scalars(statement)))
    if risk_rating:
        opportunities = [
            opportunity
            for opportunity in opportunities
            if _normalise_risk_filter(opportunity.calculated_risk_rating or opportunity.risk_rating)
            == _normalise_risk_filter(risk_rating)
        ]

    return opportunities[:limit]


@router.get("/{opportunity_id}", response_model=OpportunityRead)
def get_opportunity(opportunity_id: int, db: Session = Depends(get_db)) -> OpportunityRead:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return enrich_opportunity(opportunity)


def _normalise_risk_filter(value: str) -> str:
    normalised = value.strip().lower()
    if normalised in {"red", "high"}:
        return "red"
    if normalised in {"amber", "medium"}:
        return "amber"
    if normalised in {"green", "low"}:
        return "green"
    return normalised
