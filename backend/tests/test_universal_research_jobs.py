import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.universal_research import UniversalResearchRequest
from app.services.universal_research_jobs import JobQueueFull, ResearchJobManager


def wait_for(manager, job_id, state):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = manager.get(job_id)
        if job and job["status"] == state:
            return job
        threading.Event().wait(0.01)
    pytest.fail(f"Job did not reach {state}")


def test_jobs_are_bounded_and_report_progress_without_blocking():
    entered, release = threading.Event(), threading.Event()
    def research(request, *, progress_callback):
        progress_callback({"phase":"searching", "planned":3, "completed":1, "failed":0})
        entered.set()
        assert release.wait(3)
        return {"brief":request.brief, "opportunities":[]}
    manager = ResearchJobManager(research, workers=1, capacity=2)
    try:
        request = UniversalResearchRequest(brief="Find maintenance opportunities in Wales", max_searches=3)
        first = manager.submit(request)
        assert entered.wait(3)
        running = manager.get(first["job_id"])
        assert running["status"] == "running"
        assert running["progress"]["phase"] == "searching"
        assert running["progress"]["completed"] == 1
        second = manager.submit(request)
        assert second["status"] == "queued"
        with pytest.raises(JobQueueFull):
            manager.submit(request)
        release.set()
        completed = wait_for(manager, second["job_id"], "completed")
        assert completed["result"]["brief"] == request.brief
        assert completed["finished_at"] is not None
        assert completed["error"] is None
    finally:
        release.set()
        manager.shutdown()


def test_failure_is_safe_and_results_expire():
    def broken(request, *, progress_callback):
        raise RuntimeError("secret-sensitive-provider-error")
    manager = ResearchJobManager(broken, workers=1, capacity=1, ttl_seconds=0.05)
    try:
        job = manager.submit(UniversalResearchRequest(brief="Find hospital maintenance leads"))
        failed = wait_for(manager, job["job_id"], "failed")
        assert failed["result"] is None
        assert failed["error"] == "Research could not be completed. Please retry."
        assert "secret" not in str(failed)
        threading.Event().wait(0.07)
        assert manager.get(job["job_id"]) is None
    finally:
        manager.shutdown()


def test_router_submits_and_polls_and_not_found_is_explicit(monkeypatch):
    import app.routers.universal_research_jobs as routes
    entered, release = threading.Event(), threading.Event()
    def research(request, *, progress_callback):
        entered.set()
        assert release.wait(3)
        return {"brief":request.brief, "opportunities":[]}
    manager = ResearchJobManager(research, workers=1, capacity=1)
    monkeypatch.setattr(routes, "job_manager", manager)
    app = FastAPI()
    app.include_router(routes.router)
    try:
        with TestClient(app) as client:
            assert client.post("/api/intelligence/universal-research-jobs", json={"brief":"short"}).status_code == 422
            started = client.post("/api/intelligence/universal-research-jobs", json={"brief":"Find fire maintenance leads", "max_searches":2})
            assert started.status_code == 202
            job_id = started.json()["job_id"]
            assert entered.wait(3)
            assert client.get(f"/api/intelligence/universal-research-jobs/{job_id}").json()["status"] == "running"
            assert client.post("/api/intelligence/universal-research-jobs", json={"brief":"Find a second research lead"}).status_code == 429
            assert client.get("/api/intelligence/universal-research-jobs/missing").status_code == 404
            release.set()
            wait_for(manager, job_id, "completed")
            response = client.get(f"/api/intelligence/universal-research-jobs/{job_id}")
            assert response.json()["result"]["brief"] == "Find fire maintenance leads"
    finally:
        release.set()
        manager.shutdown()
