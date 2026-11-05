"""Regression tests for the hardening pass: quotation approval versioning and contact suppression."""
from fastapi.testclient import TestClient

from test_salesintel_journey import add_mo, env, journey_to_logged_contact  # noqa: F401  (env is a fixture)

SURVEY = [("panels", 2), ("devices", 80), ("visits_per_year", 2), ("panel_make", "Example Panel")]
RATES = {"fire_alarm.panels": 120, "fire_alarm.devices": 5, "fire_alarm.visits_per_year": 350}


def approved_deal(c: TestClient) -> int:
    account_id, key = journey_to_logged_contact(c)
    deal = c.post(f"/api/si/accounts/{account_id}/deals", json={"source_key": key, "services": ["fire_alarm"], "work_type": "ppm",
                                                              "qualification": {"requirement": "PPM for 2 sites"}}).json()
    c.put(f"/api/si/deals/{deal['id']}/scope", json={"entries": [{"service": "fire_alarm", "field": f, "value": v, "basis": "surveyed"} for f, v in SURVEY]})
    c.post(f"/api/si/deals/{deal['id']}/quote", json={"rates": RATES})
    assert c.post(f"/api/si/deals/{deal['id']}/quote/approve", json={"reviewer": "Pat Manager"}).json()["quote"]["status"] == "approved"
    return deal["id"]


def test_changing_scope_after_approval_invalidates_it_and_blocks_won(env):
    c, db = env["client"]()
    add_mo(db)
    deal = approved_deal(c)
    changed = c.put(f"/api/si/deals/{deal}/scope", json={"entries": [{"service": "fire_alarm", "field": "devices", "value": 120, "basis": "surveyed"}]}).json()
    assert changed["quote"]["status"] == "superseded"
    assert changed["quote"]["approvals"][0]["version"] == 1 and changed["quote"]["approvals"][0]["reviewer"] == "Pat Manager"
    blocked = c.patch(f"/api/si/deals/{deal}", json={"stage": "won", "reason": "Signed"})
    assert blocked.status_code == 422 and "approve" in blocked.json()["detail"].lower()
    # Rebuild and re-approve: a second version, and only then can the deal be won.
    c.post(f"/api/si/deals/{deal}/quote", json={"rates": RATES})
    again = c.post(f"/api/si/deals/{deal}/quote/approve", json={"reviewer": "Pat Manager"}).json()["quote"]
    assert again["status"] == "approved" and again["version"] == 2 and again["subtotal"] == "1540.00"
    for stage in ("survey", "proposal", "approval"):
        c.patch(f"/api/si/deals/{deal}", json={"stage": stage})
    won = c.patch(f"/api/si/deals/{deal}", json={"stage": "won", "reason": "Signed"}).json()
    assert won["stage"] == "won" and won["handover"]["quote"]["version"] == 2


def test_services_work_type_and_rates_also_invalidate_approval(env):
    c, db = env["client"]()
    add_mo(db)
    deal = approved_deal(c)

    def reapprove():
        c.put(f"/api/si/deals/{deal}/scope", json={"entries": [{"service": "fire_alarm", "field": f, "value": v, "basis": "surveyed"} for f, v in SURVEY]})
        c.post(f"/api/si/deals/{deal}/quote", json={"rates": RATES})
        return c.post(f"/api/si/deals/{deal}/quote/approve", json={"reviewer": "Pat Manager"}).json()["quote"]

    assert c.patch(f"/api/si/deals/{deal}", json={"work_type": "reactive"}).json()["quote"]["status"] == "superseded"
    assert reapprove()["status"] == "approved"
    assert c.patch(f"/api/si/deals/{deal}", json={"services": ["fire_alarm", "cctv"]}).json()["quote"]["status"] == "superseded"
    c.patch(f"/api/si/deals/{deal}", json={"services": ["fire_alarm"]})
    approved = reapprove()
    assert approved["status"] == "approved" and approved["version"] == 3
    rebuilt = c.post(f"/api/si/deals/{deal}/quote", json={"rates": {**RATES, "fire_alarm.devices": 6}}).json()["quote"]
    assert rebuilt["status"] == "draft" and [a["version"] for a in rebuilt["approvals"]] == [1, 2, 3]
    # A change that does not affect the quotation (the next step text) leaves the approval alone.
    reapprove()
    assert c.patch(f"/api/si/deals/{deal}", json={"next_step": "Call on Monday"}).json()["quote"]["status"] == "approved"


