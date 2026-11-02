from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.ingestion.market_find_tender import record_for_release, relevant_release
from app.models.market_network import MarketSourceState, SourceRevision
from app.services.market_monitor import MonitorBusy, run_find_tender_window

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def release(i='123456', title='Fire alarm maintenance', supplier='Demo Ltd'):
    return {'id': f'{i}-2026', 'ocid': f'ocds-h6vhtk-{i}', 'date': '2026-10-27T12:00:00Z',
            'tag': ['award'], 'tender': {'title': title},
            'buyer': {'id': 'b', 'name': 'Council'},
            'parties': [{'id': 's', 'name': supplier, 'identifier': {'scheme': 'GB-COH', 'id': '12345678'},
                         'contactPoint': {'name': 'Private person', 'email': 'name@example.com'}}],
            'awards': [{'id': 'award-1', 'status': 'active', 'suppliers': [{'id': 's', 'name': supplier}]}]}


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    from app.models.market_network import MarketAward, MarketEntity
    Base.metadata.create_all(engine, tables=[MarketSourceState.__table__, SourceRevision.__table__, MarketEntity.__table__, MarketAward.__table__])
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_filter_and_redaction_are_conservative():
    assert relevant_release(release())
    assert relevant_release(release(title='CCTV support'))
    assert not relevant_release(release(title='General cleaning services'))
    r = record_for_release(release(), NOW)
    assert r['source_url'].endswith('/123456-2026')
    assert 'contactPoint' not in r['raw']['parties'][0]
    assert record_for_release({**release(), 'id': '../../example'}, NOW) is None
    assert record_for_release({**release(), 'date': 'invalid'}, NOW) is None


def test_incremental_page_checkpoint_and_failure_recovery(db):
    calls = []
    fail_second = True
    def handler(request):
        nonlocal fail_second
        cursor = request.url.params.get('cursor')
        calls.append((cursor, request.url.params.get('updatedFrom'), request.url.params.get('updatedTo')))
        if not cursor:
            return httpx.Response(200, json={'releases': [release(), release('123457', 'General cleaning')],
                                  'links': {'next': 'https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?cursor=YWJj'}})
        if fail_second:
            return httpx.Response(503, headers={'Retry-After': '90'})
        return httpx.Response(200, json={'releases': [release('123458', 'CCTV servicing')], 'links': {}})
    with client_for(handler) as client:
        with pytest.raises(httpx.HTTPStatusError) as error:
            run_find_tender_window(db, max_pages=2, client=client, now=NOW)
        assert error.value.response.headers['Retry-After'] == '90'
        state = db.get(MarketSourceState, 'find_a_tender')
        assert state.cursor == 'YWJj' and state.failure_count == 1 and state.last_error == 'HTTP 503'
        assert state.watermark is None and state.lease_token is None
        assert len(db.scalars(select(SourceRevision)).all()) == 1
        fail_second = False
        result = run_find_tender_window(db, max_pages=2, client=client, now=NOW + timedelta(minutes=1))
        assert result['new'] == 1 and not result['incomplete']
        state = db.get(MarketSourceState, 'find_a_tender')
        assert state.watermark.replace(tzinfo=UTC) == NOW
        assert state.cursor is None and state.failure_count == 0
        assert calls[0][1:] == calls[1][1:] == calls[2][1:]  # fixed window across retries
        assert len(db.scalars(select(SourceRevision)).all()) == 2


def test_unchanged_replay_and_corrected_record_keep_history(db):
    current = release()
    with client_for(lambda req: httpx.Response(200, json={'releases': [current], 'links': {}})) as client:
        first = run_find_tender_window(db, client=client, now=NOW)
        again = run_find_tender_window(db, client=client, now=NOW + timedelta(hours=1))
        assert first['new'] == 1 and again['unchanged'] == 1
        # A correction removing the sector term is retained because this is a known notice.
        current = release(title='Corrected title with no sector language')
        changed = run_find_tender_window(db, client=client, now=NOW + timedelta(hours=2))
        assert changed['changed'] == 1
        revisions = db.scalars(select(SourceRevision).order_by(SourceRevision.id)).all()
        assert len(revisions) == 2 and revisions[0].superseded_at is not None and revisions[1].superseded_at is None


def test_active_lease_prevents_two_workers(db):
    db.add(MarketSourceState(source_key='find_a_tender', lease_token='other', lease_until=NOW + timedelta(minutes=2)))
    db.commit()
    with pytest.raises(MonitorBusy):
        run_find_tender_window(db, now=NOW)


def test_pagination_url_must_stay_on_source(db):
    with client_for(lambda req: httpx.Response(200, json={'releases': [release()], 'links': {'next': 'https://attacker.invalid/?cursor=YWJj'}})) as client:
        with pytest.raises(ValueError):
            run_find_tender_window(db, client=client, now=NOW)
    assert not db.scalars(select(SourceRevision)).all()
    assert db.get(MarketSourceState, 'find_a_tender').last_error == 'ValueError'


def test_older_revision_remains_historical_without_replacing_latest(db):
    current = release()
    with client_for(lambda req: httpx.Response(200, json={'releases': [current], 'links': {}})) as client:
        first = run_find_tender_window(db, client=client, now=NOW)
        assert first['new'] == 1
        current = {**release(title='Fire alarm maintenance - earlier'), 'date': '2026-10-01T12:00:00Z'}
        older = run_find_tender_window(db, client=client, now=NOW + timedelta(hours=1))
        assert older['historical'] == 1
        revisions = db.scalars(select(SourceRevision).order_by(SourceRevision.id)).all()
        assert len(revisions) == 2
        assert revisions[0].superseded_at is None
        assert revisions[1].superseded_at is not None
        replay = run_find_tender_window(db, client=client, now=NOW + timedelta(hours=2))
        assert replay['unchanged'] == 1
        assert len(db.scalars(select(SourceRevision)).all()) == 2


def test_failed_page_rolls_back_records_and_checkpoint(db, monkeypatch):
    from app.services import market_monitor
    original = market_monitor.ingest_market_release
    def fail_after_first(session, record):
        if record['release_id'] == '123458-2026':
            raise RuntimeError('untrusted detail should not be persisted')
        return original(session, record)
    monkeypatch.setattr(market_monitor, 'ingest_market_release', fail_after_first)
    with client_for(lambda req: httpx.Response(200, json={'releases': [release(), release('123458')], 'links': {}})) as client:
        with pytest.raises(RuntimeError):
            run_find_tender_window(db, client=client, now=NOW)
    state = db.get(MarketSourceState, 'find_a_tender')
    assert state.last_error == 'RuntimeError' and state.watermark is None and state.cursor is None
    assert state.failure_count == 1 and state.lease_token is None
    assert not db.scalars(select(SourceRevision)).all()
