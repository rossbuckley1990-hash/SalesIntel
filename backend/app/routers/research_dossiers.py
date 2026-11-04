"""Saved research dossiers and explicit salesperson review actions."""
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.research_dossier import ResearchContactSnapshot, ResearchLead, ResearchLeadAction, ResearchLeadFeedback, SavedResearchRun
from app.intelligence.openai_client import InvalidOpenAIJSONError, MissingOpenAIKeyError, OpenAIRequestError
from app.intelligence.public_contacts import research_public_contacts
from app.schemas.public_contacts import PublicContactRequest
from app.services.research_dossiers import action_dict, lead_dict, run_dict, save_run

router = APIRouter(prefix="/api/research-dossiers", tags=["research dossiers"])
LeadStatus = Literal["new", "investigate", "ready", "contacted", "qualified", "not_now", "not_relevant"]
Feedback = Literal["useful", "not_useful", "incorrect", "needs_research"]


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: LeadStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)
    feedback: Feedback | None = None

    @model_validator(mode="after")
    def require_action(self):
        if self.status is None and self.notes is None and self.feedback is None:
            raise ValueError("Provide a status, notes or feedback")
        return self


class NewLeadAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=5, max_length=1200)
    due_date: date | None = None


class LeadActionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["open", "completed", "deferred"] | None = None
    text: str | None = Field(default=None, min_length=5, max_length=1200)
    due_date: date | None = None

    @model_validator(mode="after")
    def require_action(self):
        if not self.model_fields_set:
            raise ValueError("Provide a status, action or due date")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Status cannot be null")
        if "text" in self.model_fields_set and self.text is None:
            raise ValueError("Action cannot be null")
        return self


@router.post("/from-job/{job_id}")
def save_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    existing = db.scalar(select(SavedResearchRun).where(SavedResearchRun.job_id == job_id))
    if existing:
        return run_dict(db, existing)
    from app.routers.universal_research_jobs import job_manager
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    if job["status"] != "completed" or job.get("result") is None:
        raise HTTPException(status_code=409, detail="Only completed research can be saved")
    return run_dict(db, save_run(db, job_id, job["result"], job["finished_at"]))


@router.get("/runs")
def list_runs(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db)) -> dict:
    total = db.scalar(select(func.count()).select_from(SavedResearchRun))
    runs = db.scalars(select(SavedResearchRun).order_by(SavedResearchRun.id.desc()).offset(offset).limit(limit)).all()
    return {"items": [run_dict(db, run) for run in runs], "total": total}


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    run = db.get(SavedResearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    return run_dict(db, run)


@router.get("/leads")
def list_leads(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
               status: LeadStatus | None = None, q: str | None = Query(default=None, max_length=120),
               db: Session = Depends(get_db)) -> dict:
    query = select(ResearchLead)
    count = select(func.count()).select_from(ResearchLead)
    if status is not None:
        query = query.where(ResearchLead.status == status)
        count = count.where(ResearchLead.status == status)
    if q and q.strip():
        # Escape SQL wildcard characters so the field is literal text search.
        text = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{text}%"
        matches = or_(*(func.lower(column).like(pattern, escape="\\") for column in
                        (ResearchLead.organisation, ResearchLead.headline, ResearchLead.location)))
        query, count = query.where(matches), count.where(matches)
    leads = db.scalars(query.order_by(ResearchLead.id.desc()).offset(offset).limit(limit)).all()
    return {"items": [lead_dict(db, lead) for lead in leads], "total": db.scalar(count)}


@router.get("/actions")
def list_research_actions(status: Literal["open", "completed", "deferred"] | None = None,
                          limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                          db: Session = Depends(get_db)) -> dict:
    query = select(ResearchLeadAction, ResearchLead).join(ResearchLead, ResearchLead.id == ResearchLeadAction.lead_id)
    count = select(func.count()).select_from(ResearchLeadAction)
    if status:
        query = query.where(ResearchLeadAction.status == status)
        count = count.where(ResearchLeadAction.status == status)
    # Real due dates, then undated actions; no synthetic urgency scores.
    rows = db.execute(query.order_by(ResearchLeadAction.due_date.is_(None),
                                    ResearchLeadAction.due_date.asc(), ResearchLeadAction.id.desc())
                      .offset(offset).limit(limit)).all()
    return {"items": [action_dict(action, lead) for action, lead in rows], "total": db.scalar(count)}


@router.post("/leads/{lead_id}/actions")
def add_research_action(lead_id: int, request: NewLeadAction, db: Session = Depends(get_db)) -> dict:
    lead = db.get(ResearchLead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Research lead not found")
    action = ResearchLeadAction(lead_id=lead.id, text=request.text, due_date=request.due_date)
    db.add(action)
    db.commit()
    db.refresh(action)
    return action_dict(action, lead)


@router.patch("/actions/{action_id}")
def update_research_action(action_id: int, request: LeadActionUpdate, db: Session = Depends(get_db)) -> dict:
    action = db.get(ResearchLeadAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Research action not found")
    if "status" in request.model_fields_set:
        action.status = request.status
    if "text" in request.model_fields_set:
        action.text = request.text
    if "due_date" in request.model_fields_set:
        action.due_date = request.due_date
    action.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(action)
    return action_dict(action, db.get(ResearchLead, action.lead_id))


@router.get("/leads/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db)) -> dict:
    lead = db.get(ResearchLead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Research lead not found")
    return lead_dict(db, lead)


@router.post("/leads/{lead_id}/contact-research")
def find_and_save_contacts(lead_id: int, db: Session = Depends(get_db)) -> dict:
    lead = db.get(ResearchLead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Research lead not found")
    item = lead.opportunity
    request = PublicContactRequest(organisation=lead.organisation, location=lead.location,
        contact_name=item.get("contact_name") or "", contact_role=item.get("contact_role") or "")
    try:
        result = research_public_contacts(request)
    except MissingOpenAIKeyError as exc:
        raise HTTPException(status_code=503, detail="Public contact research is not configured on the server.") from exc
    except (OpenAIRequestError, InvalidOpenAIJSONError) as exc:
        raise HTTPException(status_code=502, detail="Public contact research failed. Please try again.") from exc
    researched_at = datetime.now(UTC)
    result_data = result.model_dump(mode="json")
    snapshot = ResearchContactSnapshot(lead_id=lead.id, result=result_data, researched_at=researched_at)
    db.add(snapshot)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        return {"result": result_data, "researched_at": researched_at, "saved": False,
                "save_error": "The contact search completed but could not be saved. Copy any details you need before leaving this page."}
    db.refresh(snapshot)
    # SQLite stores timezone-aware datetimes without the offset; return the
    # original UTC timestamp instead of presenting it as local wall time.
    return {"result": snapshot.result, "researched_at": researched_at, "saved": True, "save_error": None}


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, update: LeadUpdate, db: Session = Depends(get_db)) -> dict:
    lead = db.get(ResearchLead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Research lead not found")
    previous = lead.status
    if update.status is not None:
        lead.status = update.status
    if update.notes is not None:
        lead.notes = update.notes
    lead.updated_at = datetime.now(UTC)
    db.add(ResearchLeadFeedback(lead_id=lead.id, previous_status=previous, status=lead.status,
                                feedback=update.feedback, notes=lead.notes))
    db.commit()
    db.refresh(lead)
    return lead_dict(db, lead)
