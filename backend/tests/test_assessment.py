"""Can we win this? Fit and readiness at once; a win probability only when validated history supports one."""
from datetime import UTC, datetime, timedelta

from app.models.crm import Account, DealRecord
from app.services.si_assess import INSUFFICIENT
from tenancy_support import hosted  # noqa: F401
from test_salesintel_journey import add_mo, env, journey_to_logged_contact  # noqa: F401

T0 = datetime(2025, 1, 1, tzinfo=UTC)


def history(db, outcomes: list[tuple[str, str, bool]], organisation_id: int | None = None):
    """Closed deals in order: (service, work type, won)."""
    account = Account(name="History Ltd", key="history ltd", kind="private", status="customer", watched=False, notes="", created_at=T0, updated_at=T0,
                      **({"organisation_id": organisation_id} if organisation_id else {}))
    db.add(account)
    db.flush()
    for i, (service, work_type, won) in enumerate(outcomes):
        moment = T0 + timedelta(days=i)
        db.add(DealRecord(account_id=account.id, title=f"Past {i}", stage="won" if won else "lost", origin={}, services=[service], work_type=work_type,
                          qualification={"requirement": "x"}, value_basis="unknown", next_step="", scope={}, quote={}, handover={}, outcome_reason="r",
                          created_at=moment, updated_at=moment, **({"organisation_id": organisation_id} if organisation_id else {})))
    db.commit()


def new_deal(c):
    account, key = journey_to_logged_contact(c)
    return c.post(f"/api/si/accounts/{account}/deals", json={"source_key": key, "services": ["fire_alarm"], "work_type": "ppm",
                                                          "qualification": {"requirement": "Annual PPM for 3 sites"}}).json()["id"]


def test_fit_and_readiness_are_immediate_and_probability_is_withheld_without_history(env):
    c, db = env["client"]()
    add_mo(db)
    c.put("/api/si/preferences", json={"services": ["fire_alarm"], "territory": ["England"]})
    deal = new_deal(c)
    c.patch(f"/api/si/deals/{deal}", json={"seller_confidence": "high"})
    a = c.get(f"/api/si/deals/{deal}/assessment").json()
    fit = {i["key"]: i for i in a["commercial_fit"]["criteria"]}
    assert fit["services"]["status"] == "met" and fit["work_type"]["status"] == "met"
    assert fit["accreditations"]["status"] == "unknown" and "not assumed" in fit["accreditations"]["evidence"]  # never assumed compliant
    ready = {i["key"]: i for i in a["win_readiness"]["items"]}
    assert ready["requirement"]["status"] == "done" and ready["decision_maker"]["status"] == "missing"
    assert ready["decision_maker"]["action"] == "Find out who signs off the contract and who influences it."
    assert ready["quotation"]["status"] == "missing" and ready["next_step"]["status"] in ("done", "missing")
    assert a["seller_confidence"] == {"value": "high", "label": "High", "basis": "The salesperson's own judgement."}
    p = a["win_probability"]
    assert p["available"] is False and p["message"] == INSUFFICIENT and p["comparable_outcomes"] == 0 and "estimate" not in p


def test_a_validated_rate_is_shown_with_its_sample_interval_and_limits(env):
    c, db = env["client"]()
    add_mo(db)
    # Fire alarm maintenance usually won, CCTV installation usually lost: comparable deals carry real signal.
    pattern = []
    for i in range(40):
        pattern.append(("fire_alarm", "ppm", i % 5 != 0))      # 80% won
        pattern.append(("cctv", "installation", i % 5 == 0))   # 20% won
    history(db, pattern)
    deal = new_deal(c)
    p = c.get(f"/api/si/deals/{deal}/assessment").json()["win_probability"]
    assert p["available"] is True and p["comparable_outcomes"] == 40 and p["wins"] == 32 and p["estimate"] == 0.8
    assert p["interval"][0] < 0.8 < p["interval"][1] and p["interval"][1] - p["interval"][0] > 0.15  # uncertainty is shown, not hidden
    assert p["validation"]["brier"] < p["validation"]["baseline_brier"] and p["validation"]["holdout_deals"] >= 10
    assert any("not what this customer will decide" in x for x in p["limitations"])


def test_history_without_predictive_value_still_gives_no_number(env):
    c, db = env["client"]()
    add_mo(db)
    history(db, [("fire_alarm", "ppm", i % 2 == 0) for i in range(60)])  # one cohort: no better than the overall rate
    deal = new_deal(c)
    p = c.get(f"/api/si/deals/{deal}/assessment").json()["win_probability"]
    assert p["available"] is False and p["message"] == INSUFFICIENT and "no better than the overall win rate" in p["reason"]
    assert p["comparable_outcomes"] == 60


def test_too_few_outcomes_of_one_kind_gives_no_number(env):
    c, db = env["client"]()
    add_mo(db)
    history(db, [("fire_alarm", "ppm", True) for _ in range(35)] + [("fire_alarm", "ppm", False) for _ in range(3)])
    p = c.get(f"/api/si/deals/{new_deal(c)}/assessment").json()["win_probability"]
    assert p["available"] is False and "5 wins and 5 losses" in p["reason"]


def test_another_workspaces_history_never_counts_and_its_assessments_are_private(hosted):
    h = hosted
    with h.system() as db:
        add_mo(db)
    alice = h.client("alice", "alice@alpha.example")
    a_org = alice.post("/api/workspaces", json={"name": "Alpha"}).json()["id"]
    alice = h.client("alice", "alice@alpha.example", workspace=a_org)
    bob = h.client("bob", "bob@beta.example")
    b_org = bob.post("/api/workspaces", json={"name": "Beta"}).json()["id"]
    bob = h.client("bob", "bob@beta.example", workspace=b_org)
    pattern = [("fire_alarm", "ppm", i % 5 != 0) for i in range(40)] + [("cctv", "installation", i % 5 == 0) for i in range(40)]
    with h.as_workspace(b_org) as db:
        history(db, pattern, organisation_id=b_org)
    deal = new_deal(alice)
    p = alice.get(f"/api/si/deals/{deal}/assessment").json()["win_probability"]
    assert p["available"] is False and p["comparable_outcomes"] == 0
    assert bob.get(f"/api/si/deals/{deal}/assessment").status_code == 404
