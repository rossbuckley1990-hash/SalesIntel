from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models.evidence_observation import EvidenceObservation
from app.routers.research_dossiers import router
from app.services.universal_research_jobs import ResearchJobManager


RESULT = {
    "brief": "Find fire maintenance opportunities", "model": "test-model", "searches": [],
    "observations": [
        {"id": "a", "source_url": "https://example.org/report", "source_title": "Report", "published_date": "2025-01-01", "fact": "A public observation"},
        {"id": "b", "source_url": "https://example.org/counter", "source_title": "Counterpoint", "published_date": "2025-02-01", "fact": "A contradictory observation"},
    ],
    "opportunities": [{"organisation": "Example Ltd", "location": "Bristol", "headline": "Review maintenance",
                       "thesis": "A hypothesis", "supporting_observation_ids": ["a"], "counter_observation_ids": ["b"],
                       "unknowns": ["Incumbent"], "contact_name": "", "contact_role": "Facilities manager",
                       "contact_observation_ids": [], "engagement": "Ask about arrangements", "verification_action": "Confirm need"}],
    "limitations": ["Sources require verification"],
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.routers.universal_research_jobs as jobs
    engine = create_engine(f"sqlite:///{tmp_path / 'dossiers.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(router)
    def db_override():
        with session() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    job = {"job_id": "job-1", "status": "completed", "result": RESULT, "finished_at": datetime.now(UTC).isoformat()}
    monkeypatch.setattr(jobs, "job_manager", SimpleNamespace(get=lambda job_id: job if job_id == "job-1" else None))
    with TestClient(app) as test_client:
        test_client.db_factory = session
        yield test_client
    engine.dispose()


def test_save_review_and_retry_preserve_source_and_feedback(client):
    base = "/api/research-dossiers"
    assert client.post(f"{base}/from-job/missing").status_code == 404
    run = client.post(f"{base}/from-job/job-1").json()
    assert run["brief"] == RESULT["brief"]
    assert run["result"] == RESULT
    lead_id = run["leads"][0]["id"]
    lead = client.patch(f"{base}/leads/{lead_id}", json={"status": "investigate", "notes": "Confirm incumbent", "feedback": "needs_research"}).json()
    assert lead["observations"] == RESULT["observations"]
    assert lead["opportunity"]["counter_observation_ids"] == ["b"]
    assert lead["feedback"][0]["previous_status"] == "new"
    assert lead["feedback"][0]["notes"] == "Confirm incumbent"
    assert client.post(f"{base}/from-job/job-1").json()["leads"][0]["status"] == "investigate"
    assert client.get(f"{base}/runs").json()["total"] == 1
    assert client.get(f"{base}/leads?status=investigate").json()["items"][0] == lead
    assert client.get(f"{base}/leads/{lead_id}").json() == lead
    assert client.patch(f"{base}/leads/{lead_id}", json={"status": "invalid"}).status_code == 422
    assert client.patch(f"{base}/leads/{lead_id}", json={}).status_code == 422
    assert client.get(f"{base}/leads/999").status_code == 404


def test_search_matches_saved_leads_across_pages_and_treats_wildcards_as_text(client):
    base = "/api/research-dossiers"
    client.post(f"{base}/from-job/job-1")
    assert client.get(f"{base}/leads", params={"q":"bRiStOl"}).json()["total"] == 1
    assert client.get(f"{base}/leads", params={"q":"Example", "status":"new"}).json()["total"] == 1
    assert client.get(f"{base}/leads", params={"q":"Example", "status":"qualified"}).json()["total"] == 0
    assert client.get(f"{base}/leads", params={"q":"%"}).json()["total"] == 0
    assert client.get(f"{base}/leads", params={"q":"a" * 121}).status_code == 422


def test_salesperson_can_choose_a_followup_without_creating_a_crm_opportunity(client):
    from sqlalchemy import select
    from app.models.opportunity import Opportunity
    base = "/api/research-dossiers"
    lead_id = client.post(f"{base}/from-job/job-1").json()["leads"][0]["id"]
    response = client.post(f"{base}/leads/{lead_id}/actions", json={"text":"Confirm the current service owner", "due_date":"2026-11-12"})
    assert response.status_code == 200
    action = response.json()
    assert action["status"] == "open" and action["due_date"] == "2026-11-12"
    assert action["organisation"] == "Example Ltd" and action["lead_id"] == lead_id
    assert client.get(f"{base}/actions?status=open").json()["total"] == 1
    assert client.get(f"{base}/leads/{lead_id}").json()["actions"][0]["id"] == action["id"]
    assert client.patch(f"{base}/actions/{action['id']}", json={"status":"completed"}).json()["status"] == "completed"
    assert client.get(f"{base}/actions?status=open").json()["total"] == 0
    assert client.patch(f"{base}/actions/{action['id']}", json={"status":"invented"}).status_code == 422
    assert client.post(f"{base}/leads/999/actions", json={"text":"Confirm the owner"}).status_code == 404
    with client.db_factory() as db:
        assert db.scalars(select(Opportunity)).all() == []


def test_followup_can_be_edited_rescheduled_deferred_and_restored(client):
    base = "/api/research-dossiers"
    lead_id = client.post(f"{base}/from-job/job-1").json()["leads"][0]["id"]
    original = client.post(f"{base}/leads/{lead_id}/actions", json={
        "text": "Confirm service owner", "due_date": "2026-12-12"}).json()
    path = f"{base}/actions/{original['id']}"

    edited = client.patch(path, json={"text": "  Ask the facilities team about current arrangements  ",
                                      "due_date": "2026-11-12"}).json()
    assert edited["text"] == "Ask the facilities team about current arrangements"
    assert edited["due_date"] == "2026-11-12" and edited["status"] == "open"
    assert client.get(f"{base}/leads/{lead_id}").json()["actions"][0]["text"] == edited["text"]
    deferred = client.patch(path, json={"status": "deferred", "due_date": None}).json()
    assert deferred["status"] == "deferred" and deferred["due_date"] is None
    assert client.get(f"{base}/actions", params={"status": "open"}).json()["total"] == 0
    assert client.patch(path, json={"status": "open"}).json()["status"] == "open"

    for invalid in ({}, {"status": None}, {"text": None}, {"text": "   "},
                    {"text": "x" * 1201}, {"due_date": "tomorrow"}, {"other": "x"}):
        assert client.patch(path, json=invalid).status_code == 422
    assert client.patch(f"{base}/actions/999", json={"text": "An action"}).status_code == 404


def test_open_followups_are_ordered_by_due_date_without_inventing_a_date(client):
    base = "/api/research-dossiers"
    lead_id = client.post(f"{base}/from-job/job-1").json()["leads"][0]["id"]
    def create(text, due_date=None):
        return client.post(f"{base}/leads/{lead_id}/actions", json={"text": text, "due_date": due_date}).json()
    undated = create("An undated follow-up")
    later = create("A later follow-up", "2026-12-12")
    sooner = create("An earlier follow-up", "2026-11-12")
    page = client.get(f"{base}/actions", params={"status": "open", "limit": 2}).json()
    assert page["total"] == 3
    assert [item["id"] for item in page["items"]] == [sooner["id"], later["id"]]
    assert client.get(f"{base}/actions", params={"status": "open", "offset": 2}).json()["items"][0]["id"] == undated["id"]


def test_job_completion_persists_and_save_failure_keeps_result():
    seen = []
    def research(_request, *, progress_callback):
        return RESULT
    def on_success(job_id, result, completed):
        seen.append((job_id, result, completed))
        return 42
    manager = ResearchJobManager(research, workers=1, capacity=1, on_success=on_success)
    try:
        job_id = manager.submit(None)["job_id"]
        manager.shutdown()


        finished = manager.get(job_id)
        assert finished["status"] == "completed" and finished["saved_run_id"] == 42
        assert seen[0][1] == RESULT
    finally:
        manager.shutdown()

    def fail(*args):
        raise RuntimeError("private database details")
    manager = ResearchJobManager(research, workers=1, capacity=1, on_success=fail)
    try:
        job_id = manager.submit(None)["job_id"]
        manager.shutdown()
        finished = manager.get(job_id)
        assert finished["status"] == "completed" and finished["result"] == RESULT
        assert finished["save_error"] and "private" not in finished["save_error"]
    finally:
        manager.shutdown()

def test_related_evidence_requires_exact_name_and_keeps_site_and_provenance(client):
    with client.db_factory() as db:
        for i, name in enumerate([" EXAMPLE LTD ", "Example Ltd West", "Different Ltd"]):
            db.add(EvidenceObservation(fingerprint=str(i) * 64, organisation_id=f"test:{i}",
                organisation_name=name, site=f"Site {i}", category="maintenance",
                observed_statement="A public observation", source_title="Public report",
                source_reference="report-1", source_url="https://example.org/report",
                published_at=date(2025, 1, 1), retrieved_at=datetime.now(UTC)))
        db.commit()
    run = client.post("/api/research-dossiers/from-job/job-1").json()
    lead = client.get(f"/api/research-dossiers/leads/{run['leads'][0]['id']}").json()
    assert len(lead["related_observations"]) == 1
    match = lead["related_observations"][0]
    assert match["organisation_id"] == "test:0" and match["site"] == "Site 0"
    assert match["source_url"] == "https://example.org/report" and match["published_at"] == "2025-01-01"
    assert "do not establish demand" in lead["related_observations_note"]


def test_completed_job_is_saved_to_database_and_survives_manager_shutdown(tmp_path, monkeypatch):
    import app.db as db_module
    from app.services.research_dossiers import persist_completed_research
    from app.models.research_dossier import SavedResearchRun

    engine = create_engine(f"sqlite:///{tmp_path / 'auto-save.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(db_module, "SessionLocal", sessions)
    manager = ResearchJobManager(lambda request, progress_callback: RESULT,
                                 workers=1, capacity=1, on_success=persist_completed_research)
    job_id = manager.submit(None)["job_id"]
    manager.shutdown()
    assert manager.get(job_id)["saved_run_id"] is not None
    with sessions() as db:
        run = db.get(SavedResearchRun, manager.get(job_id)["saved_run_id"])
        assert run.job_id == job_id and run.result == RESULT
    engine.dispose()


def test_contact_research_persists_sourced_candidate_and_does_not_repeat_on_read(client, monkeypatch):
    from app.schemas.public_contacts import PublicContactResult
    from app.routers import research_dossiers
    calls = []
    def research(request):
        calls.append(request)
        return PublicContactResult(organisation=request.organisation, contacts=[{
            "name": "", "role": "", "kind": "email", "value": "office@example.org",
            "source_url": "https://example.org/contact", "source_title": "Contact", "source_date": "2025",
            "evidence_quote": "Email office@example.org"}], limitations=["Independently confirm this candidate."])
    monkeypatch.setattr(research_dossiers, "research_public_contacts", research)
    lead_id = client.post("/api/research-dossiers/from-job/job-1").json()["leads"][0]["id"]
    path = f"/api/research-dossiers/leads/{lead_id}"
    assert client.get(path).json()["contact_research"] is None
    response = client.post(f"{path}/contact-research").json()
    assert response["saved"] is True and response["researched_at"]
    assert calls[0].organisation == "Example Ltd" and calls[0].contact_role == "Facilities manager"
    snapshot = client.get(path).json()["contact_research"]
    assert snapshot["result"]["contacts"][0]["source_url"] == "https://example.org/contact"
    assert snapshot["result"]["limitations"] == ["Independently confirm this candidate."]
    assert snapshot["researched_at"] and len(calls) == 1
    assert client.post("/api/research-dossiers/leads/999/contact-research").status_code == 404


def test_contact_lookup_returns_result_even_when_saving_fails(client, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    from app.routers import research_dossiers
    from app.schemas.public_contacts import PublicContactResult
    lead_id = client.post("/api/research-dossiers/from-job/job-1").json()["leads"][0]["id"]
    monkeypatch.setattr(research_dossiers, "research_public_contacts", lambda request: PublicContactResult(
        organisation=request.organisation, contacts=[], limitations=["Please verify."]))
    monkeypatch.setattr(Session, "commit", lambda self: (_ for _ in ()).throw(SQLAlchemyError("private error")))
    response = client.post(f"/api/research-dossiers/leads/{lead_id}/contact-research")
    assert response.status_code == 200
    assert response.json()["saved"] is False
    assert response.json()["result"]["limitations"] == ["Please verify."]
    assert "private" not in response.json()["save_error"]
