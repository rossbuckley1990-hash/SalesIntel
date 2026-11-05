"""Phase 2B acceptance: durable research, spending limits, idempotency, the Contact Navigator and isolation.

Runs the real application in hosted mode (signed tokens, workspaces) on SQLite and PostgreSQL, the
latter under row-level security as an ordinary database role. Research is replayed offline
(app/services/research_replay.py): no network, no credit, and adversarial content included.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import re

import pytest
from sqlalchemy import select, text

from app.models.acquisition import ResearchJob, SpendBudget
from app.models.crm import Account, Contact
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.services import jobs, navigator, spend
from tenancy_support import hosted  # noqa: F401
from test_salesintel_journey import suggestion

NOW = datetime.now(UTC)


def add_notice(db, customer="EXAMPLE HOUSING TRUST LIMITED", record_key="example-synthetic-0001"):
    item = MarketOpportunity(dedup_key=f"n:{record_key}", first_seen=NOW, last_evaluated=NOW)
    db.add(item)
    db.flush()
    result = suggestion(customer=customer, title="Fire alarm servicing and maintenance across 14 sheltered schemes", supplier="Sample Fire Services Ltd")
    result["evidence"] = [{"source_revision_id": 1, "source_url": f"https://www.contractsfinder.service.gov.uk/Notice/{record_key}", "source": "Contracts Finder",
                           "record_key": record_key, "published_at": "2026-04-01"}]
    rev = MarketOpportunityRevision(opportunity_id=item.id, fingerprint="f", result=result, created_at=NOW)
    db.add(rev)
    db.flush()
    item.current_revision_id = rev.id
    db.commit()
    return item.id


def workspace(h, sub, name):
    c = h.client(sub, f"{sub}@{name.split()[0].lower()}.example", sub.title())
    org = c.post("/api/workspaces", json={"name": name}).json()["id"]
    c = h.client(sub, f"{sub}@{name.split()[0].lower()}.example", sub.title(), workspace=org)
    c.put("/api/si/preferences", json={"company_name": name, "services": ["fire_alarm"], "territory": ["Yorkshire", "England"], "sectors": ["Logistics", "Housing"]})
    return c, org


def people_for(c, account, h, **body):
    started = c.post(f"/api/si/accounts/{account}/people-search", json=body)
    assert started.status_code == 200, started.text
    jobs.drain(h.engine)
    return c.get(f"/api/si/accounts/{account}/people").json(), started.json()


# ---------------------------------------------------------------- public opportunity

def test_public_notice_to_a_verified_procurement_route_and_named_lead(hosted):
    h = hosted
    with h.system() as db:
        mo = add_notice(db)
    alice, a_org = workspace(h, "alice", "Alpha Fire Ltd")
    account = alice.post(f"/api/si/discover/mo:{mo}/account", json={}).json()["account_id"]
    view, started = people_for(alice, account, h)
    job = view["job"]
    assert job["status"] == "succeeded" and "only through the route and rules the notice sets out" in job["result"]["message"]
    routes = {(r["route_kind"], r["email"] or r["phone"] or r["url"] or r["name"]): r for r in view["routes"]}
    official = routes[("departmental_email", "procurement@example-housing.example")]
    assert official["role_category"] == "procurement" and "Use only for questions about it" in official["use_restriction"]
    assert routes[("procurement_notice", "https://www.contractsfinder.service.gov.uk/Notice/example-synthetic-0001")]["quality"] == "public_source"
    robin = routes[("none", "Robin Sample")]
    assert robin["role"] == "Head of Assets" and robin["source_url"] == "https://www.example-housing.example/about/our-people"
    assert "Robin Sample, Head of Assets at Example Housing Trust" in robin["source_quote"]
    assert ("departmental_email", "assets@example-housing.example") in routes  # the website was confirmed from a page naming the trust
    assert view["routes"][0]["role_category"] == "procurement"  # a public procurement ranks the buyer's official route first
    # Measured, simulated cost, settled against today's limits.
    assert job["usage"]["web_searches"] == 6 and job["usage"]["simulated"] is True and job["actual_cents"] == 19
    s = alice.get("/api/si/spend").json()
    assert s["workspace"]["spent_cents"] == 19 and s["workspace"]["reserved_cents"] == 0
    # Reused, not regenerated.
    again = alice.post(f"/api/si/accounts/{account}/people-search", json={}).json()
    assert again["id"] == started["id"] and again["reused"] is True and alice.get("/api/si/spend").json()["workspace"]["spent_cents"] == 19
    # A grounded introduction to the official route, then follow-up and outcome.
    intro = alice.post(f"/api/si/accounts/{account}/introduction", json={"contact_id": official["contact_id"], "source_key": f"mo:{mo}"}).json()
    assert "contractsfinder.service.gov.uk" in str(intro["evidence"]) and not re.search(r"[\w.]+@(?!example-housing\.example)[\w.-]+", intro["body"])


# ---------------------------------------------------------------- private opportunity

def test_private_brief_to_sourced_prospect_people_and_no_fabricated_contacts(hosted):
    h = hosted
    alice, a_org = workspace(h, "alice", "Alpha Fire Ltd")
    started = alice.post("/api/si/discover/research", json={"query": "Logistics companies with new warehouses in Yorkshire"})
    assert started.status_code == 200 and started.json()["kind"] == "prospect_search"
    jobs.drain(h.engine)
    job = alice.get(f"/api/si/research-jobs/{started.json()['id']}").json()
    assert job["status"] == "succeeded" and len(job["result"]["prospect_ids"]) == 2
    leads = {x["organisation"]: x for x in alice.get("/api/si/discover", params={"source": "private"}).json()["items"]}
    northgate = leads["Northgate Distribution Ltd"]
    assert northgate["kind"] == "private_signal" and northgate["brief"]["why_now"].startswith("Announced a 400,000 sq ft")
    assert any(k["source_url"] == "https://news.example/northgate-wakefield-hub" and k["date"] == "2026-09-14" for k in northgate["brief"]["known"])
    assert leads["Calder Freight Services"]["kind"] == "unverified_candidate"  # an inferred signal is not promoted
    assert "confirmed" not in northgate["brief"]["why_now"].lower()
    account = alice.post(f"/api/si/discover/{northgate['key']}/account", json={}).json()["account_id"]
    view, _ = people_for(alice, account, h)
    result = view["job"]["result"]
    assert view["job"]["status"] == "partial" and result["message"] == navigator.PARTIAL
    reasons = {r["reason"] for r in result["rejected"]}
    assert "The address does not appear in the source; it is not guessed." in reasons or "The quoted words do not appear on the source page." in reasons
    assert "The page tried to give instructions to the AI, so nothing from it is used." in reasons
    with h.as_workspace(a_org) as db:
        contacts = db.scalars(select(Contact).where(Contact.account_id == account)).all()
        values = {c.email for c in contacts if c.email} | {c.phone for c in contacts if c.phone} | {c.name for c in contacts if c.name}
    assert "sam.patel@northgate-distribution.example" not in values and "md.northgate@gmail.com" not in values and "Alex Northgate" not in values
    assert {"Sam Patel", "0113 496 0000"} <= values
    assert all(c.source_url and c.source_url.startswith("https://") for c in contacts)


def test_roles_only_is_a_reported_partial_result_and_nothing_is_invented(hosted):
    h = hosted
    alice, _ = workspace(h, "alice", "Alpha Fire Ltd")
    quiet = alice.post("/api/si/accounts", json={"name": "Quiet Fields Care Ltd", "website": "https://www.quietfields-care.example"}).json()["account_id"]
    view, _ = people_for(alice, quiet, h)
    assert view["job"]["status"] == "partial" and view["job"]["result"]["message"] == navigator.PARTIAL
    assert [(r["name"], r["route_kind"], r["quality"]) for r in view["routes"]] == [(None, "none", "role_only")]
    unknown = alice.post("/api/si/accounts", json={"name": "Nobody Publishes Ltd"}).json()["account_id"]
    view, _ = people_for(alice, unknown, h)
    assert view["routes"] == [] and view["job"]["result"]["message"] == navigator.NONE_FOUND


# ---------------------------------------------------------------- contact safety

def test_suppression_survives_repeated_research_and_new_sources(hosted, monkeypatch):
    h = hosted
    monkeypatch.setenv("AI_DAILY_LIMIT_CENTS_PER_WORKSPACE", "1000")  # this test researches the same account three times
    from app.config import get_settings
    get_settings.cache_clear()
    with h.system() as db:
        mo = add_notice(db)
    alice, a_org = workspace(h, "alice", "Alpha Fire Ltd")
    account = alice.post(f"/api/si/discover/mo:{mo}/account", json={}).json()["account_id"]
    view, _ = people_for(alice, account, h)
    assets = next(r for r in view["routes"] if r["email"] == "assets@example-housing.example")
    alice.patch(f"/api/si/contacts/{assets['contact_id']}", json={"status": "do_not_contact"})
    view, _ = people_for(alice, account, h, refresh=True)
    assert all(r["email"] != "assets@example-housing.example" for r in view["routes"])  # never offered again
    with h.as_workspace(a_org) as db:
        rows = db.scalars(select(Contact).where(Contact.email == "assets@example-housing.example")).all()
        assert [r.status for r in rows] == ["do_not_contact"]  # one record, still suppressed
        db.delete(rows[0])
        db.commit()
    view, _ = people_for(alice, account, h, refresh=True)  # the record is gone, but the opt-out is remembered by hash
    with h.as_workspace(a_org) as db:
        assert [r.status for r in db.scalars(select(Contact).where(Contact.email == "assets@example-housing.example"))] == ["do_not_contact"]
    added = alice.post(f"/api/si/accounts/{account}/contacts", json={"name": "Assets", "role": "Team", "email": "ASSETS@example-housing.example"}).json()
    assert added["status"] == "do_not_contact"  # typed in by hand: still suppressed
    # Lifting an opt-out is deliberate and audited, and then research respects it.
    with h.as_workspace(a_org) as db:
        current = db.scalar(select(Contact).where(Contact.email == "assets@example-housing.example", Contact.name.is_(None)))
    alice.patch(f"/api/si/contacts/{current.id}", json={"status": "unverified"})
    alice.patch(f"/api/si/contacts/{added['id']}", json={"status": "unverified"})
    view, _ = people_for(alice, account, h, refresh=True)
    assert any(r["email"] == "assets@example-housing.example" for r in view["routes"])
    assert any(e["action"] == "lift_optout" for e in alice.get("/api/workspace/audit").json()["items"])


def test_a_person_who_moved_employer_and_stale_or_conflicting_provider_data_are_flagged(hosted, monkeypatch):
    h = hosted

    class Provider(navigator.EnrichmentProvider):
        name, licence_note = "mockdata", "Test double only."

        def find(self, org, roles):
            return [{"name": "Sam Patel", "role": "Head of Property", "employer": "Northgate Distribution", "email": "s.patel@northgate-distribution.example",
                     "status": "valid", "checked_on": "2024-01-05", "source_url": "https://provider.example/record/1"},
                    {"name": "Sam Patel", "role": "Head of Property", "employer": "Northgate Distribution", "email": "sam.p@northgate-distribution.example",
                     "status": "unknown", "checked_on": "", "source_url": "https://provider.example/record/2"},
                    {"name": "Pat Doe", "role": "Buyer", "employer": "Someone Else plc", "email": "pat@someone-else.example", "status": "valid",
                     "checked_on": "2026-10-01", "source_url": "https://provider.example/record/3"}]
    navigator.register(Provider())
    monkeypatch.setenv("CONTACT_ENRICHMENT_PROVIDERS", "mockdata")
    from app.config import get_settings
    get_settings.cache_clear()
    alice, a_org = workspace(h, "alice", "Alpha Fire Ltd")
    account = alice.post("/api/si/accounts", json={"name": "Northgate Distribution Ltd", "website": "https://www.northgate-distribution.example"}).json()["account_id"]
    alice.post(f"/api/si/accounts/{account}/contacts", json={"name": "Jordan Lee", "role": "Facilities Manager"})
    view, _ = people_for(alice, account, h)
    by_email = {r["email"]: r for r in view["routes"] if r["email"]}
    stale = by_email["s.patel@northgate-distribution.example"]
    assert stale["quality"] == "provider_verified" and "stale" in stale["flags"] and "conflict" in stale["flags"]
    assert by_email["sam.p@northgate-distribution.example"]["quality"] == "unverified"
    assert "pat@someone-else.example" not in by_email  # the provider placed them at another organisation
    jordan = next(r for r in view["routes"] if r["name"] == "Jordan Lee")
    assert "may_have_moved" in jordan["flags"] and "A newer source suggests they have moved" in jordan["why"]
    assert view["routes"].index(jordan) > view["routes"].index(next(r for r in view["routes"] if r["name"] == "Sam Patel"))
    navigator.PROVIDERS.pop("mockdata")
    get_settings.cache_clear()


# ---------------------------------------------------------------- isolation

def test_research_output_contacts_and_jobs_are_private_to_their_workspace(hosted):
    h = hosted
    with h.system() as db:
        mo = add_notice(db)
    alice, a_org = workspace(h, "alice", "Alpha Fire Ltd")
    bob, b_org = workspace(h, "bob", "Beta Security Ltd")
    account = alice.post(f"/api/si/discover/mo:{mo}/account", json={}).json()["account_id"]
    view, started = people_for(alice, account, h)
    contact = view["routes"][0]["contact_id"]
    for path in (f"/api/si/accounts/{account}/people", f"/api/si/research-jobs/{started['id']}"):
        assert bob.get(path).status_code == 404
    assert bob.post(f"/api/si/accounts/{account}/people-search", json={}).status_code == 404
    assert bob.post(f"/api/si/research-jobs/{started['id']}/cancel").status_code == 404
    assert bob.patch(f"/api/si/contacts/{contact}", json={"status": "do_not_contact"}).status_code == 404
    assert bob.get("/api/si/research-jobs").json()["items"] == []
    # Beta researching the same public notice gets its own contacts; Alpha's are untouched.
    b_account = bob.post(f"/api/si/discover/mo:{mo}/account", json={}).json()["account_id"]
    b_view, _ = people_for(bob, b_account, h)
    assert {r["contact_id"] for r in b_view["routes"]}.isdisjoint({r["contact_id"] for r in view["routes"]})
    with h.as_workspace(b_org) as db:
        assert db.scalar(select(Contact).where(Contact.account_id == account)) is None
        assert {j.organisation_id for j in db.scalars(select(ResearchJob))} == {b_org}


def test_postgres_row_level_security_refuses_raw_sql_across_workspaces(hosted):
    h = hosted
    if h.engine.dialect.name != "postgresql":
        pytest.skip("Row-level security is a PostgreSQL feature; SQLite is single-user only.")
    with h.system() as db:
        mo = add_notice(db)
    alice, a_org = workspace(h, "alice", "Alpha Fire Ltd")
    bob, b_org = workspace(h, "bob", "Beta Security Ltd")
    account = alice.post(f"/api/si/discover/mo:{mo}/account", json={}).json()["account_id"]
    people_for(alice, account, h)
    with h.as_workspace(b_org) as db:  # raw SQL bypasses every ORM filter; the database still refuses
        for table in ("si_accounts", "si_contacts", "si_research_jobs", "si_spend_budgets", "si_audit_events", "si_preferences"):
            assert db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE organisation_id = :o"), {"o": a_org}).scalar() == 0, table
        with pytest.raises(Exception, match="row-level security"):
            db.execute(text("INSERT INTO si_accounts (organisation_id, name, key, kind, status, watched, notes, created_at, updated_at) "
                            "VALUES (:o, 'Planted', 'planted', 'unknown', 'prospect', false, '', now(), now())"), {"o": a_org})
    with h.engine.connect() as raw:  # no workspace at all: nothing
        assert raw.execute(text("SELECT COUNT(*) FROM si_contacts")).scalar() == 0


# ---------------------------------------------------------------- durability, limits, idempotency

def test_spending_limits_cannot_be_bypassed_by_concurrent_requests(hosted, monkeypatch):
    h = hosted
    monkeypatch.setenv("AI_DAILY_LIMIT_CENTS_PER_WORKSPACE", "100")
    monkeypatch.setenv("AI_DAILY_LIMIT_CENTS_PER_USER", "100")
    from app.config import get_settings
    get_settings.cache_clear()
    alice, a_org = workspace(h, "alice", "Alpha Fire Ltd")
    accounts = [alice.post("/api/si/accounts", json={"name": f"Concurrent {i} Ltd"}).json()["account_id"] for i in range(8)]
    token = alice.headers["Authorization"]

    def start(account):
        c = h.client("alice", "alice@alpha.example", "Alice", workspace=a_org)
        return c.post(f"/api/si/accounts/{account}/people-search", json={}).status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(start, accounts))
    assert codes.count(200) == 3 and codes.count(429) == 5, codes  # 3 x 30 cents fit in 100; the fourth would not
    with h.as_workspace(a_org) as db:
        row = db.scalar(select(SpendBudget).where(SpendBudget.user_id == 0))
        assert row.reserved_cents == 90 and db.scalar(select(text("count(*)")).select_from(ResearchJob)) == 3
    jobs.drain(h.engine)
    with h.as_workspace(a_org) as db:
        row = db.scalar(select(SpendBudget).where(SpendBudget.user_id == 0))
        assert row.reserved_cents == 0 and row.spent_cents == 0 + sum(j.actual_cents for j in db.scalars(select(ResearchJob)))
    assert token
    get_settings.cache_clear()


def test_a_retried_write_is_applied_once(hosted):
    h = hosted
    alice, _ = workspace(h, "alice", "Alpha Fire Ltd")
    account = alice.post("/api/si/accounts", json={"name": "Retry Ltd"}).json()["account_id"]
    body = {"services": ["fire_alarm"], "qualification": {"requirement": "PPM for 3 sites"}}
    key = {"Idempotency-Key": "deal-create-0001"}
    first = alice.post(f"/api/si/accounts/{account}/deals", json=body, headers=key).json()
    second = alice.post(f"/api/si/accounts/{account}/deals", json=body, headers=key).json()
    assert first["id"] == second["id"] and len(alice.get("/api/si/deals").json()["items"]) == 1
    assert alice.post(f"/api/si/accounts/{account}/deals", json={**body, "title": "Different"}, headers=key).status_code == 422
    activity = {"kind": "call", "summary": "Spoke to estates", "follow_up": {"due_on": (NOW.date() + timedelta(days=2)).isoformat(), "title": "Send note"}}

    def log(_):
        c = h.client("alice", "alice@alpha.example", "Alice", workspace=alice.headers["X-SalesIntel-Workspace"])
        return c.post(f"/api/si/accounts/{account}/activities", json=activity, headers={"Idempotency-Key": "activity-0001"}).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(log, range(4)))
    view = alice.get(f"/api/si/accounts/{account}").json()
    assert len(view["activities"]) == 1 and len([t for t in view["tasks"] if t["title"] == "Send note"]) == 1, codes
    assert set(codes) <= {200, 409}


def test_jobs_recover_from_a_dead_worker_retry_and_cancel(hosted, monkeypatch):
    h = hosted
    alice, a_org = workspace(h, "alice", "Alpha Fire Ltd")
    account = alice.post("/api/si/accounts", json={"name": "Quiet Fields Care Ltd", "website": "https://www.quietfields-care.example"}).json()["account_id"]
    started = alice.post(f"/api/si/accounts/{account}/people-search", json={}).json()
    claimed = jobs.claim(h.engine)  # a worker claims it, then dies without finishing
    assert claimed and claimed[0] == started["id"]
    assert jobs.claim(h.engine) is None  # its lease still holds
    with h.system() as db:
        db.get(ResearchJob, started["id"]).lease_until = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    jobs.drain(h.engine)  # another worker recovers it
    job = alice.get(f"/api/si/research-jobs/{started['id']}").json()
    assert job["status"] == "partial" and job["attempts"] == 2
    # A transient failure is retried; a cancelled job stops and releases its unspent reservation.
    calls = {"n": 0}

    @jobs.handler("flaky_test")
    def flaky(run):
        calls["n"] += 1
        if calls["n"] == 1:
            raise jobs.Transient("provider timeout")
        return {"status": "succeeded"}
    with h.as_workspace(a_org) as db:
        flaky_job, _ = jobs.enqueue(db, "flaky_test", account_id=None, params={}, estimated_cents=0, user_id=None)
        db.commit()
        fid = flaky_job.id
    jobs.drain(h.engine)
    with h.system() as db:
        db.get(ResearchJob, fid).next_run_at = datetime.now(UTC)
        db.commit()
    jobs.drain(h.engine)
    with h.as_workspace(a_org) as db:
        assert db.get(ResearchJob, fid).status == "succeeded" and db.get(ResearchJob, fid).attempts == 2
    other = alice.post("/api/si/accounts", json={"name": "Cancel Me Ltd"}).json()["account_id"]
    queued = alice.post(f"/api/si/accounts/{other}/people-search", json={}).json()
    before = alice.get("/api/si/spend").json()["workspace"]["reserved_cents"]
    assert alice.post(f"/api/si/research-jobs/{queued['id']}/cancel").json()["status"] == "cancelled"
    assert alice.get("/api/si/spend").json()["workspace"]["reserved_cents"] == before - 30
    jobs.HANDLERS.pop("flaky_test")
