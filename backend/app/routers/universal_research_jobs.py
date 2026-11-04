"""Start and poll bounded research jobs; completed results are saved."""
from fastapi import APIRouter, HTTPException, status

from app.intelligence.universal_research import research_universal
from app.schemas.universal_research import UniversalResearchRequest
from app.services.universal_research_jobs import JobQueueFull, ResearchJobManager
from app.services.research_dossiers import persist_completed_research


router = APIRouter(prefix="/api/intelligence/universal-research-jobs", tags=["intelligence"])
job_manager = ResearchJobManager(research_universal, on_success=persist_completed_research)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_universal_research(request: UniversalResearchRequest) -> dict:
    try:
        return job_manager.submit(request)
    except JobQueueFull as exc:
        raise HTTPException(status_code=429, detail="Research capacity is full. Please retry shortly.") from exc


@router.get("/{job_id}")
def read_universal_research(job_id: str) -> dict:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Research job not found; it may have expired or the server may have restarted.")
    return job
