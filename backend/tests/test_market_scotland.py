from datetime import UTC,datetime,timedelta
import httpx
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.db import Base
from app.ingestion.market_scotland import record_for_release
from app.models.market_network import MarketAward,MarketEntity,MarketSourceState,SourceRevision
from app.services.market_scotland_monitor import run_scotland_month

NOW=datetime(2026,10,28,tzinfo=UTC)


def release(index=1,title='Fire alarm maintenance'):
    return {'id':f'rls-{index}-JAN497115','ocid':'ocds-r6ebe6-0000743351','date':'2024-01-24T00:00:00Z',
            'tender':{'title':title},'buyer':{'name':'Council'},
            'parties':[{'id':'s','contactPoint':{'email':'private@example.test'}}],
            'awards':[{'id':'1','suppliers':[{'id':'s','name':'Contractor Ltd'}]}]}


@pytest.fixture
def db():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine,tables=[MarketSourceState.__table__,SourceRevision.__table__,MarketEntity.__table__,MarketAward.__table__])
    with Session(engine,expire_on_commit=False) as session: yield session
    engine.dispose()


def test_record_validates_identifier_and_redacts_contact():
    r=record_for_release(release(),NOW)
    assert r['release_id']=='JAN497115'
    assert r['source_url']=='https://www.publiccontractsscotland.gov.uk/search/show/search_view.aspx?ID=JAN497115'
    assert r['raw']['id']=='JAN497115'
    assert 'contactPoint' not in r['raw']['parties'][0]
    assert record_for_release({**release(),'id':'../../foo'},NOW) is None


def test_month_replay_idempotent_then_correction_retains_history(db):
    current=release()
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'releases':[current]}))) as client:
        assert run_scotland_month(db,year=2024,month=1,client=client,now=NOW)['new']==1
        current=release(index=9) # publisher package index is not identity
        assert run_scotland_month(db,year=2024,month=1,client=client,now=NOW+timedelta(days=1))['unchanged']==1
        current=release(index=5,title='Fire alarm maintenance corrected')
        assert run_scotland_month(db,year=2024,month=1,client=client,now=NOW+timedelta(days=2))['changed']==1
    records=db.scalars(select(SourceRevision).order_by(SourceRevision.id)).all()
    assert len(records)==2 and records[0].superseded_at is not None and records[1].superseded_at is None
    assert db.get(MarketSourceState,'pcs_2024_01_3').watermark is not None


def test_bad_response_retains_failed_state(db):
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(503))) as client:
        for i in range(3):
            with pytest.raises(httpx.HTTPStatusError):
                run_scotland_month(db,year=2024,month=1,client=client,now=NOW+timedelta(days=i))
    assert db.get(MarketSourceState,'public_contracts_scotland').last_error=='HTTP 503'
    assert db.get(MarketSourceState,'pcs_2024_01_3').failure_count==3
    assert not db.scalars(select(SourceRevision)).all()
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'releases':[release()]}))) as client:
        assert run_scotland_month(db,year=2024,month=1,client=client,now=NOW+timedelta(days=4))['new']==1
    assert db.get(MarketSourceState,'pcs_2024_01_3').failure_count==0
