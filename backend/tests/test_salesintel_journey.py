"""SalesIntel 2.0 acceptance tests, run on synthetic records with no paid model calls.

A discover to contact, B continuity across a restart, C deduplication, D relevance,
E no fabricated facts, G operational safety, H conversion to a deal and handover.
"""
from datetime import UTC, date, datetime, timedelta
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import Base, get_db
from app.intelligence.renewal_radar import classify
from app.main import create_app
from app.models import Opportunity
from app.models.crm import Account, AccountLink, FunnelEvent
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.models.prospect import Prospect
from app.routers import salesintel as si_router
from app.services.opportunity_dossier import DossierUnavailable, create_dossier

NOW = datetime.now(UTC)
END = (NOW + timedelta(days=200)).date().isoformat()
NOTICE = "https://www.contractsfinder.service.gov.uk/Notice/example-orbit"
NEWS = "https://news.example.co.uk/orbit-new-hub"


def suggestion(customer="ORBIT GROUP LIMITED", title="Service and maintenance of fire alarm systems", supplier="Example Fire Ltd", value=None):
    return {"kind": "possible_renewal_window", "fit_reason": "title names both the system and the service", "unknowns": [], "category": "pre_tender", "category_label": "Pre-tender opportunity", "customer": customer, "title": title, "supplier": supplier,
            "timing": END, "timing_basis": "published award contract period", "end_estimated": False, "latest_end": None, "nation": "England", "fit": "core",
            "value": value or {"type": "unknown", "published_total": None, "estimated_annualised": None, "framework_ceiling": None, "basis": "No value is published.", "scope_note": ""},
            "priority": {"tier": 1, "reasons": ["Core fit"]}, "counter_evidence": [], "next_actions": ["Investigate"], "next_action": "Investigate", "extension": "",
            "link": {"confidence": "exact", "records": 1, "sources": ["Contracts Finder"]},
            "brief": {"why_it_matters": "Title names both the system and the service.", "missing_information": ["Procurement route."], "contract_lifecycle": "", "procurement_route": ""},
            "evidence": [{"source_revision_id": 1, "source_url": NOTICE, "source": "Contracts Finder", "record_key": "example-orbit", "published_at": "2023-05-01"}]}


def add_mo(db, **kwargs):
    item = MarketOpportunity(dedup_key=f"renewal:{kwargs.get('customer', 'orbit')}:{kwargs.get('title', 'x')}", first_seen=NOW, last_evaluated=NOW)
    db.add(item)
    db.flush()
    version = MarketOpportunityRevision(opportunity_id=item.id, fingerprint="f", result=suggestion(**kwargs), created_at=NOW)
    db.add(version)
    db.flush()
    item.current_revision_id = version.id
    db.commit()
    return item.id


def add_prospect(db, name="Orbit Group Ltd", company_number="", people=True):
    data = {"website": "https://www.orbit.example.co.uk", "sector": "Housing", "location": "Coventry", "company_number": company_number, "size": "",
            "headline": "Opening a new regional hub in 2027.", "summary": "S",
            "signals": [{"type": "new_site", "title": "New regional hub announced", "detail": "d", "date": "2026-09", "basis": "stated", "direction": "supports", "source_url": NEWS}],
            "timing_clues": [{"kind": "site_opening", "date": "2027-06-01", "detail": "Hub opens", "basis": "stated", "system_family": "", "source_url": NEWS}],
            "incumbent": {"name": "", "detail": "", "basis": "unknown", "source_url": ""}, "competitors": [],
            "people": [{"name": "Sam Example", "role": "Head of Property", "influence": "decision_maker", "why": "Leads the hub", "source_url": NEWS, "quote": "said Sam Example, Head of Property"}] if people else [],
            "contact_routes": [{"kind": "switchboard", "value": "024 7600 0000", "label": "Switchboard", "source_url": NEWS, "quote": "Call 024 7600 0000"}] if people else [],
            "approach": {"angle": "a", "opening_line": "o", "offer": "f", "questions": []}, "services": ["fire_alarm"], "unknowns": []}
    row = Prospect(dedup_key=name.lower(), name=name, status="new", data=data, created_at=NOW, updated_at=NOW)
    db.add(row)
    db.commit()
    return row.id


@pytest.fixture
def env(tmp_path):
    url = f"sqlite:///{tmp_path / 'salesintel.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    state = {"engine": engine, "url": url}

    def client():
        session = Session(state["engine"])
        app = create_app()
        app.dependency_overrides[get_db] = lambda: session
        return TestClient(app), session
    state["client"] = client
    yield state
    state["engine"].dispose()


