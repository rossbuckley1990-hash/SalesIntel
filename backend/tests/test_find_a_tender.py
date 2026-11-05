from datetime import UTC, datetime, timedelta

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import Base, create_database_engine, get_db
from app.ingestion.find_a_tender import fetch_batch, parse_release
from app.routers import public_sources

NOW = datetime(2026, 10, 28, 14, tzinfo=UTC)


def release(**changes):
    return {'id': '123456-2026', 'ocid': 'ocds-h6vhtk-123456', 'date': '2026-10-25T15:15:00Z',
            'tag': ['award', 'contract'], 'buyer': {'id': 'GB-PPON-AAA', 'name': 'Example Council'},
            'parties': [{'id': 'GB-PPON-AAA', 'identifier': {'scheme': 'GB-PPON', 'id': 'AAA'},
                         'address': {'locality': 'York', 'postalCode': 'YO1 1AA'}}],
            'tender': {'title': 'Fire alarm maintenance', 'description': 'Inspection and service'}, **changes}


def test_extraction_is_source_linked_and_does_not_invent_site_or_failure():
    item = parse_release(release(), NOW)
    assert item.organisation_id == 'GB-PPON:AAA'
    assert item.site == 'Unknown'
    assert item.source_url == 'https://www.find-tender.service.gov.uk/Notice/123456-2026'
    assert 'buyer address' in item.observed_statement
    assert 'does not establish present demand' in item.observed_statement
    assert item.published_at.isoformat() == '2026-10-25'
    assert parse_release(release(tag=['tender']), NOW) is None
    assert parse_release(release(parties=[]), NOW) is None
    assert parse_release(release(id='https://evil.example'), NOW) is None
    assert parse_release(release(tender={'title': 'Catering services'}), NOW) is None
    assert parse_release(release(tender={'title': 'Catering services'}), NOW, ['catering']) is not None


def test_pagination_is_bounded_and_uses_frozen_window():
    requests = []
    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={'releases': [release()], 'links': {'next': 'https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?cursor=YWJj'}})
        return httpx.Response(200, json={'releases': [release(id='123457-2026')], 'links': {}})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        observations, scanned, pages, cursor = fetch_batch(updated_from=NOW-timedelta(days=1), updated_to=NOW, max_pages=2, client=client)
    assert (len(observations), scanned, pages, cursor) == (2, 2, 2, None)
    assert requests[1].url.params['cursor'] == 'YWJj'
    assert requests[0].url.params['updatedTo'] == requests[1].url.params['updatedTo']


def test_rejects_untrusted_next_url():
    def respond(request):
        return httpx.Response(200, json={'releases': [], 'links': {'next': 'https://evil.example/api/1.0/ocdsReleasePackages?cursor=YWJj'}})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        import pytest
        with pytest.raises(ValueError):
            fetch_batch(updated_from=NOW-timedelta(days=1), updated_to=NOW, client=client)


def test_refresh_is_idempotent_and_validation_and_failed_fetch_do_not_write(tmp_path, monkeypatch):
    engine = create_database_engine(f'sqlite:///{tmp_path / "isolated.db"}')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(public_sources.router)
    def db_override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(public_sources, 'fetch_batch', lambda **kw: ([parse_release(release(), NOW)], 100, 1, None))
    with TestClient(app) as client:
        first = client.post('/api/public-sources/find-a-tender/refresh', json={})
        second = client.post('/api/public-sources/find-a-tender/refresh', json={})
        assert first.status_code == 200 and first.json()['imported'] == 1
        assert second.json()['duplicates'] == 1
        assert client.post('/api/public-sources/find-a-tender/refresh', json={'cursor': 'YWJj'}).status_code == 422
        assert client.post('/api/public-sources/find-a-tender/refresh', json={'max_pages': 11}).status_code == 422
        def bad(**kw):
            raise ValueError('broken upstream')
        monkeypatch.setattr(public_sources, 'fetch_batch', bad)
        assert client.post('/api/public-sources/find-a-tender/refresh', json={}).status_code == 502
        from app.models.evidence_observation import EvidenceObservation
        with factory() as session:
            assert session.query(EvidenceObservation).count() == 1
    engine.dispose()
