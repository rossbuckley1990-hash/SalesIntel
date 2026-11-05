"""Hosted-mode test harness: real app, signed tokens, a fresh session per request, SQLite or PostgreSQL."""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import auth
from app.config import get_settings
from app.db import Base, get_db
from app.main import create_app
from app.tenancy import ORG, SYSTEM

POSTGRES = os.environ.get("SALESINTEL_TEST_POSTGRES_URL")  # an admin URL; each test gets its own database
BACKENDS = ["sqlite"] + (["postgresql"] if POSTGRES else [])


def require_postgres_in_ci():
    if os.environ.get("SALESINTEL_REQUIRE_POSTGRES") and not POSTGRES:
        raise AssertionError("CI requires the PostgreSQL tenancy tests: set SALESINTEL_TEST_POSTGRES_URL.")


@contextmanager
def database(kind: str, tmp_path):
    if kind == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'hosted.db'}", connect_args={"check_same_thread": False})
        yield engine
        engine.dispose()
        return
    name = f"si_t_{uuid.uuid4().hex[:12]}"
    admin = create_engine(POSTGRES.replace("postgresql://", "postgresql+psycopg://", 1), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    base = POSTGRES.rsplit("/", 1)[0].replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(f"{base}/{name}")
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def app_role_engine(admin_engine):
    """PostgreSQL: row-level security on, and the application connecting as an ordinary role, as in production."""
    from app.rls import enable
    role = f"si_app_{uuid.uuid4().hex[:8]}"
    with admin_engine.begin() as c:
        enable(c)
        c.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD 'test-only' NOSUPERUSER NOBYPASSRLS"))
        c.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
        c.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}"))
        c.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"))
    url = admin_engine.url.set(username=role, password="test-only")
    return create_engine(url), role


class Hosted:
    def __init__(self, engine):
        self.engine = engine
        self.app = create_app()

        def fresh_session():
            session = Session(engine)
            try:
                yield session
            finally:
                session.close()
        self.app.dependency_overrides[get_db] = fresh_session

    def client(self, sub: str, email: str, name: str = "", workspace: int | None = None, **claims) -> TestClient:
        headers = {"Authorization": f"Bearer {auth.dev_token(sub, email, name or sub.title(), **claims)}"}
        if workspace is not None:
            headers["X-SalesIntel-Workspace"] = str(workspace)
        return TestClient(self.app, headers=headers)

    def anonymous(self) -> TestClient:
        return TestClient(self.app)

    def system(self) -> Session:
        session = Session(self.engine)
        session.info[SYSTEM] = True
        return session

    def as_workspace(self, org: int) -> Session:
        session = Session(self.engine)
        session.info[ORG] = org
        return session


@pytest.fixture(params=BACKENDS)
def hosted(request, tmp_path, monkeypatch):
    require_postgres_in_ci()
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("RESEARCH_PROVIDER", "replay")  # offline synthetic research; no network, no credit
    monkeypatch.setenv("RESEARCH_WORKER", "off")  # tests run jobs explicitly with jobs.drain
    get_settings.cache_clear()
    with database(request.param, tmp_path) as engine:
        Base.metadata.create_all(engine)
        if request.param == "postgresql":
            app_engine, role = app_role_engine(engine)
            yield Hosted(app_engine)
            app_engine.dispose()
            with engine.begin() as c:
                c.execute(text(f"DROP OWNED BY {role}"))
                c.execute(text(f"DROP ROLE {role}"))
        else:
            yield Hosted(engine)
    get_settings.cache_clear()
