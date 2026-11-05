"""Follow-up research is bounded, durable and separate from the original lead."""
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models.research_dossier import ResearchInvestigation, ResearchLead
from app.routers.research_investigations import router
from app.services.research_dossiers import save_run
from app.services.universal_research_jobs import JobQueueFull

RESULT = {"brief":"Find opportunities", "model":"test-model", "searches":[],
  "observations":[
    {"id":"a", "source_url":"https://example.org/report?token=private#section", "source_title":"Report", "published_date":"2025-01-01", "fact":"Example Ltd published an estate report.", "origin":"web_search"},
    {"id":"b", "source_url":"https://example.org/import", "source_title":"Imported", "published_date":"", "fact":"Sensitive imported text", "origin":"evidence_inbox"}],
  "opportunities":[{"organisation":"Example Ltd", "location":"Bristol", "headline":"Review maintenance", "thesis":"A hypothesis to verify", "supporting_observation_ids":["a","b"], "counter_observation_ids":[], "unknowns":["Supplier"], "contact_name":"", "contact_role":"Facilities manager", "contact_observation_ids":[], "engagement":"Ask about arrangements", "verification_action":"Confirm scope"}], "limitations":[]}


class FakeJobs:
    def __init__(self):
        self.jobs = {}
        self.requests = []
        self.full = False
    def submit(self, request):
        if self.full:
            raise JobQueueFull()
        self.requests.append(request)
        identifier = f"follow-{len(self.requests)}"
        job = {"job_id":identifier, "status":"queued", "progress":{"phase":"queued"}, "error":None, "save_error":None}
        self.jobs[identifier] = job
        return job
    def get(self, job_id):
        return self.jobs.get(job_id)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    import app.routers.universal_research_jobs as jobs
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        saved = save_run(db, "parent", RESULT, datetime.now(UTC))
        lead_id = db.scalar(select(ResearchLead.id).where(ResearchLead.run_id == saved.id))
        lead = db.get(ResearchLead, lead_id)
        lead.notes = "Confidential salesperson note"
        db.commit()
    fake = FakeJobs()
    monkeypatch.setattr(jobs, "job_manager", fake)
    app = FastAPI()
    app.include_router(router)
    def db_override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as client:
        yield client, fake, sessions, lead_id
    engine.dispose()


def test_followup_uses_bounded_context_and_keeps_history_after_restart(setup):
    client, jobs, sessions, lead_id = setup
    question = "Who manages fire maintenance and what changed recently?"
    response = client.post(f"/api/research-dossiers/leads/{lead_id}/investigations", json={"question":question, "max_searches":3})
    assert response.status_code == 202
    created = response.json()
    assert created["question"] == question and created["status"] == "queued"
    request = jobs.requests[0]
    assert request.max_searches == 3 and request.include_inbox is False
    assert question in request.brief and "Example Ltd" in request.brief
    assert "unverified" in request.brief and "independently" in request.brief
    assert "Confidential salesperson note" not in request.brief
    assert "Sensitive imported text" not in request.brief and "token=private" not in request.brief
    assert len(request.brief) <= 1200
    jobs.jobs[created["job_id"]]["status"] = "running"
    assert client.get(f"/api/research-dossiers/investigations/{created['id']}").json()["status"] == "running"
    with sessions() as db:
        saved = save_run(db, created["job_id"], RESULT, datetime.now(UTC))
        saved_id = saved.id
    jobs.jobs.clear()  # process restarted or in-memory job expired
    detail = client.get(f"/api/research-dossiers/investigations/{created['id']}").json()
    assert detail["status"] == "completed" and detail["saved_run_id"] == saved_id
    assert client.get(f"/api/research-dossiers/leads/{lead_id}/investigations").json()["total"] == 1
    followup = client.post(f"/api/research-dossiers/leads/{lead_id}/investigations", json={"question":"What changed since that finding?"})
    assert followup.status_code == 202
    assert "previous_followup_observations_unverified" in jobs.requests[-1].brief
    assert "Example Ltd published an estate report." in jobs.requests[-1].brief
    assert "token=private" not in jobs.requests[-1].brief
    with sessions() as db:
        assert db.get(ResearchLead, lead_id).notes == "Confidential salesperson note"
        assert db.get(ResearchLead, lead_id).opportunity == RESULT["opportunities"][0]


def test_later_question_retains_recent_questions_and_unsaved_result_is_honest(setup):
    client, jobs, _, lead_id = setup
    path = f"/api/research-dossiers/leads/{lead_id}/investigations"
    first = client.post(path, json={"question":"What are the current maintenance arrangements?"}).json()
    second = client.post(path, json={"question":"What counter-evidence exists?"}).json()
    assert "What are the current maintenance arrangements?" in jobs.requests[-1].brief
    jobs.jobs[second["job_id"]].update(status="completed", save_error="Could not save this research.")
    result = client.get(f"/api/research-dossiers/investigations/{second['id']}").json()
    assert result["status"] == "completed_unsaved" and result["saved_run_id"] is None
    jobs.jobs.pop(first["job_id"])
    assert client.get(f"/api/research-dossiers/investigations/{first['id']}").json()["status"] == "interrupted"


def test_validates_limits_and_queue_before_saving(setup):
    client, jobs, sessions, lead_id = setup
    path = f"/api/research-dossiers/leads/{lead_id}/investigations"
    for invalid in ({"question":"short"}, {"question":"x" * 601}, {"question":"A suitable question", "max_searches":13}, {"question":"A suitable question", "extra":True}):
        assert client.post(path, json=invalid).status_code == 422
    jobs.full = True
    assert client.post(path, json={"question":"What should be checked next?"}).status_code == 429
    assert client.post("/api/research-dossiers/leads/999/investigations", json={"question":"What should be checked next?"}).status_code == 404
    assert client.get("/api/research-dossiers/investigations/999").status_code == 404
    with sessions() as db:
        assert db.scalars(select(ResearchInvestigation)).all() == []


def test_long_question_is_preserved_and_brief_stays_within_provider_limit(setup):
    client, jobs, _, lead_id = setup
    question = "Ask about " + "\\" * 590
    response = client.post(f"/api/research-dossiers/leads/{lead_id}/investigations", json={"question":question})
    assert response.status_code == 202
    assert question in jobs.requests[0].brief and len(jobs.requests[0].brief) <= 1200
