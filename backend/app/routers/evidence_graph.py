"""Inspect the evidence links already present in one saved research lead."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.intelligence.evidence_graph import build_evidence_graph
from app.models.research_dossier import ResearchLead, SavedResearchRun


router = APIRouter(prefix="/api/research-dossiers", tags=["research evidence"])


@router.get("/leads/{lead_id}/evidence-map")
def evidence_map(lead_id: int, db: Session = Depends(get_db)) -> dict:
    lead = db.get(ResearchLead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Research lead not found")
    run = db.get(SavedResearchRun, lead.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research result not found")
    result = run.result if isinstance(run.result, dict) else {}
    return build_evidence_graph(lead.id, lead.opportunity, result.get("observations", []))
