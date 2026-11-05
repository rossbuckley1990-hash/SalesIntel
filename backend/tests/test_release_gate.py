"""Release-gate adversarial findings for PR #3. Each test failed against the code before its fix."""
from datetime import UTC, date, datetime

from app.models.crm import Task
from app.services import si_core
from test_salesintel_journey import add_mo, env, journey_to_logged_contact  # noqa: F401


def two_accounts(c):
    a = c.post("/api/si/accounts", json={"name": "Alpha Housing Ltd"}).json()["account_id"]
    b = c.post("/api/si/accounts", json={"name": "Beta Estates Ltd"}).json()["account_id"]
    return a, b


def test_logging_on_one_account_cannot_complete_another_accounts_follow_up(env):
    c, db = env["client"]()
    a, b = two_accounts(c)
    task_b = c.post(f"/api/si/accounts/{b}/tasks", json={"title": "Call Beta", "due_on": "2026-12-01"}).json()["id"]
    r = c.post(f"/api/si/accounts/{a}/activities", json={"kind": "note", "summary": "Alpha note", "follow_up": {"complete_task_ids": [task_b]}})
    assert r.status_code == 404
    db.expire_all()
    assert db.get(Task, task_b).status == "open"
    assert c.get(f"/api/si/accounts/{a}").json()["activities"] == []  # nothing half-written


def test_drafts_and_tasks_cannot_point_at_another_accounts_deal(env):
    c, _ = env["client"]()
    a, b = two_accounts(c)
    deal_b = c.post(f"/api/si/accounts/{b}/deals", json={"services": ["cctv"], "qualification": {"requirement": "CCTV maintenance"}}).json()["id"]
    assert c.post(f"/api/si/accounts/{a}/drafts", json={"subject": "Hi", "body": "Hello", "deal_id": deal_b}).status_code == 404
    assert c.post(f"/api/si/accounts/{a}/tasks", json={"title": "Chase", "due_on": "2026-12-01", "deal_id": deal_b}).status_code == 404
    assert c.get(f"/api/si/accounts/{a}").json()["tasks"] == []


def won_deal(c, db):
    add_mo(db)
    account, key = journey_to_logged_contact(c)
    deal = c.post(f"/api/si/accounts/{account}/deals", json={"source_key": key, "services": ["fire_alarm"], "qualification": {"requirement": "PPM"}}).json()["id"]
    c.put(f"/api/si/deals/{deal}/scope", json={"entries": [{"service": "fire_alarm", "field": f, "value": v, "basis": "surveyed"}
                                                          for f, v in (("panels", 2), ("devices", 80), ("visits_per_year", 2), ("panel_make", "X"))]})
    c.post(f"/api/si/deals/{deal}/quote", json={"rates": {"fire_alarm.panels": "120", "fire_alarm.devices": "5", "fire_alarm.visits_per_year": "350"}})
    c.post(f"/api/si/deals/{deal}/quote/approve", json={"reviewer": "Pat Manager"})
    assert c.patch(f"/api/si/deals/{deal}", json={"stage": "won", "reason": "Signed"}).json()["stage"] == "won"
    return account, deal


def test_a_won_deal_is_closed_and_its_handed_over_quotation_cannot_be_reopened(env):
    c, db = env["client"]()
    account, deal = won_deal(c, db)
    before = c.get(f"/api/si/deals/{deal}").json()
    for path, method, body in ((f"/api/si/deals/{deal}", "patch", {"stage": "qualify"}),
                               (f"/api/si/deals/{deal}", "patch", {"stage": "lost", "reason": "Changed mind"}),
                               (f"/api/si/deals/{deal}", "patch", {"services": ["fire_alarm", "cctv"]}),
                               (f"/api/si/deals/{deal}/scope", "put", {"entries": [{"service": "fire_alarm", "field": "devices", "value": 90, "basis": "surveyed"}]}),
                               (f"/api/si/deals/{deal}/quote", "post", {"rates": {"fire_alarm.devices": "6"}})):
        assert getattr(c, method)(path, json=body).status_code == 409, (method, path, body)
    after = c.get(f"/api/si/deals/{deal}").json()
    assert after["stage"] == "won" and after["quote"] == before["quote"] and after["handover"] == before["handover"]
    assert c.get(f"/api/si/accounts/{account}").json()["status"] == "customer"
    # Non-commercial notes can still be kept up to date.
    assert c.patch(f"/api/si/deals/{deal}", json={"next_step": "Mobilisation call"}).json()["next_step"] == "Mobilisation call"


def test_today_follows_the_uk_calendar_not_utc(env, monkeypatch):
    c, _ = env["client"]()
    a, _ = two_accounts(c)
    c.post(f"/api/si/accounts/{a}/tasks", json={"title": "Due today in London", "due_on": "2026-06-11"})
    c.post(f"/api/si/accounts/{a}/tasks", json={"title": "Due yesterday in London", "due_on": "2026-06-10"})
    # 23:30 UTC on 10 June is 00:30 BST on 11 June.
    monkeypatch.setattr(si_core, "now", lambda: datetime(2026, 6, 10, 23, 30, tzinfo=UTC))
    queue = {q["title"]: q for q in c.get("/api/si/today").json()["queue"] if q["kind"] == "follow_up"}
    assert queue["Due today in London"]["priority"] == 1 and "is due" in queue["Due today in London"]["why"]
    assert queue["Due yesterday in London"]["priority"] == 0 and "overdue" in queue["Due yesterday in London"]["why"]
    assert next(x for x in c.get("/api/si/accounts").json()["items"] if x["id"] == a)["overdue"] is True
    assert si_core.uk_today() == date(2026, 6, 11)
