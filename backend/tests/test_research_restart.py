"""Durable research across a real process crash: kill the API mid-research, start it again, and the job finishes."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import httpx
from sqlalchemy import create_engine, text

from app.db import Base
import app.models  # noqa: F401

BACKEND = Path(__file__).resolve().parents[1]


def port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(db_url: str, p: int) -> subprocess.Popen:
    env = {**os.environ, "DATABASE_URL": db_url, "APP_ENV": "test", "AUTH_MODE": "local", "RESEARCH_PROVIDER": "replay", "RESEARCH_WORKER": "inline",
           "RESEARCH_LEASE_SECONDS": "3", "SALESINTEL_REPLAY_DELAY_SECONDS": "2", "PYTHONPATH": str(BACKEND), "ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", str(BACKEND), "--host", "127.0.0.1", "--port", str(p)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(150):
        try:
            if httpx.get(f"http://127.0.0.1:{p}/api/si/today", timeout=1).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("API did not start")


def wait(fn, seconds: float):
    end = time.time() + seconds
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError("timed out")


def test_research_survives_the_server_being_killed_mid_run(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'restart.db'}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    p = port()
    base = f"http://127.0.0.1:{p}/api/si"
    api = start(db_url, p)
    try:
        account = httpx.post(f"{base}/accounts", json={"name": "Quiet Fields Care Ltd", "website": "https://www.quietfields-care.example"}).json()["account_id"]
        job = httpx.post(f"{base}/accounts/{account}/people-search", json={}).json()
        wait(lambda: httpx.get(f"{base}/research-jobs/{job['id']}").json()["status"] == "running", 10)
        time.sleep(0.5)  # it is now inside a (slow, replayed) provider call
    finally:
        api.send_signal(signal.SIGKILL)  # no shutdown hook, no cleanup: a crash
        api.wait()
    with engine.connect() as c:
        assert c.execute(text("SELECT status FROM si_research_jobs WHERE id = :i"), {"i": job["id"]}).scalar() == "running"  # stranded mid-run
    api = start(db_url, p)  # a new process on the same database
    try:
        done = wait(lambda: (j := httpx.get(f"{base}/research-jobs/{job['id']}").json())["status"] in ("succeeded", "partial") and j, 40)
        assert done["attempts"] == 2 and done["result"]["message"].startswith("Relevant decision-maker role identified")
        people = httpx.get(f"{base}/accounts/{account}/people").json()
        assert [r["quality"] for r in people["routes"]] == ["role_only"]  # saved once, not duplicated by the retry
        spend = httpx.get(f"{base}/spend").json()["workspace"]
        assert done["actual_cents"] > 0 and spend["reserved_cents"] == 0
        assert spend["spent_cents"] == max(done["actual_cents"], done["estimated_cents"])  # the interrupted call is charged conservatively
    finally:
        api.kill()
        api.wait()
