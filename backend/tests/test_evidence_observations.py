from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, create_database_engine, get_db
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'evidence.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app = create_app()
    app.state.test_engine = engine
    app.dependency_overrides[get_db] = override
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    engine.dispose()


def observation(**overrides):
    return {
        "organisation_id": "GB-COH:12345678", "organisation_name": "Example Ltd",
        "site": "York", "category": "service_issue",
        "observed_statement": "A report describes delayed service visits.",
        "source_title": "Example source", "source_reference": "report-1",
        "source_url": "https://example.com/report/1", "published_at": "2026-10-01",
        "observed_at": "2026-09-30", "retrieved_at": "2026-10-28T14:00:00+01:00",
        **overrides,
    }


def test_import_is_idempotent_but_keeps_conflicting_and_separate_site_evidence(client: TestClient):
    a = observation()
    contradictory = observation(observed_statement="A later account says visits were completed on time.")
    different_site = observation(site="Leeds")
    response = client.post('/api/evidence-observations/import', json={'observations': [a, a, contradictory, different_site]})
    assert response.status_code == 200, response.text
    assert response.json() == {'imported': 3, 'duplicates': 1}
    assert client.post('/api/evidence-observations/import', json={'observations': [observation(retrieved_at="2026-10-29T15:00:00Z")]}).json() == {'imported': 0, 'duplicates': 1}
    dossier = client.get('/api/evidence-observations/accounts/GB-COH:12345678').json()
    assert dossier['total'] == 3
    assert {item['site'] for item in dossier['observations']} == {'York', 'Leeds'}
    assert {item['observed_statement'] for item in dossier['observations']} == {a['observed_statement'], contradictory['observed_statement']}
    assert dossier['observations'][0]['source_reference'] == 'report-1'
    assert '2026-10-28T13:00:00' in dossier['observations'][0]['retrieved_at']


def test_exact_supplied_identifier_grouping_and_pagination(client: TestClient):
    records = [observation(), observation(organisation_id="GB-COH:87654321", organisation_name="Example Ltd"), observation(site="Bristol")]
    assert client.post('/api/evidence-observations/import', json={'observations': records}).status_code == 200
    accounts = client.get('/api/evidence-observations/accounts?limit=1&offset=0').json()
    assert accounts['total'] == 2 and len(accounts['items']) == 1
    assert accounts['items'][0]['observation_count'] == 2
    account = client.get('/api/evidence-observations/accounts/GB-COH:12345678?limit=1&offset=1').json()
    assert account['total'] == 2 and len(account['observations']) == 1
    assert client.get('/api/evidence-observations?organisation_id=GB-COH:87654321').json()['total'] == 1
    assert client.get('/api/evidence-observations/accounts/GB-COH:00000000').status_code == 404


def test_hypotheses_scope_by_site_and_user_selection(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.routers.evidence_observations as router
    from app.schemas.side_channel import AIHypothesisResult

    records = [observation(category="maintenance", observed_statement="Fire alarm maintenance", source_reference="source-1"),
        observation(category="service_issue", source_reference="source-2", source_url="https://example.org/2"),
        observation(site="Leeds", source_reference="source-3", source_url="https://example.org/3"),
        observation(organisation_id="GB-COH:87654321", source_reference="source-4", source_url="https://example.org/4")]
    assert client.post('/api/evidence-observations/import', json={'observations': records}).status_code == 200
    data = client.get('/api/evidence-observations/accounts/GB-COH:12345678/hypotheses').json()
    assert data['analysed_observations'] == 3
    york = next(site for site in data['sites'] if site['site'] == 'York')
    assert len(york['hypotheses']) == 1
    ids = york['hypotheses'][0]['observation_ids']
    sent = []
    def fake(org, site, observations, *, settings):
        sent.extend(observations)
        return AIHypothesisResult(hypotheses=[], limitations=[])
    monkeypatch.setattr(router, 'synthesise_hypotheses', fake)
    monkeypatch.setattr(router, 'get_settings', lambda: None)
    path = '/api/evidence-observations/accounts/GB-COH:12345678/ai-hypotheses'
    assert client.post(path, json={'site': 'York', 'observation_ids': ids + [4]}).status_code == 422
    assert not sent
    result = client.post(path, json={'site': 'York', 'observation_ids': ids})
    assert result.status_code == 200
    assert {item.id for item in sent} == set(ids)
    assert len(result.json()['observations']) == 2


def test_batch_validation_is_atomic_and_rejects_unstable_ids_and_invalid_provenance(client: TestClient):
    for bad in [observation(organisation_id="Example Ltd"), observation(site=" "), observation(source_url="javascript:alert(1)"), observation(retrieved_at="2026-10-28T12:00:00"), observation(category="unproven_compliance_failure")]:
        response = client.post('/api/evidence-observations/import', json={'observations': [observation(), bad]})
        assert response.status_code == 422
        assert client.get('/api/evidence-observations').json()['total'] == 0
    assert client.post('/api/evidence-observations/import', json={'observations': []}).status_code == 422
    assert client.get('/api/evidence-observations?limit=201').status_code == 422


def test_database_error_rolls_back_entire_batch(client: TestClient):
    # A real SQLite constraint failure on the second insert must roll back the first.
    with client.app.state.test_engine.begin() as connection:
        connection.execute(text("""CREATE TRIGGER reject_second_observation
            BEFORE INSERT ON evidence_observations
            WHEN NEW.source_reference = 'reject-me'
            BEGIN SELECT RAISE(ABORT, 'test failure'); END"""))
    response = client.post('/api/evidence-observations/import', json={
        'observations': [observation(), observation(source_reference='reject-me')],
    })
    assert response.status_code == 500
    assert client.get('/api/evidence-observations').json()['total'] == 0


def test_thousand_records_import_and_page_without_duplication(client: TestClient):
    batch = [observation(source_reference=f"record-{number}") for number in range(1000)]
    assert client.post('/api/evidence-observations/import', json={'observations': batch}).json() == {'imported': 1000, 'duplicates': 0}
    assert client.post('/api/evidence-observations/import', json={'observations': batch}).json() == {'imported': 0, 'duplicates': 1000}
    assert client.post('/api/evidence-observations/import', json={'observations': batch + [observation()]}).status_code == 422
    page = client.get('/api/evidence-observations/accounts/GB-COH:12345678?limit=200&offset=800').json()
    assert page['total'] == 1000 and len(page['observations']) == 200
