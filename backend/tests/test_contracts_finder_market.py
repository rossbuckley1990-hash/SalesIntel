from datetime import UTC, datetime, timedelta
import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db import Base
from app.models.market_network import MarketAward, MarketEntity, MarketSourceState, SourceRevision
from app.ingestion.market_contracts_finder import fetch_page, record_for_release
from app.services.market_contracts_monitor import SourceCooldown, run_contracts_finder_window

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def release(n='000001', title='Fire alarm maintenance'):
    return {'id': 'dd7c15a1-91b6-44e2-b14a-adb7449c495b-' + n,
            'ocid': 'ocds-b5fd17-0808a8ff-1fb1-4d44-878c-14699b5955b7',
            'date': '2024-01-02T23:39:52Z', 'tag': ['award'], 'tender': {'title': title},
            'buyer': {'name':'Council'}, 'parties': [{'id':'s','identifier':{'scheme':'GB-COH','id':'12345678'},'contactPoint':{'email':'private'}}],
            'awards':[{'id':'a','suppliers':[{'id':'s','name':'Firm Ltd'}]}]}


@pytest.fixture
def db():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[MarketSourceState.__table__, SourceRevision.__table__, MarketEntity.__table__, MarketAward.__table__])
    with Session(engine,expire_on_commit=False) as session:
        yield session
    engine.dispose()


def test_release_url_privacy_and_offsite_pagination_rejection():
    record=record_for_release(release(),NOW)
    assert record['source_url']=='https://www.contractsfinder.service.gov.uk/Notice/dd7c15a1-91b6-44e2-b14a-adb7449c495b'
    assert 'contactPoint' not in record['raw']['parties'][0]
    assert record_for_release({**release(),'id':'../../path'},NOW) is None
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'releases':[], 'links':{'next':'https://attacker.test/?cursor=YWJj'}})))
    with client, pytest.raises(ValueError,match='Unexpected'):
        fetch_page(updated_from=NOW-timedelta(days=1),updated_to=NOW,client=client)


def test_failure_cooldown_persisted_then_cursor_resumes(db):
    fail=True
    calls=[]
    def handler(req):
        nonlocal fail
        calls.append(dict(req.url.params))
        if not req.url.params.get('cursor'):
            return httpx.Response(200,json={'releases':[release()], 'links':{'next':'https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search?cursor=YWJj'}})
        if fail:
            return httpx.Response(403)
        return httpx.Response(200,json={'releases':[release('000002')], 'links':{}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first=run_contracts_finder_window(db,client=client,now=NOW,start_at=datetime(2024,1,1,tzinfo=UTC),end_at=datetime(2024,2,1,tzinfo=UTC),state_key='contracts_finder_backfill_2024')
        assert first['new']==1 and first['incomplete']
        with pytest.raises(httpx.HTTPStatusError):
            run_contracts_finder_window(db,client=client,now=NOW+timedelta(seconds=4),state_key='contracts_finder_backfill_2024')
        assert db.get(MarketSourceState,'contracts_finder').last_error=='HTTP 403'
        # The live lane shares the source cooldown after a backfill failure.
        with pytest.raises(SourceCooldown) as exc:
            run_contracts_finder_window(db,client=client,now=NOW+timedelta(seconds=10))
        assert exc.value.retry_after_seconds > 290
        fail=False
        recovered=run_contracts_finder_window(db,client=client,now=NOW+timedelta(minutes=6),state_key='contracts_finder_backfill_2024')
        assert recovered['new']==1 and not recovered['incomplete']
        assert db.get(MarketSourceState,'contracts_finder_backfill_2024').watermark.replace(tzinfo=UTC)==datetime(2024,2,1,tzinfo=UTC)
        assert len(db.scalars(select(SourceRevision)).all())==2
        assert calls[0]['publishedFrom']==calls[1]['publishedFrom']==calls[2]['publishedFrom']