def journey_to_logged_contact(c):
    """Discover, open the account, prepare and approve an introduction, log it and schedule a follow-up."""
    lead = next(x for x in c.get("/api/si/discover").json()["items"] if x["type"] == "public")
    assert lead["why_now"].startswith("Published contract with Example Fire Ltd ends") and lead["basis"] == "published"
    linked = c.post(f"/api/si/discover/{lead['key']}/account", json={}).json()
    account_id = linked["account_id"]
    intro = c.post(f"/api/si/accounts/{account_id}/introduction", json={"source_key": lead["key"]}).json()
    assert "Dear [name]," in intro["body"] and any("No contact selected" in g for g in intro["gaps"])
    draft = c.post(f"/api/si/accounts/{account_id}/drafts", json={"subject": intro["subject"], "body": intro["body"], "evidence": intro["evidence"], "gaps": intro["gaps"]}).json()
    assert c.post(f"/api/si/drafts/{draft['id']}/approve").status_code == 422  # placeholders remain
    body = intro["body"].replace("Dear [name],", "Dear Facilities team,").replace("[your name]", "Alex Rep").replace("[your company]", "Regional Fire Ltd")
    c.patch(f"/api/si/drafts/{draft['id']}", json={"body": body})
    assert c.post(f"/api/si/drafts/{draft['id']}/approve").json()["status"] == "approved"
    assert c.post(f"/api/si/drafts/{draft['id']}/log", json={"sent_externally": False}).status_code == 422
    due = (NOW.date() + timedelta(days=3)).isoformat()
    logged = c.post(f"/api/si/drafts/{draft['id']}/log", json={"sent_externally": True, "follow_up": {"title": "Call facilities team", "due_on": due}}).json()
    assert logged["activity"]["kind"] == "email" and logged["task"]["due_on"] == due
    return account_id, lead["key"]


def test_a_discover_to_contact_without_invented_details(env):
    c, db = env["client"]()
    add_mo(db)
    account_id, key = journey_to_logged_contact(c)
    view = c.get(f"/api/si/accounts/{account_id}").json()
    assert view["name"] == "Orbit Group Limited" and view["sources"][0]["key"] == key
    assert view["contacts"] == []  # nothing was invented
    assert not re.search(r"[\w.]+@[\w.]+|\d{4}\s?\d{3}\s?\d{4}", view["drafts"][0]["body"])
    assert [a["kind"] for a in view["activities"]] == ["email"] and view["tasks"][0]["title"] == "Call facilities team"
    assert c.get("/api/si/discover").json()["items"][0]["account_id"] == account_id


def test_b_relationship_survives_a_restart(env):
    c, db = env["client"]()
    add_mo(db)
    account_id, _ = journey_to_logged_contact(c)
    c.post(f"/api/si/accounts/{account_id}/activities", json={"kind": "call", "summary": "Spoke to facilities", "outcome": "interested", "requirements": "Two sites, annual service"})
    db.close()
    env["engine"].dispose()
    env["engine"] = create_engine(env["url"], connect_args={"check_same_thread": False})  # a new process opening the same file
    c2, _ = env["client"]()
    view = c2.get(f"/api/si/accounts/{account_id}").json()
    assert [a["kind"] for a in view["activities"]] == ["call", "email"] and view["activities"][0]["requirements"] == "Two sites, annual service"
    assert view["tasks"][0]["status"] == "open" and view["sources"][0]["evidence"][0]["url"] == NOTICE
    today = c2.get("/api/si/today").json()
    assert any(t["title"] == "Call facilities team" for t in today["upcoming"]) or any(q.get("task_id") for q in today["queue"])


def test_c_same_organisation_in_procurement_and_research_is_one_account(env):
    c, db = env["client"]()
    mo = add_mo(db)
    pr = add_prospect(db)
    other = add_prospect(db, name="Orbit Housing Association")
    a = c.post(f"/api/si/discover/mo:{mo}/account", json={}).json()
    b = c.post(f"/api/si/discover/pr:{pr}/account", json={}).json()
    assert a["account_id"] == b["account_id"] and a["basis"] == "created_from" and b["basis"] == "same_name" and b["confirmed"] is False
    assert db.scalar(select(Account).where(Account.id == a["account_id"])) is not None and len(db.scalars(select(Account)).all()) == 1
    view = c.get(f"/api/si/accounts/{a['account_id']}").json()
    assert {i["basis"] for i in view["identities"]} == {"created_from", "same_name"}
    assert view["sites"] == []  # no site is assumed from a matching name
    suggested = c.get(f"/api/si/accounts/{a['account_id']}/suggestions").json()["items"]
    assert any(s["source"] == f"pr:{other}" for s in suggested)
    assert db.scalar(select(AccountLink).where(AccountLink.entity_type == "prospect", AccountLink.entity_id == other)) is None
    # Different registered numbers are never merged, even with the same name.
    x = add_prospect(db, name="Acme Fire Ltd", company_number="01234567")
    y = add_prospect(db, name="Acme Fire Limited", company_number="07654321")
    assert c.post(f"/api/si/discover/pr:{x}/account", json={}).json()["account_id"] != c.post(f"/api/si/discover/pr:{y}/account", json={}).json()["account_id"]