def test_suppressing_a_contact_blocks_existing_drafts_but_keeps_history(env):
    c, db = env["client"]()
    add_mo(db)
    account = c.post("/api/si/discover/mo:1/account", json={}).json()["account_id"]
    contact = c.post(f"/api/si/accounts/{account}/contacts", json={"name": "Jo Example", "role": "Estates lead", "email": "jo@example-housing.example"}).json()
    # A message genuinely sent before the opt-out.
    first = c.post(f"/api/si/accounts/{account}/drafts", json={"subject": "Intro", "body": "Dear Jo, hello. Regards, Alex, Regional Fire", "contact_id": contact["id"]}).json()
    c.post(f"/api/si/drafts/{first['id']}/approve")
    sent = c.post(f"/api/si/drafts/{first['id']}/log", json={"sent_externally": True}).json()["activity"]
    # A second, approved but unsent draft, then the contact opts out.
    second = c.post(f"/api/si/accounts/{account}/drafts", json={"subject": "Follow-up", "body": "Dear Jo, following up. Regards, Alex, Regional Fire", "contact_id": contact["id"]}).json()
    assert c.post(f"/api/si/drafts/{second['id']}/approve").json()["status"] == "approved"
    c.patch(f"/api/si/contacts/{contact['id']}", json={"status": "do_not_contact"})
    view = c.get(f"/api/si/accounts/{account}").json()
    assert [d["status"] for d in view["drafts"] if d["id"] == second["id"]] == ["suppressed"]
    assert c.post(f"/api/si/drafts/{second['id']}/approve").status_code == 409
    assert c.post(f"/api/si/drafts/{second['id']}/log", json={"sent_externally": True}).status_code == 409
    assert all(q.get("draft_id") != second["id"] for q in c.get("/api/si/today").json()["queue"])
    assert c.post(f"/api/si/accounts/{account}/activities", json={"kind": "call", "direction": "outbound", "summary": "Called Jo", "contact_id": contact["id"]}).status_code == 409
    # Factual history is untouched, and an inbound message from them can still be recorded.
    assert [a["id"] for a in view["activities"]] == [sent["id"]] and view["activities"][0]["summary"] == "Sent: Intro"
    assert c.post(f"/api/si/accounts/{account}/activities", json={"kind": "email", "direction": "inbound", "summary": "Jo asked to be removed", "contact_id": contact["id"]}).status_code == 200
    # Lifting the opt-out does not silently re-approve: the draft must be saved and approved again.
    c.patch(f"/api/si/contacts/{contact['id']}", json={"status": "verified"})
    assert c.get(f"/api/si/accounts/{account}").json()["drafts"][0]["status"] == "suppressed"
    assert c.post(f"/api/si/drafts/{second['id']}/approve").status_code == 409
    assert c.patch(f"/api/si/drafts/{second['id']}", json={"body": "Dear Jo, following up. Regards, Alex, Regional Fire"}).json()["status"] == "draft"
    assert c.post(f"/api/si/drafts/{second['id']}/approve").json()["status"] == "approved"


def test_money_is_exact_and_invalid_inputs_are_rejected(env):
    c, db = env["client"]()
    add_mo(db)
    account_id, key = journey_to_logged_contact(c)
    deal = c.post(f"/api/si/accounts/{account_id}/deals", json={"source_key": key, "services": ["fire_alarm"], "qualification": {"requirement": "PPM"}}).json()["id"]
    entries = [{"service": "fire_alarm", "field": f, "value": v, "basis": "surveyed"} for f, v in (("panels", 3), ("devices", 3), ("visits_per_year", 3), ("panel_make", "X"))]
    assert c.put(f"/api/si/deals/{deal}/scope", json={"entries": entries}).status_code == 200
    # Fractional pence are allowed on unit rates; each line rounds half up to the penny, and the total is exact.
    quote = c.post(f"/api/si/deals/{deal}/quote", json={"rates": {"fire_alarm.panels": "4.555", "fire_alarm.devices": "0.1", "fire_alarm.visits_per_year": "0.1"}}).json()["quote"]
    assert [l["total"] for l in quote["lines"]] == ["13.67", "0.30", "0.30"] and quote["subtotal"] == "14.27"
    assert quote["lines"][0]["rate"] == "4.555"
    bad_rates = ["4.55555", "-1", "abc", "NaN", "Infinity", "1e12", 0.1 + 0.2, True, ""]
    for bad in bad_rates[:-1]:
        response = c.post(f"/api/si/deals/{deal}/quote", json={"rates": {"fire_alarm.panels": bad}})
        assert response.status_code == 422, bad
    assert c.get(f"/api/si/deals/{deal}").json()["quote"]["subtotal"] == "14.27"  # a rejected input changes nothing
    for bad in ("2.5", "-1", "many", True):
        assert c.put(f"/api/si/deals/{deal}/scope", json={"entries": [{"service": "fire_alarm", "field": "panels", "value": bad, "basis": "surveyed"}]}).status_code == 422, bad
    assert c.patch(f"/api/si/deals/{deal}", json={"value_total": "£12,500.50"}).json()["value_total"] == 12500.5
    for bad in ("12.345", "-5", "free"):
        assert c.patch(f"/api/si/deals/{deal}", json={"value_total": bad}).status_code == 422, bad
