import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_db
from app.main import create_app
from app.models.prospect import Prospect, ProspectSearch
from app.services import prospect_research as pr

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)
NEWS = "https://www.example-news.co.uk/acme-opens-new-distribution-centre"
SITE = "https://www.acme-logistics.co.uk/contact"


def prospect(**over):
    base = {
        "name": "Acme Logistics Ltd", "website": "https://www.acme-logistics.co.uk", "sector": "Logistics", "location": "Daventry",
        "company_number": "", "size": "", "headline": "New 400,000 sq ft site opening next autumn.", "summary": "S",
        "signals": [{"type": "new_site", "title": "New DC", "detail": "d", "date": "2026-09", "basis": "stated", "direction": "supports", "source_url": NEWS},
                    {"type": "incumbent_poor_performance", "title": "Made up", "detail": "d", "date": "", "basis": "stated", "direction": "supports", "source_url": "https://invented.example/x"}],
        "timing_clues": [{"kind": "site_opening", "date": "2027-09-01", "detail": "opens", "basis": "stated", "system_family": "", "source_url": NEWS}],
        "incumbent": {"name": "", "detail": "", "basis": "unknown", "source_url": ""}, "competitors": [],
        "people": [{"name": "Jane Smith", "role": "Head of Property", "influence": "decision_maker", "why": "w", "source_url": NEWS,
                    "quote": "said Jane Smith, Head of Property at Acme"},
                   {"name": "John Doe", "role": "COO", "influence": "influencer", "why": "w", "source_url": NEWS, "quote": "the chief operating officer said"}],
        "contact_routes": [{"kind": "email", "value": "facilities@acme-logistics.co.uk", "label": "Facilities", "source_url": SITE, "quote": "Email facilities@acme-logistics.co.uk"},
                           {"kind": "email", "value": "jane.smith@acme-logistics.co.uk", "label": "Guessed", "source_url": SITE, "quote": "Contact our team"},
                           {"kind": "email", "value": "jane@gmail.com", "label": "Personal", "source_url": SITE, "quote": "jane@gmail.com"},
                           {"kind": "phone", "value": "01327 555 0100", "label": "Switchboard", "source_url": SITE, "quote": "Call 01327 555 0100"}],
        "approach": {"angle": "a", "opening_line": "o", "offer": "f", "questions": []}, "services": ["cctv", "fire_alarm"], "unknowns": [],
    }
    return {**base, **over}


def fake(calls, prospects):
    def post(payload):
        calls.append(payload)
        if "tools" in payload:
            return {"stop_reason": "end_turn", "content": [
                {"type": "web_search_tool_result", "content": [{"type": "web_search_result", "url": NEWS, "title": "News"}, {"type": "web_search_result", "url": SITE, "title": "Contact"}]},
                {"type": "text", "text": "Acme is opening a site.", "citations": [{"url": NEWS, "title": "News", "cited_text": "opening"}]}]}
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps({"prospects": prospects})}]}
    return post


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_clean_keeps_only_sourced_people_and_verbatim_business_contacts():
    item = pr.clean(prospect(), {NEWS: "News", SITE: "Contact"})
    assert [p["name"] for p in item["people"]] == ["Jane Smith"]
    assert [c["value"] for c in item["contact_routes"]] == ["facilities@acme-logistics.co.uk", "01327 555 0100"]
    assert item["signals"][1]["source_url"] == "" and item["signals"][1]["basis"] == "inferred"
    assert item["checks"] == {"people": 1, "contact_routes": 2, "links": 1}


def test_search_saves_prospects_with_inferred_timing_and_dedupes(db):
    calls = []
    search = ProspectSearch(query="logistics sites in the Midlands", mode="discover", status="running", model="", prospect_ids=[], sources_reviewed=0, created_at=NOW)
    db.add(search)
    db.commit()
    pr.run_search(db, search, post=fake(calls, [prospect(), prospect(name="ACME Logistics Limited")]), settings=Settings(anthropic_model="claude-opus-5-5"), now=NOW)
    assert search.status == "complete" and search.sources_reviewed == 2 and len(set(search.prospect_ids)) == 1
    assert calls[0]["tools"][0]["type"] == "web_search_20260209" and "output_config" in calls[1]
    assert "PSTN" in calls[0]["messages"][0]["content"]
    shown = pr.view(db.get(Prospect, search.prospect_ids[0]), today=NOW.date())
    assert shown["timing"]["phase"] == "engage_now" and shown["timing"]["light"] == "green"
    assert shown["signal_groups"] == ["Growth", "Incumbent"]


def test_failed_research_is_recorded_not_raised(db):
    search = ProspectSearch(query="x", mode="company", status="running", model="", prospect_ids=[], sources_reviewed=0, created_at=NOW)
    db.add(search)
    db.commit()
    pr.run_search(db, search, settings=Settings(anthropic_api_key=None), now=NOW)
    assert search.status == "failed" and "ANTHROPIC_API_KEY" in search.error


def test_api_runs_search_lists_and_adds_to_pipeline(db, monkeypatch):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(pr, "_background", lambda search_id: pr.run_search(db, db.get(ProspectSearch, search_id),
                        post=fake([], [prospect()]), settings=Settings(anthropic_model="m"), now=NOW))
    client = TestClient(app)
    started = client.post("/api/prospects/searches", json={"query": "Acme Logistics, Daventry", "mode": "company"}).json()
    assert client.get(f"/api/prospects/searches/{started['id']}").json()["status"] == "complete"
    items = client.get("/api/prospects").json()["items"]
    assert len(items) == 1 and items[0]["name"] == "Acme Logistics Ltd"
    added = client.post(f"/api/prospects/{items[0]['id']}/promote").json()
    again = client.post(f"/api/prospects/{items[0]['id']}/promote").json()
    assert added["created"] is True and again == {"opportunity_id": added["opportunity_id"], "created": False}
    assert client.get("/api/prospects", params={"status": "pipeline"}).json()["items"][0]["opportunity_id"] == added["opportunity_id"]
    assert client.patch(f"/api/prospects/{items[0]['id']}", json={"status": "dismissed"}).json()["status"] == "dismissed"
    assert client.get("/api/prospects").json()["items"] == []
    assert len(client.get("/api/prospects/signals").json()["signals"]) == len(pr.SIGNALS)


def test_deepening_updates_the_same_prospect_even_under_a_new_name(db, monkeypatch):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    names = iter(["Acme Logistics Ltd", "Acme Logistics UK – Daventry DC"])
    monkeypatch.setattr(pr, "_background", lambda search_id: pr.run_search(db, db.get(ProspectSearch, search_id),
                        post=fake([], [prospect(name=next(names))]), settings=Settings(anthropic_model="m"), now=NOW))
    client = TestClient(app)
    client.post("/api/prospects/searches", json={"query": "Acme", "mode": "company"})
    first = client.get("/api/prospects").json()["items"][0]["id"]
    deeper = client.post("/api/prospects/searches", json={"query": "Acme, Daventry", "mode": "company", "prospect_id": first}).json()
    assert deeper["target_prospect_id"] == first
    items = client.get("/api/prospects").json()["items"]
    assert [x["id"] for x in items] == [first] and items[0]["name"] == "Acme Logistics Ltd" and items[0]["search_id"] == deeper["id"]
    assert client.post("/api/prospects/searches", json={"query": "x y z", "prospect_id": 999}).status_code == 404