def test_d_only_fire_and_security_services_are_surfaced():
    unrelated = [("Supply of vehicle alarm and tracking units for fleet vans", "Fit car alarms to council fleet."),
                 ("Legal services for CCTV evidence review", "Solicitors to review footage."),
                 ("Personal alarm and telecare service", "Community alarm service for vulnerable residents."),
                 ("Cyber security penetration testing", "IT security testing."), ("Security printing of ballot papers", "Secure printing.")]
    for title, body in unrelated:
        assert classify({"title": title, "description": body, "suppliers": ["A Ltd"], "start": "2025-01-01", "end": "2028-01-01"})[0] == "exclude", title
    assert classify({"title": "Fire alarm maintenance and servicing", "description": "PPM of fire alarm systems across 12 sites.", "suppliers": ["A Ltd"],
                     "start": "2025-01-01", "end": "2028-01-01"})[0] == "core"


def test_e_unknown_facts_stay_unknown(env):
    c, db = env["client"]()
    add_mo(db, supplier=None)
    pr = add_prospect(db, name="Brightwell Care Ltd", people=False)
    lead = c.post("/api/si/discover/mo:1/account", json={}).json()
    view = c.get(f"/api/si/accounts/{lead['account_id']}").json()
    assert "Contract value (not published)" in view["to_confirm"] and "Who maintains their fire and security systems today" in view["to_confirm"]
    intro = c.post(f"/api/si/accounts/{lead['account_id']}/introduction", json={}).json()
    assert any("Current provider unknown" in g for g in intro["gaps"]) and "Example Fire" not in intro["body"]
    deal = c.post(f"/api/si/accounts/{lead['account_id']}/deals", json={"source_key": "mo:1", "services": ["fire_alarm"], "qualification": {"requirement": "Annual servicing"}}).json()
    assert deal["value_total"] is None and deal["value_basis"] == "unknown"
    quote = c.post(f"/api/si/deals/{deal['id']}/quote", json={"rates": {}}).json()["quote"]
    assert quote["subtotal"] is None and quote["partial_total"] is None and quote["missing"]
    c.put(f"/api/si/deals/{deal['id']}/scope", json={"entries": [{"service": "fire_alarm", "field": "panels", "value": 3, "basis": "estimate"},
                                                                  {"service": "fire_alarm", "field": "devices", "value": 120, "basis": "customer_stated"},
                                                                  {"service": "fire_alarm", "field": "visits_per_year", "value": 2, "basis": "customer_stated"},
                                                                  {"service": "fire_alarm", "field": "panel_make", "value": "Unknown model", "basis": "customer_stated"}]})
    rates = {"fire_alarm.panels": 150, "fire_alarm.devices": 4, "fire_alarm.visits_per_year": 300}
    quote = c.post(f"/api/si/deals/{deal['id']}/quote", json={"rates": rates}).json()["quote"]
    assert quote["subtotal"] == "1530.00" and any("Estimated quantity" in l["warning"] for l in quote["lines"])
    assert c.post(f"/api/si/deals/{deal['id']}/quote/approve", json={"reviewer": "Pat Manager"}).status_code == 422  # estimate must be confirmed
    pr_account = c.post(f"/api/si/discover/pr:{pr}/account", json={}).json()["account_id"]
    assert c.get(f"/api/si/accounts/{pr_account}").json()["contacts"] == []


