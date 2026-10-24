from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EnrichmentRun, FieldIntelligence, OpportunityEnrichment
from app.routers.query import Limit
from app.schemas import (
    EnrichmentRunRead,
    FieldIntelligenceRead,
    OpportunityEnrichmentRead,
)

router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


@router.get("/runs", response_model=list[EnrichmentRunRead])
def list_enrichment_runs(
    db: Session = Depends(get_db),
    limit: Limit = 100,
    opportunity_id: int | None = None,
    run_type: str | None = None,
    status: str | None = None,
) -> list[EnrichmentRunRead]:
    statement = select(EnrichmentRun).order_by(EnrichmentRun.started_at.desc())
    if opportunity_id is not None:
        statement = statement.where(EnrichmentRun.opportunity_id == opportunity_id)
    if run_type:
        statement = statement.where(EnrichmentRun.run_type == run_type)
    if status:
        statement = statement.where(EnrichmentRun.status == status)
    return list(db.scalars(statement.limit(limit)))


@router.get("/runs/{run_id}", response_model=EnrichmentRunRead)
def get_enrichment_run(run_id: int, db: Session = Depends(get_db)) -> EnrichmentRunRead:
    run = db.get(EnrichmentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Enrichment run not found")
    return run


@router.get(
    "/opportunities/{opportunity_id}",
    response_model=list[OpportunityEnrichmentRead],
)
def list_opportunity_enrichments(
    opportunity_id: int,
    db: Session = Depends(get_db),
    limit: Limit = 20,
) -> list[OpportunityEnrichmentRead]:
    statement = (
        select(OpportunityEnrichment)
        .where(OpportunityEnrichment.opportunity_id == opportunity_id)
        .order_by(OpportunityEnrichment.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


@router.get("/field-intelligence", response_model=list[FieldIntelligenceRead])
def list_field_intelligence(
    entity_type: str = Query(min_length=1, max_length=80),
    entity_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    field_name: str | None = Query(default=None, max_length=120),
    limit: Limit = 200,
) -> list[FieldIntelligenceRead]:
    statement = (
        select(FieldIntelligence)
        .where(FieldIntelligence.entity_type == entity_type)
        .where(FieldIntelligence.entity_id == entity_id)
        .order_by(FieldIntelligence.field_name, FieldIntelligence.updated_at.desc())
        .limit(limit)
    )
    if field_name:
        statement = statement.where(FieldIntelligence.field_name == field_name)
    return list(db.scalars(statement))
