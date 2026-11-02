from copy import deepcopy
from datetime import UTC, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.models.market_network import MarketAward, MarketEntity, MarketEntityEvidence, SourceRevision
from app.services.market_network import ingest_market_company, ingest_market_release

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def record(release_id='notice-1'):
    return {'source_key': 'find_a_tender', 'release_id': release_id, 'ocid': 'ocds-1',
        'source_url': 'https://www.find-tender.service.gov.uk/Notice/1', 'retrieved_at': NOW,
        'published_at': NOW, 'raw': {'id': release_id, 'ocid': 'ocds-1',
        'tender': {'title': 'Fire alarm maintenance'}, 'buyer': {'name': 'Public buyer', 'contactPoint': {'email': 'private@example.test'}},
        'parties': [{'id': 'supplier-1', 'identifier': {'scheme': 'GB-COH', 'id': '12345678'},
                     'contactPoint': {'email': 'private@example.test'}}],
        'awards': [{'id':'award-1', 'status':'active', 'date':'2025-12-01',
                    'value': {'amount': 1000, 'currency':'GBP'}, 'suppliers': [{'id':'supplier-1', 'name':'Example Ltd'}]}]}}


def make_db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_idempotency_change_history_and_no_contact_retention():
    with make_db() as db:
        first = record()
        assert ingest_market_release(db, first)['state'] == 'new'
        assert ingest_market_release(db, first)['state'] == 'unchanged'
        changed = deepcopy(first)
        changed['retrieved_at'] = NOW + timedelta(days=1)
        changed['raw']['awards'][0]['value']['amount'] = 1200
        assert ingest_market_release(db, changed)['state'] == 'changed'
        sources = db.scalars(select(SourceRevision).order_by(SourceRevision.id)).all()
        assert len(sources) == 2 and sources[0].superseded_at is not None and sources[1].superseded_at is None
        assert len(db.scalars(select(MarketAward)).all()) == 2
        assert len(db.scalars(select(MarketEntity)).all()) == 1
        assert 'private@example.test' not in str(sources[0].raw)


def test_names_do_not_merge_and_companies_house_record_proves_identity_only():
    with make_db() as db:
        first = record()
        first['raw']['parties'][0].pop('identifier')
        second = deepcopy(first)
        second['release_id'] = 'notice-2'
        second['raw']['id'] = 'notice-2'
        ingest_market_release(db, first)
        ingest_market_release(db, second)
        assert len(db.scalars(select(MarketEntity)).all()) == 2
        ch = {'source_key':'companies_house', 'release_id':'12345678', 'source_url':'https://find-and-update.company-information.service.gov.uk/company/12345678',
              'retrieved_at':NOW, 'raw': {'company_number':'12345678', 'company_name':'Example Ltd', 'company_status':'active',
                                          'officers':[{'name':'A Person'}]}}
        assert ingest_market_company(db, ch)['state'] == 'new'
        assert ingest_market_company(db, ch)['state'] == 'unchanged'
        assert len(db.scalars(select(MarketEntity)).all()) == 3
        assert len(db.scalars(select(MarketEntityEvidence)).all()) == 1
        source = db.scalar(select(SourceRevision).where(SourceRevision.source_key == 'companies_house'))
        assert 'officers' not in source.raw


def test_official_number_joins_without_name_matching_and_read_api_labels_limitations():
    with make_db() as db:
        ingest_market_release(db, record())
        ch = {'source_key':'companies_house', 'release_id':'12345678', 'source_url':'https://find-and-update.company-information.service.gov.uk/company/12345678',
              'retrieved_at':NOW, 'raw': {'company_number':'12345678', 'company_name':'Example Legal Limited'}}
        ingest_market_company(db, ch)
        db.commit()
        assert len(db.scalars(select(MarketEntity)).all()) == 1
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            summary = client.get('/api/market-network/summary').json()
            assert summary['companies'] == summary['verified_companies'] == summary['awards'] == 1
            assert 'not proof of current delivery' in ' '.join(summary['limitations'])
            award = client.get('/api/market-network/awards').json()['items'][0]
            assert award['classification'] == 'unknown'
            assert client.get(f"/api/market-network/sources/{award['source_revision_id']}").json()['raw']['awards'][0]['id'] == 'award-1'
            assert client.get('/api/market-network/companies/999/sources').status_code == 404


def test_out_of_order_revisions_preserve_latest_snapshot_and_do_not_duplicate_history():
    with make_db() as db:
        recent = record()
        recent['published_at'] = NOW + timedelta(days=5)
        recent['raw']['awards'][0]['value']['amount'] = 2000
        ingest_market_release(db, recent)
        older = record()
        older['published_at'] = NOW
        older['retrieved_at'] = NOW + timedelta(days=6)
        assert ingest_market_release(db, older)['state'] == 'historical'
        assert ingest_market_release(db, older)['state'] == 'unchanged'
        revisions = db.scalars(select(SourceRevision)).all()
        assert len(revisions) == 2
        current = next(r for r in revisions if r.superseded_at is None)
        assert current.raw['awards'][0]['value']['amount'] == 2000