def test_g_operational_safety(env, monkeypatch):
    c, db = env["client"]()
    add_mo(db)
    add_mo(db, customer="Another Council", title="CCTV maintenance")
    a = c.post("/api/si/discover/mo:1/account", json={}).json()["account_id"]
    b = c.post("/api/si/discover/mo:2/account", json={}).json()["account_id"]
    other = c.post(f"/api/si/accounts/{b}/contacts", json={"name": "Jo Example", "role": "Estates"}).json()
    assert c.post(f"/api/si/accounts/{a}/activities", json={"kind": "call", "summary": "x", "contact_id": other["id"]}).status_code == 404
    blocked = c.post(f"/api/si/accounts/{b}/contacts", json={"role": "Facilities team", "email": "facilities@another.example.gov.uk"}).json()
    c.patch(f"/api/si/contacts/{blocked['id']}", json={"status": "do_not_contact"})
    assert c.post(f"/api/si/accounts/{b}/introduction", json={"contact_id": blocked["id"]}).status_code == 409
    c.post(f"/api/si/accounts/{b}/activities", json={"kind": "note", "summary": "Private to B"})
    assert all(x["summary"] != "Private to B" for x in c.get(f"/api/si/accounts/{a}").json()["activities"])
    assert not [r for r in create_app().routes if "send" in getattr(r, "path", "")]  # there is no send endpoint
    monkeypatch.setattr(si_router, "get_settings", lambda: Settings(app_env="demo"))
    assert c.post("/api/si/discover/research", json={"query": "care homes in Yorkshire"}).status_code == 403
    with pytest.raises(DossierUnavailable):
        create_dossier(db, 1, post=lambda payload: pytest.fail("a paid model call was attempted"), settings=Settings(app_env="demo"))
    events = {e.event for e in db.scalars(select(FunnelEvent))}
    assert "account_created" in events and not any("@" in e for e in events)


def test_h_qualified_opportunity_becomes_a_persistent_deal_through_to_handover(env):
    c, db = env["client"]()
    add_mo(db, value={"type": "published_total", "published_total": 90000, "estimated_annualised": None, "framework_ceiling": None, "basis": "Published", "scope_note": ""})
    account_id, key = journey_to_logged_contact(c)
    c.post(f"/api/si/accounts/{account_id}/activities", json={"kind": "meeting", "summary": "Met estates lead", "outcome": "requirement_captured",
                                                              "requirements": "PPM for 2 sites", "commitments": "Send scope by Friday"})
    assert c.post(f"/api/si/accounts/{account_id}/deals", json={"source_key": key, "qualification": {"requirement": ""}}).status_code == 422
    deal = c.post(f"/api/si/accounts/{account_id}/deals", json={"source_key": key, "services": ["fire_alarm"], "work_type": "ppm",
                                                              "qualification": {"requirement": "PPM for 2 sites", "decision_maker": "Estates lead"}}).json()
    assert deal["origin"]["evidence"][0]["url"] == NOTICE and deal["value_total"] == 90000 and deal["value_basis"] == "published"
    assert {a["kind"] for a in deal["activities"]} == {"email", "meeting"}
    assert db.get(Opportunity, deal["opportunity_id"]).stage == "Qualification"
    assert c.patch(f"/api/si/deals/{deal['id']}", json={"stage": "won", "reason": "Best value"}).status_code == 422  # no approved quote
    entries = [{"service": "fire_alarm", "field": f, "value": v, "basis": "surveyed"} for f, v in (("panels", 2), ("devices", 80), ("visits_per_year", 2), ("panel_make", "Example Panel"))]
    c.put(f"/api/si/deals/{deal['id']}/scope", json={"entries": entries})
    c.post(f"/api/si/deals/{deal['id']}/quote", json={"rates": {"fire_alarm.panels": 120, "fire_alarm.devices": 5, "fire_alarm.visits_per_year": 350}})
    assert c.post(f"/api/si/deals/{deal['id']}/quote/approve", json={"reviewer": "Pat Manager"}).json()["quote"]["status"] == "approved"
    for stage in ("survey", "proposal", "approval"):
        assert c.patch(f"/api/si/deals/{deal['id']}", json={"stage": stage}).json()["stage"] == stage
    won = c.patch(f"/api/si/deals/{deal['id']}", json={"stage": "won", "reason": "Strong survey and local response"}).json()
    assert won["stage"] == "won" and won["handover"]["requirements"] == ["PPM for 2 sites"] and won["handover"]["commitments"] == ["Send scope by Friday"]
    assert won["handover"]["quote"]["subtotal"] == "1340.00" and won["handover"]["origin"]["key"] == key
    assert db.get(Opportunity, deal["opportunity_id"]).stage == "Won"
    reopened = c.get(f"/api/si/deals/{deal['id']}").json()
    assert reopened["origin"]["why_now"] and c.get(f"/api/si/accounts/{account_id}").json()["status"] == "customer"
    assert c.get("/api/si/deals").json()["items"][0]["stage"] == "won"
