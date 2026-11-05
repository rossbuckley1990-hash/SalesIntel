"""Store immutable research snapshots alongside user-controlled sales reviews."""
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.research_dossier import ResearchContactSnapshot, ResearchLead, ResearchLeadAction, ResearchLeadFeedback, SavedResearchRun
from app.models.evidence_observation import EvidenceObservation
from app.schemas.evidence_observation import EvidenceObservationRead
from app.schemas.universal_research import UniversalResearchResult


def save_run(db: Session, job_id: str, result: dict[str, Any], completed_at: str | datetime) -> SavedResearchRun:
    existing = db.scalar(select(SavedResearchRun).where(SavedResearchRun.job_id == job_id))
    if existing:
        return existing
    # Do not rewrite historical snapshots by inserting fields introduced by
    # later schema versions; explicitly present fields remain durable.
    data = UniversalResearchResult.model_validate(result).model_dump(mode="json", exclude_unset=True)
    completed = datetime.fromisoformat(completed_at) if isinstance(completed_at, str) else completed_at
    run = SavedResearchRun(job_id=job_id, brief=data["brief"], model=data["model"], result=data, completed_at=completed)
    db.add(run)
    try:
        db.flush()
        for position, opportunity in enumerate(data["opportunities"]):
            db.add(ResearchLead(run_id=run.id, position=position, organisation=opportunity["organisation"],
                                location=opportunity["location"], headline=opportunity["headline"], opportunity=opportunity))
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent save of the same job is safe to reuse, never overwriting review work.
        existing = db.scalar(select(SavedResearchRun).where(SavedResearchRun.job_id == job_id))
        if existing is None:
            raise
        return existing
    db.refresh(run)
    return run


def persist_completed_research(job_id: str, result: dict[str, Any], completed_at: str) -> int:
    from app.db import SessionLocal
    with SessionLocal() as db:
        return save_run(db, job_id, result, completed_at).id


def action_dict(action: ResearchLeadAction, lead: ResearchLead) -> dict[str, Any]:
    def utc(value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return {"id": action.id, "lead_id": action.lead_id, "organisation": lead.organisation,
            "headline": lead.headline, "text": action.text, "status": action.status, "due_date": action.due_date,
            "created_at": utc(action.created_at), "updated_at": utc(action.updated_at)}


def lead_dict(db: Session, lead: ResearchLead, run: SavedResearchRun | None = None) -> dict[str, Any]:
    run = run or db.get(SavedResearchRun, lead.run_id)
    events = db.scalars(select(ResearchLeadFeedback).where(ResearchLeadFeedback.lead_id == lead.id)
                        .order_by(ResearchLeadFeedback.id)).all()
    contact_snapshot = db.scalar(select(ResearchContactSnapshot).where(ResearchContactSnapshot.lead_id == lead.id)
                                 .order_by(ResearchContactSnapshot.id.desc()).limit(1))
    actions = db.scalars(select(ResearchLeadAction).where(ResearchLeadAction.lead_id == lead.id)
                         .order_by(ResearchLeadAction.id.desc()).limit(50)).all()
    # A name match is a research hint, never proof of an entity or site match.
    # Limit related evidence and retain its original site and source provenance.
    normalised_name = lead.organisation.strip().lower()
    related = []
    if normalised_name:
        related = db.scalars(select(EvidenceObservation).where(
            func.lower(func.trim(EvidenceObservation.organisation_name)) == normalised_name
        ).order_by(EvidenceObservation.id.desc()).limit(20)).all()
    return {"id": lead.id, "run_id": lead.run_id, "position": lead.position,
            "organisation": lead.organisation, "location": lead.location, "headline": lead.headline,
            "status": lead.status, "notes": lead.notes, "created_at": lead.created_at,
            "updated_at": lead.updated_at, "opportunity": lead.opportunity,
            "brief": run.brief, "model": run.model, "observations": run.result.get("observations", []),
            "source_discovery": run.result.get("source_discovery"),
            "estate_lookup": run.result.get("estate_lookup"),
            "actions": [action_dict(action, lead) for action in actions],
            "related_observations": [EvidenceObservationRead.model_validate(item).model_dump(mode="json") for item in related],
            "related_observations_note": "Exact organisation-name matches only; identity, site relevance and sources require verification. They do not establish demand.",
            "contact_research": {"result": contact_snapshot.result, "researched_at":
                (contact_snapshot.researched_at.replace(tzinfo=UTC) if contact_snapshot.researched_at.tzinfo is None
                 else contact_snapshot.researched_at)}
                if contact_snapshot else None,
            "feedback": [{"id": e.id, "lead_id": e.lead_id, "previous_status": e.previous_status,
                          "status": e.status, "feedback": e.feedback, "notes": e.notes, "created_at": e.created_at}
                         for e in events]}


def run_dict(db: Session, run: SavedResearchRun) -> dict[str, Any]:
    leads = db.scalars(select(ResearchLead).where(ResearchLead.run_id == run.id).order_by(ResearchLead.position)).all()
    return {"id": run.id, "job_id": run.job_id, "brief": run.brief, "model": run.model,
            "created_at": run.created_at, "completed_at": run.completed_at, "result": run.result,
            "leads": [lead_dict(db, lead, run) for lead in leads]}
