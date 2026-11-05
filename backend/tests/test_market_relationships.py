from copy import deepcopy
from datetime import UTC, datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.main import create_app
from app.models.market_graph import MarketRelationship
from app.models.market_network import MarketEntity, SourceRevision
from app.services.market_relationships import ingest_reviewed_psc_snapshot
import pytest


def sample():
    return {'company_number':'12345678','company_name':'Example company',
            'source_url':'https://find-and-update.company-information.service.gov.uk/company/12345678/persons-with-significant-control',
            'retrieved_at':'2026-10-28T12:00:00Z','controllers':[
              {'company_number':'87654321','company_name':'Old Holdings','notified_on':'2019-01-01','ceased_on':'2024-01-01','nature_of_control':['Ownership of shares – 75% or more']},
              {'company_number':'12340000','company_name':'New Holdings','notified_on':'2024-01-01','nature_of_control':['Ownership of shares – 75% or more']} ]}


def test_replay_history_and_temporal_queries():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert ingest_reviewed_psc_snapshot(db,sample())['relationships_created']==2
        assert ingest_reviewed_psc_snapshot(db,sample())['relationships_created']==0
        assert len(db.scalars(select(MarketEntity)).all())==3
        assert len(db.scalars(select(MarketRelationship)).all())==2
        db.commit()
        app=create_app(); app.dependency_overrides[get_db]=lambda:db
        with TestClient(app) as client:
            before=client.get('/api/market-network/relationships',params={'as_of':'2022-06-01'}).json()
            after=client.get('/api/market-network/relationships',params={'as_of':'2025-06-01'}).json()
            assert [x['object'] for x in before['items']]==['Old Holdings']
            assert [x['object'] for x in after['items']]==['New Holdings']
            assert before['items'][0]['source_url']==sample()['source_url']
            assert 'cached' in ' '.join(before['limitations'])
        update=deepcopy(sample());update['retrieved_at']='2026-10-29T12:00:00Z';update['controllers'][1]['ceased_on']='2026-10-29'
        assert ingest_reviewed_psc_snapshot(db,update)['state']=='changed'
        assert len(db.scalars(select(SourceRevision)).all())==2
        assert len(db.scalars(select(MarketRelationship)).all())==4


def test_rejects_unidentified_controllers_and_untrusted_source():
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        bad=sample();bad['source_url']='https://example.test/not-a-registry'
        with pytest.raises(ValueError): ingest_reviewed_psc_snapshot(db,bad)
        bad=sample();bad['controllers'][0]['company_number']='not-a-number'
        with pytest.raises(ValueError): ingest_reviewed_psc_snapshot(db,bad)
