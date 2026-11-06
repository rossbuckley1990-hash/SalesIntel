"""A local install has no Team page, so its owner approves the research budget from the app's own menu.

Live paid research stays refused until they do, and the refusal says where to go: never to a page that does not exist."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import Base, get_db
from app.main import create_app
from app.services import spend


@pytest.fixture
def local(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'local.db'}", connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    session = Session(engine)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app), session
    session.close()
    engine.dispose()


def test_the_owner_of_a_local_install_approves_the_research_budget(local, monkeypatch):
    client, session = local
    assert get_settings().auth_mode == 'local'  # no sign-in: the person at this Mac is the administrator
    monkeypatch.setattr(spend, 'live_provider', lambda: True)  # as if a real, paid provider were configured
    before = client.get('/api/si/research-budget').json()
    assert before['approved'] is False and before['live_provider'] is True
    approved = client.post('/api/si/research-budget', json={'amount_cents': 2000, 'note': 'First live investigations'})
    assert approved.status_code == 200, approved.text
    assert approved.json()['approved_cents'] == 2000 and approved.json()['remaining_cents'] == 2000
    from app.models.tenancy import WorkspaceAuditEvent
    event = session.scalar(select(WorkspaceAuditEvent).where(WorkspaceAuditEvent.action == 'budget_up'))
    assert event.detail['added_cents'] == 2000  # every approval is recorded


def test_a_refusal_points_a_local_owner_to_the_menu_and_a_team_to_its_administrator(monkeypatch):
    missing = spend.refusal(spend.ApprovalRequired('not_approved'))
    used_up = spend.refusal(spend.ApprovalRequired('used_up'))
    assert missing['status_code'] == used_up['status_code'] == 409
    for refused in (missing, used_up):
        text = refused['detail']
        assert 'Team' not in text and 'administrator' not in text  # a local install has neither
        assert 'Research budget' in text and 'Nothing was started or charged' in text
    monkeypatch.setattr(spend, 'get_settings', lambda: Settings(auth_mode='dev', app_env='test'))
    hosted = spend.refusal(spend.ApprovalRequired('not_approved'))['detail']
    assert 'approved by an administrator (Team, Research budget)' in hosted  # a team's wording is unchanged
