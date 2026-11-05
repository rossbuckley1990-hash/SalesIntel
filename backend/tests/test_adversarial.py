"""Adversarial acceptance challenge for the discovery-to-won loop.

Each test tries to break a promise the product makes: that records survive a real process
restart, that nothing leaves the machine, that duplicates do not multiply accounts, and that
follow-ups and history stay continuous.
"""
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from test_salesintel_journey import add_mo, add_prospect, env, journey_to_logged_contact  # noqa: F401

BACKEND = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_api(db_url: str, port: int) -> subprocess.Popen:
    env = {**os.environ, "DATABASE_URL": db_url, "APP_ENV": "local", "PYTHONPATH": str(BACKEND), "ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", str(BACKEND), "--host", "127.0.0.1", "--port", str(port)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/api/si/today", timeout=1).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("API did not start")


def test_records_survive_a_real_process_restart(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'restart.db'}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        add_mo(db)
    engine.dispose()
    port = free_port()
    base = f"http://127.0.0.1:{port}/api/si"
    api = start_api(db_url, port)
    try:
        account = httpx.post(f"{base}/discover/mo:1/account", json={}).json()["account_id"]
        due = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()
        httpx.post(f"{base}/accounts/{account}/activities", json={"kind": "call", "summary": "Spoke to estates", "outcome": "interested",
                                                                   "follow_up": {"due_on": due, "title": "Send capability note"}}).raise_for_status()
        deal = httpx.post(f"{base}/accounts/{account}/deals", json={"source_key": "mo:1", "services": ["fire_alarm"], "qualification": {"requirement": "Annual PPM"}}).json()
    finally:
        api.kill()
        api.wait()
    api = start_api(db_url, port)  # a new process on the same file
    try:
        view = httpx.get(f"{base}/accounts/{account}").json()
        assert [a["summary"] for a in view["activities"]] == ["Spoke to estates"]
        assert view["tasks"][0]["title"] == "Send capability note" and view["tasks"][0]["status"] == "open"
        assert view["sources"][0]["evidence"][0]["url"].startswith("https://www.contractsfinder.service.gov.uk/")
        reopened = httpx.get(f"{base}/deals/{deal['id']}").json()
        assert reopened["stage"] == "qualify" and reopened["origin"]["key"] == "mo:1" and reopened["value_basis"] == "unknown"
        assert any(t["title"] == "Send capability note" for t in httpx.get(f"{base}/today").json()["upcoming"])
    finally:
        api.kill()
        api.wait()


@pytest.fixture
def no_network(monkeypatch):
    """Fail any connection that is not to this machine, so a send or paid call cannot hide."""
    attempts = []
    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost"):
            attempts.append(host)
            raise ConnectionRefusedError(f"blocked external connection to {host}")
        return real_connect(self, address)
    monkeypatch.setattr(socket.socket, "connect", guarded)
    real_getaddrinfo = socket.getaddrinfo

    def resolve(host, *args, **kwargs):
        if host not in ("127.0.0.1", "::1", "localhost", "testserver"):
            attempts.append(host)
            raise socket.gaierror(f"blocked lookup of {host}")
        return real_getaddrinfo(host, *args, **kwargs)
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    return attempts


def test_the_whole_loop_makes_no_external_connection(env, no_network):
    c, db = env["client"]()
    add_mo(db, value={"type": "published_total", "published_total": 90000, "estimated_annualised": None, "framework_ceiling": None, "basis": "Published", "scope_note": ""})
    account, key = journey_to_logged_contact(c)
    deal = c.post(f"/api/si/accounts/{account}/deals", json={"source_key": key, "services": ["fire_alarm"], "qualification": {"requirement": "PPM"}}).json()["id"]
    c.put(f"/api/si/deals/{deal}/scope", json={"entries": [{"service": "fire_alarm", "field": f, "value": v, "basis": "surveyed"}
                                                          for f, v in (("panels", 2), ("devices", 80), ("visits_per_year", 2), ("panel_make", "X"))]})
    c.post(f"/api/si/deals/{deal}/quote", json={"rates": {"fire_alarm.panels": "120", "fire_alarm.devices": "5", "fire_alarm.visits_per_year": "350"}})
    c.post(f"/api/si/deals/{deal}/quote/approve", json={"reviewer": "Pat Manager"})
    for stage in ("survey", "proposal", "approval"):
        c.patch(f"/api/si/deals/{deal}", json={"stage": stage})
    assert c.patch(f"/api/si/deals/{deal}", json={"stage": "won", "reason": "Signed"}).json()["stage"] == "won"
    assert no_network == []  # nothing in the loop reached outside this machine


def test_repeated_notices_and_research_for_one_organisation_make_one_account(env):
    c, db = env["client"]()
    first = add_mo(db, customer="ORBIT GROUP LIMITED", title="Fire alarm servicing")
    second = add_mo(db, customer="Orbit Group Ltd", title="CCTV maintenance")
    research = add_prospect(db, name="Orbit Group")
    ids = {c.post(f"/api/si/discover/{key}/account", json={}).json()["account_id"] for key in (f"mo:{first}", f"mo:{second}", f"pr:{research}")}
    assert len(ids) == 1
    account = c.get(f"/api/si/accounts/{ids.pop()}").json()
    assert len(account["sources"]) == 3 and [i["confirmed"] for i in account["identities"]] == [True, False, False]
    assert len(c.get("/api/si/accounts").json()["items"]) == 1
    # Linking the same record twice is idempotent.
    assert c.post(f"/api/si/discover/mo:{first}/account", json={}).json()["created"] is False
    assert len(c.get(f"/api/si/accounts/{account['id']}").json()["identities"]) == 3


def test_follow_ups_and_history_stay_continuous(env):
    c, db = env["client"]()
    add_mo(db)
    account, _ = journey_to_logged_contact(c)
    task = c.get(f"/api/si/accounts/{account}").json()["tasks"][0]
    tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    assert c.patch(f"/api/si/tasks/{task['id']}", json={"due_on": tomorrow}).json()["due_on"] == tomorrow
    # Logging the call that the follow-up asked for completes it and schedules the next one, in one step.
    logged = c.post(f"/api/si/accounts/{account}/activities", json={"kind": "call", "summary": "Followed up by phone", "outcome": "meeting_booked",
                                                                    "follow_up": {"due_on": tomorrow, "title": "Prepare for the meeting", "complete_task_ids": [task["id"]]}}).json()
    view = c.get(f"/api/si/accounts/{account}").json()
    assert {t["title"]: t["status"] for t in view["tasks"]} == {"Call facilities team": "done", "Prepare for the meeting": "open"}
    assert [a["summary"] for a in view["activities"]][0] == "Followed up by phone" and len(view["activities"]) == 2
    assert view["next_step"].startswith("Prepare for the meeting") and logged["task"]["title"] == "Prepare for the meeting"
    assert c.get("/api/si/metrics").json()["counts"]["meeting_booked"] == 1
