from copy import deepcopy
from datetime import UTC, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.models.market_network import MarketSourceState
from app.services.market_network import ingest_market_release
from app.services.market_opportunities import refresh_market_opportunities

NOW = datetime(2026, 10, 28, tzinfo=UTC)


def make_db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def record(key, ocid, title, desc, *, tag=None, status='planned'):
    raw={'id':key,'ocid':ocid,'tag':tag or ['planning'], 'buyer':{'name':'Public buyer'},
         'tender':{'title':title,'description':desc,'status':status}}
    return {'source_key':'find_a_tender','release_id':key,'ocid':ocid,'source_url':f'https://www.find-tender.service.gov.uk/Notice/{key}',
            'published_at':NOW,'retrieved_at':NOW,'raw':raw}


def test_planning_deduplicates_revisions_and_review_stays_separate_from_truth():
    with make_db() as db:
        first=record('100-2026','ocds-planning','CCTV maintenance','Maintain and service CCTV systems')
        second=deepcopy(first); second.update(release_id='101-2026', published_at=NOW+timedelta(hours=1)); second['raw']['id']='101-2026'
        ingest_market_release(db, first); ingest_market_release(db, second)
        assert refresh_market_opportunities(db,now=NOW)['candidates'] == 1
        item=db.scalar(select(MarketOpportunity)); item.review_state='investigate'
        assert refresh_market_opportunities(db,now=NOW)['new_versions'] == 0
        assert len(db.scalars(select(MarketOpportunity)).all()) == len(db.scalars(select(MarketOpportunityRevision)).all()) == 1
        proposal=db.get(MarketOpportunityRevision,item.current_revision_id).result
        assert proposal['evidence'][0]['record_key'] == '101-2026'
        assert 'may exist' in proposal['inference']
        assert item.review_state == 'investigate'


def test_renewal_requires_matching_published_contract_not_alarm_replacement_and_retracts():
    with make_db() as db:
        renewal=record('100-2026','ocds-renewal','Fire alarm maintenance','Routine fire alarm maintenance and inspections',tag=['award'],status='complete')
        renewal['raw']['awards']=[{'id':'1','suppliers':[{'id':'a','name':'Published Supplier'}]}]
        renewal['raw']['contracts']=[{'id':'c1','awardID':'1','status':'active','period':{'endDate':'2027-10-01T00:00:00Z'}}]
        replacement=record('101-2026','ocds-replace','Replacement of Roland Levinsky Fire Alarm','Replacement and upgrade of existing fire alarm panels',tag=['award'],status='complete')
        replacement['raw']['awards']=[{'id':'1','suppliers':[{'id':'a','name':'Supplier'}]}]
        replacement['raw']['contracts']=[{'id':'c1','awardID':'1','status':'active','period':{'endDate':'2027-07-31T00:00:00Z'}}]
        ingest_market_release(db,renewal); ingest_market_release(db,replacement)
        assert refresh_market_opportunities(db,now=NOW)['candidates'] == 1
        item=db.scalar(select(MarketOpportunity)); revision=db.get(MarketOpportunityRevision,item.current_revision_id)
        assert revision.result['kind'] == 'possible_renewal_window'
        assert revision.result['supplier'] == 'Published Supplier'
        assert any('currently delivers' in text for text in revision.result['unknowns'])
        changed=deepcopy(renewal); changed['published_at']=changed['retrieved_at']=NOW+timedelta(days=1)
        changed['raw']['contracts'][0]['status']='terminated'
        ingest_market_release(db,changed)
        assert refresh_market_opportunities(db,now=NOW+timedelta(days=1))['withdrawn'] == 1
        assert item.state == 'withdrawn' and db.get(MarketOpportunityRevision,item.current_revision_id).id == revision.id


def test_unmatched_contract_and_irrelevant_wording_do_not_generate_suggestions():
    with make_db() as db:
        for key,title,desc in [('1-2026','Electrical wiring','Fire exits maintained by others.'),
                               ('2-2026','Fire alarm replacement','Upgrade of existing fire alarm panels.')]:
            r=record(key,'ocds-'+key,title,desc,tag=['award'],status='complete')
            r['raw']['awards']=[{'id':'1'}]; r['raw']['contracts']=[{'id':'a','awardID':'different','period':{'endDate':'2027-01-01T00:00:00Z'}}]
            ingest_market_release(db,r)
        assert refresh_market_opportunities(db,now=NOW)['candidates'] == 0


def test_historical_deadlines_and_undated_old_notices_are_not_current_suggestions():
    with make_db() as db:
        for key in ('1-2026', '2-2026'):
            r=record(key,'ocds-'+key,'Fire alarm maintenance','Maintenance of fire alarms')
            r['published_at']=r['retrieved_at']=NOW-timedelta(days=365)
            if key == '1-2026':
                r['raw']['tender']['tenderPeriod']={'endDate':'2025-01-01T00:00:00Z'}
            ingest_market_release(db,r)
        assert refresh_market_opportunities(db,now=NOW)['candidates'] == 0


def test_framework_appointment_not_treated_as_a_supplier_maintenance_contract():
    with make_db() as db:
        r=record('1-2026','ocds-framework','Fire alarm maintenance framework','Maintenance of fire alarms',tag=['award'],status='complete')
        r['raw']['tender']['techniques']={'hasFrameworkAgreement': True}
        r['raw']['awards']=[{'id':'1','suppliers':[{'id':'a','name':'Supplier'}]}]
        r['raw']['contracts']=[{'id':'c1','awardID':'1','period':{'endDate':'2027-01-01T00:00:00Z'}}]
        ingest_market_release(db,r)
        assert refresh_market_opportunities(db,now=NOW)['candidates'] == 0


def test_truncated_scan_does_not_withdraw_unseen_and_api_supports_review():
    with make_db() as db:
        r=record('1-2026','ocds-a','Fire alarm maintenance','Maintenance of fire alarms')
        ingest_market_release(db,r); refresh_market_opportunities(db,now=NOW); db.commit()
        item=db.scalar(select(MarketOpportunity))
        ingest_market_release(db,record('2-2026','ocds-b','CCTV maintenance','Maintenance of CCTV systems'))
        assert refresh_market_opportunities(db,now=NOW,max_sources=1)['complete_scan'] is False
        assert item.state == 'suggested'
        db.commit()
        app=create_app(); app.dependency_overrides[get_db]=lambda: db
        with TestClient(app) as client:
            assert client.get('/api/market-network/opportunities').json()['total'] == 2
            assert client.patch(f'/api/market-network/opportunities/{item.id}/review',json={'review_state':'dismiss'}).status_code == 200
            assert client.patch(f'/api/market-network/opportunities/{item.id}/review',json={'review_state':'buy'}).status_code == 422
            assert client.get(f'/api/market-network/opportunities/{item.id}/history').json()['items']


def test_source_summary_separates_operational_checkpoint_lanes():
    with make_db() as db:
        for key in ('find_a_tender', 'contracts_finder', 'public_contracts_scotland',
                    'contracts_finder_backfill_2024', 'pcs_2024_01_3', 'market_backfill_budget'):
            db.add(MarketSourceState(source_key=key))
        db.commit()
        app=create_app(); app.dependency_overrides[get_db]=lambda: db
        with TestClient(app) as client:
            result=client.get('/api/market-network/summary').json()
            assert {row['source_key'] for row in result['sources']} == {'find_a_tender', 'contracts_finder', 'public_contracts_scotland'}
            assert {row['source_key'] for row in result['checkpoint_lanes']} == {'contracts_finder_backfill_2024', 'pcs_2024_01_3', 'market_backfill_budget'}
