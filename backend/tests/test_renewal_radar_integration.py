"""The integrated radar, run on real published records of the named cases."""
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.ingestion.market_find_tender_radar import monitored
from app.ingestion.market_scotland import fetch_month
from app.main import create_app
from app.models import MarketSignal, Opportunity
from app.models.market_contract import MarketContract
from app.models.market_network import MarketSourceState, SourceRevision
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.services.market_network import ingest_market_release
from app.services.market_opportunities import refresh_market_opportunities
from app.services.market_scotland_monitor import run_scotland_current
from app.services.renewal_history import import_checkpoints, search_record, tender_records
from app.services.renewal_radar import export_csv, radar_summary, refresh_if_due, run_daily_cycle, selective_weeks, source_health

NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)
CASES = json.loads((Path(__file__).parent / 'fixtures' / 'renewal_radar_named_cases.json').read_text())


def make_db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def load(db, records):
    for item in records:
        ingest_market_release(db, {**item, 'retrieved_at': NOW, 'published_at': datetime.fromisoformat(str(item['published_at'])).replace(tzinfo=UTC)})
    db.commit()


def proposals(db):
    rows = db.execute(select(MarketOpportunity, MarketOpportunityRevision).join(MarketOpportunityRevision, MarketOpportunity.current_revision_id == MarketOpportunityRevision.id)
                      .where(MarketOpportunity.state == 'suggested')).all()
    return [version.result for _, version in rows]


@pytest.fixture
def named():
    with make_db() as db:
        load(db, CASES)
        refresh_market_opportunities(db, now=NOW)
        db.commit()
        yield db


def find(db, buyer, title):
    return [x for x in proposals(db) if buyer in x['customer'].lower() and title in x['title'].lower()]


def test_leicester_city_council_contract_is_a_correct_renewal(named):
    item = find(named, 'leicester city', 'fire & intruder alarm')[0]
    assert item['category'] == 'pre_tender' and item['fit'] == 'core' and 'Churches Fire' in item['supplier'] and item['timing'] == '2027-03-31' and item['end_estimated'] is False


def test_torus_group_contracts_keep_their_own_incumbents(named):
    equipment, access = find(named, 'torus group', 'fire equipment')[0], find(named, 'torus group', 'access control')[0]
    assert 'Fieldway' in equipment['supplier'] and 'OpenView' in access['supplier'] and equipment['timing'] == access['timing'] == '2027-10-31'


def test_torus62_framework_is_not_an_individual_renewal(named):
    assert not find(named, 'torus62', 'passive fire')
    framework = named.scalars(select(MarketContract).where(MarketContract.buyer.ilike('torus62%'))).all()
    assert framework and all(x.category is None for x in framework)


def test_orbit_group_emergency_lighting_is_no_longer_rejected(named):
    item = find(named, 'orbit', 'emergency lighting services')[0]
    assert item['fit'] == 'core' and 'McIntyre' in item['supplier'] and item['timing'] == '2027-03-20'


def test_broadmoor_is_contract_defence_for_mitie_security(named):
    item = find(named, 'west london', 'broadmoor')[0]
    assert item['category'] == 'contract_defence' and item['supplier'] == 'Mitie Security Limited' and item['priority']['tier'] == 1
    assert item['next_actions'][0].startswith('Escalate')


def test_rheinmetall_vehicle_fire_suppression_is_excluded(named):
    assert not [x for x in proposals(named) if 'rheinmetall' in (x['supplier'] or '').lower()]


def test_university_of_plymouth_boden_replacement_is_excluded(named):
    assert not find(named, 'university of plymouth', 'roland levinsky')


def award(key, ocid, source='find_a_tender', title='Fire alarm servicing and maintenance', buyer='Example Council', supplier='Acme Fire Ltd', end='2027-06-30', value=300000, number=None, published=None):
    party = [{'id': f'GB-COH-{number}', 'identifier': {'scheme': 'GB-COH', 'id': number}}] if number else []
    raw = {'id': key, 'ocid': ocid, 'date': '2024-07-01T00:00:00Z', 'tag': ['award'], 'buyer': {'name': buyer}, 'parties': party, 'tender': {'title': title, 'status': 'complete'},
           'awards': [{'id': '1', 'status': 'active', 'value': {'amount': value, 'currency': 'GBP'}, 'contractPeriod': {'startDate': '2024-07-01', 'endDate': end},
                       'suppliers': [{'id': f'GB-COH-{number}' if number else 's', 'name': supplier}]}]}
    url = 'https://www.find-tender.service.gov.uk/Notice/' + key if source == 'find_a_tender' else 'https://www.contractsfinder.service.gov.uk/Notice/' + key
    return {'source_key': source, 'release_id': key, 'ocid': ocid, 'source_url': url, 'published_at': published or datetime(2024, 7, 1, tzinfo=UTC), 'retrieved_at': NOW, 'raw': raw}


def test_same_contract_on_two_sources_gives_one_suggestion_with_both_records():
    with make_db() as db:
        load(db, [award('000001-2024', 'ocds-h6vhtk-000001'), award('11111111-0000-4000-8000-000000000001-1', 'ocds-b5fd17-11111111-0000-4000-8000-000000000001', 'contracts_finder')])
        assert refresh_market_opportunities(db, now=NOW)['candidates'] == 1
        item = proposals(db)[0]
        assert item['link']['sources'] == ['Contracts Finder', 'Find a Tender'] and item['link']['confidence'] == 'strong' and db.scalar(select(func.count()).select_from(MarketContract)) == 1


def test_a_buyer_acting_for_another_body_is_the_same_buyer():
    with make_db() as db:
        load(db, [award('000001-2024', 'ocds-h6vhtk-000001', buyer='Cheshire Constabulary'), award('77777777-0000-4000-8000-000000000001-1', 'ocds-b5fd17-77777777-0000-4000-8000-000000000001', 'contracts_finder', buyer='Cheshire Constabulary on behalf of Cheshire Fire Authority')])
        assert refresh_market_opportunities(db, now=NOW)['candidates'] == 1


def test_a_similar_title_with_a_different_supplier_is_not_merged():
    with make_db() as db:
        load(db, [award('000001-2024', 'ocds-h6vhtk-000001'), award('22222222-0000-4000-8000-000000000001-1', 'ocds-b5fd17-22222222-0000-4000-8000-000000000001', 'contracts_finder', supplier='Other Alarms Ltd')])
        assert refresh_market_opportunities(db, now=NOW)['candidates'] == 2


def test_contract_keeps_its_key_and_review_when_a_second_source_arrives():
    with make_db() as db:
        load(db, [award('000001-2024', 'ocds-h6vhtk-000001')])
        refresh_market_opportunities(db, now=NOW)
        item = db.scalar(select(MarketOpportunity))
        item.review_state = 'investigate'
        load(db, [award('33333333-0000-4000-8000-000000000001-1', 'ocds-b5fd17-33333333-0000-4000-8000-000000000001', 'contracts_finder')])
        refresh_market_opportunities(db, now=NOW + timedelta(days=1))
        assert db.scalar(select(func.count()).select_from(MarketOpportunity)) == 1 and item.review_state == 'investigate' and item.state == 'suggested'


def test_a_title_match_is_only_a_possible_replacement_and_needs_verifying():
    with make_db() as db:
        newer = award('000002-2026', 'ocds-h6vhtk-000002', title='Fire alarm maintenance contract', supplier='New Fire Ltd', end='2030-06-30', published=datetime(2026, 6, 1, tzinfo=UTC))
        newer['raw']['date'] = '2026-06-01T00:00:00Z'
        load(db, [award('000001-2024', 'ocds-h6vhtk-000001'), newer])
        refresh_market_opportunities(db, now=NOW)
        item = next(x for x in proposals(db) if x['timing'] == '2027-06-30') if any(x['timing'] == '2027-06-30' for x in proposals(db)) else None
        assert item and item['category'] == 'verify_first' and item['replacement']['status'] == 'possible' and 'not a confirmed replacement' in item['counter_evidence'][0]


def test_a_historical_award_is_stored_but_never_an_opportunity():
    with make_db() as db:
        load(db, [award('000001-2021', 'ocds-h6vhtk-000001', end='2025-06-30')])
        assert refresh_market_opportunities(db, now=NOW)['candidates'] == 0
        contract = db.scalar(select(MarketContract))
        assert contract.lifecycle_status == 'historical' and contract.category is None and contract.facts['currency'] == 'historical'


def test_an_extension_can_keep_a_passed_contract_on_the_list_for_checking():
    with make_db() as db:
        record = award('000001-2021', 'ocds-h6vhtk-000001', end='2025-06-30')
        record['raw']['awards'][0]['contractPeriod']['maxExtentDate'] = '2027-06-30'
        load(db, [record])
        refresh_market_opportunities(db, now=NOW)
        item = proposals(db)[0]
        assert item['category'] == 'verify_first' and item['latest_end'] == '2027-06-30' and 'extension has been exercised' in ' '.join(item['next_actions'])


def test_estimate_and_published_end_are_kept_apart_in_contract_facts():
    with make_db() as db:
        record = award('000001-2024', 'ocds-h6vhtk-000001')
        del record['raw']['awards'][0]['contractPeriod']['endDate']
        record['raw']['tender']['lots'] = [{'id': '1', 'contractPeriod': {'durationInDays': 1095}}]
        load(db, [record])
        refresh_market_opportunities(db, now=NOW)
        facts = db.scalar(select(MarketContract)).facts
        assert facts['published_end_date'] is None and facts['estimated_end_date'] == '2027-07-01' and facts['end_basis'] == 'tender_duration'


def test_values_are_never_blended():
    with make_db() as db:
        load(db, [award('000001-2024', 'ocds-h6vhtk-000001', value=300000)])
        refresh_market_opportunities(db, now=NOW)
        value = proposals(db)[0]['value']
        assert value['published_total'] == 300000 and value['estimated_annualised'] and value['published_annual'] is None and value['type'] == 'estimated_annualised'


def planning(key, ocid, expected, title='Fire alarm maintenance'):
    return {'source_key': 'find_a_tender', 'release_id': key, 'ocid': ocid, 'source_url': 'https://www.find-tender.service.gov.uk/Notice/' + key, 'published_at': NOW - timedelta(days=30), 'retrieved_at': NOW,
            'raw': {'id': key, 'ocid': ocid, 'tag': ['planning'], 'buyer': {'name': 'Example Council'}, 'tender': {'title': title, 'status': 'planned', 'communication': {'futureNoticeDate': expected}}}}


def test_official_signal_with_a_passed_date_is_demoted_and_says_so():
    with make_db() as db:
        load(db, [planning('000003-2026', 'ocds-h6vhtk-000003', '2027-03-01T00:00:00Z'), planning('000004-2026', 'ocds-h6vhtk-000004', '2026-10-01T00:00:00Z', 'CCTV maintenance')])
        refresh_market_opportunities(db, now=NOW)
        future, passed = sorted(proposals(db), key=lambda x: x['timing'], reverse=True)
        assert future['category'] == passed['category'] == 'official_early_signal' and future['priority']['tier'] == 1 and passed['priority']['tier'] == 2
        assert 'already been published' in passed['next_action']


def test_live_tender_and_framework_tender_are_live_procurement():
    with make_db() as db:
        record = planning('000005-2026', 'ocds-h6vhtk-000005', None, 'Fire alarm maintenance framework')
        record['raw'].update(tag=['tender'])
        record['raw']['tender'].update(status='active', tenderPeriod={'endDate': '2026-12-01T12:00:00Z'}, techniques={'hasFrameworkAgreement': True})
        load(db, [record])
        refresh_market_opportunities(db, now=NOW)
        item = proposals(db)[0]
        assert item['category'] == 'live_procurement' and item['fit'] == 'framework' and item['timing'] == '2026-12-01' and 'framework eligibility' in item['next_action']


def test_unrelated_sector_is_excluded():
    with make_db() as db:
        load(db, [award('000006-2024', 'ocds-h6vhtk-000006', title='Fire engine overhaul and vehicle repairs'), award('000007-2024', 'ocds-h6vhtk-000007', title='Catering services')])
        assert refresh_market_opportunities(db, now=NOW)['candidates'] == 0


def test_api_filters_exports_and_promotes_once(named):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: named
    with TestClient(app) as client:
        page = client.get('/api/market-network/opportunities', params={'category': 'contract_defence'}).json()
        assert page['total'] == 1 and 'Broadmoor' in page['items'][0]['suggestion']['title']
        assert client.get('/api/market-network/opportunities', params={'nation': 'Scotland'}).json()['total'] == 0
        assert client.get('/api/market-network/opportunities', params={'q': 'orbit', 'tier': 1}).status_code == 200
        summary = client.get('/api/market-network/opportunities/summary').json()
        assert summary['by_category']['contract_defence'] == 1 and summary['limits'] and {'3', '6', '12', '18'} == set(summary['renewals_within_months'])
        csv_text = client.get('/api/market-network/opportunities/export.csv').text
        assert csv_text.startswith('tier,category,nation') and 'Broadmoor' in csv_text
        item = page['items'][0]['id']
        first, second = client.post(f'/api/market-network/opportunities/{item}/promote').json(), client.post(f'/api/market-network/opportunities/{item}/promote').json()
        assert first['created'] is True and second == {'opportunity_id': first['opportunity_id'], 'created': False}
        assert named.scalar(select(func.count()).select_from(MarketSignal)) == 1 and named.get(Opportunity, first['opportunity_id']).buyer_name.startswith('West London')


@pytest.mark.parametrize('title,description,suppliers', [
    ('Provision of On Train Wi-Fi maintenance and software support', 'Maintenance of CCTV on trains.', ['Icomera UK Limited']),
    ('Partial window renewal, external decorations and repairs at Alton Estate', 'Includes replacement fire doors.', ['Mulalley and Company Limited']),
    ('Lift Maintenance and Servicing', '24/7 helpdesk and callout service including alarm monitoring.', ['Liftec Express Limited']),
    ('Provision of an Alarm Receiving Centre with Disaster Recovery', 'Upgrade the current Telecare Alarm Receiving Centre.', ['E.novation']),
    ('Fire Risk Assessment, Door Inspection and Fire Door Service', 'Annual fire risk assessment.', ['Procedure discontinued']),
    ('HMPPS Exeter-Perimeter Wall Repairs, Gas Main Replacement, CCTV Replacement and Kitchen Dampers', '', ['Galliford Try Construction Ltd']),
    ('PLACE131 Design, Supply, Installation and Maintenance of Intelligent Transport Systems', 'Includes CCTV maintenance.', ['Swarco UK']),
    ('Dynamic Purchasing System for Building Safety and Security Systems', 'Lot 1: Fire alarms maintenance.', ['Fire Systems Ltd']),
    ('Camden Building Term Service Contract 2 - General Building Works South', 'Includes fire stopping maintenance.', ['Mitie Property Services (UK) Ltd']),
    ('The Provision of Security Guarding Services to the British Embassy in Nigeria', '', ['Garda World Consulting Nigeria Limited']),
    ('Parking Services - CCTV Camera Enforcement', 'This notice is to cancel 2022/S 000-011762.', ['Marston (Holdings) Limited']),
    ('Automatic Gates & Barrier Servicing and Maintenance', '', ['Alphatrack Systems Limited']),
    ('CCTV SYSTEM', 'The supply, installation, testing and commissioning of fully functional CCTV systems.', ['MDP Communication Services Ltd']),
    ('Quotation Fire Damper Remedial - National Highways', 'A recent compliance inspection identified multiple defects.', ['Edmund Services Limited']),
    ('S1232-75 - High Mast Lighting Maintenance', 'Maintenance of emergency lighting columns.', ['Coating Services Limited']),
    ('Contract 31 - Fire Door Sets 2024-2026', 'The Authority invites providers for the above Framework for skilled service.', ['Bell Group Limited']),
    ('Access Control and Security Services', 'Tideway requires an extension to the current framework agreement.', ['G4S Security Services (UK) Limited']),
    ('Fire & Intruder Alarms, Door Access Maintenance and Repairs', 'Fife Council is looking to engage with suppliers for a Fire Alarm and Intruder Maintenance Framework.', ['VWS Ltd']),
])
def test_audited_false_positives_stay_excluded(title, description, suppliers):
    from app.intelligence.renewal_radar import classify
    assert classify({'title': title, 'description': description, 'suppliers': suppliers, 'start': '2024-01-01', 'end': '2027-06-30'})[0] == 'exclude'


@pytest.mark.parametrize('title,description', [
    ('SSC - BSTC002 - Inspection, Servicing and Maintenance of Drains and Pumps, Fire Fighting Equipment, Fire Suppression', ''),
    ('CA13825 - WSFT-SB-LG-FIREALARMS-01-24', 'fire alarm maintenance and service'),
    ('Emergency Lighting Services', ''),
    ('AT1297 Fire Safety Equipment - Supply, Installation Service and Repair', ''),
])
def test_audited_missed_contracts_are_found(title, description):
    from app.intelligence.renewal_radar import classify
    assert classify({'title': title, 'description': description, 'suppliers': ['A Ltd'], 'start': '2024-01-01', 'end': '2027-06-30'})[0] != 'exclude'


def test_csv_neutralises_a_formula_in_a_published_title():
    with make_db() as db:
        load(db, [award('000001-2024', 'ocds-h6vhtk-000001', buyer='=cmd() Council')])
        refresh_market_opportunities(db, now=NOW)
        db.commit()
        assert ",'=cmd() Council," in export_csv(db)


def test_checkpoints_load_once_and_rerun_collects_nothing_new(tmp_path):
    search = tmp_path / 'notices.json'
    tenders = tmp_path / 'tenders.json'
    notice = {'id': '44444444-0000-4000-8000-000000000001', 'url': 'https://www.contractsfinder.service.gov.uk/Notice/44444444-0000-4000-8000-000000000001', 'title': 'CCTV maintenance', 'buyer': 'Council',
              'description': '', 'type': 'Contract', 'status': 'Awarded', 'published': '2024-01-01', 'start': '2024-01-01', 'end': '2027-06-30', 'approach': '', 'value': 1000.0, 'suppliers': ['A Ltd'], 'cpv': [], 'region': 'London', 'postcode': ''}
    search.write_text(json.dumps({'notices': {notice['id']: notice, 'x': {**notice, 'id': 'x', 'title': 'Catering'}}, 'fetches': []}))
    tenders.write_text(json.dumps({'tenders': {}, 'processes': {}, 'planning': {}, 'done': ['week:2026-10-19', 'week:2026-10-12', 'week:2021-03-01'], 'fetches': []}))
    with make_db() as db:
        first = import_checkpoints(db, search_path=search, tender_path=tenders)
        second = import_checkpoints(db, search_path=search, tender_path=tenders)
        assert first['new'] == 1 and first['search_rows_outside_sector'] == 1 and second['new'] == 0 and second['unchanged'] == 1
        state = db.get(MarketSourceState, 'find_a_tender_history')
        assert state.window_from.date() == date(2026, 10, 12) and '2021-03-01' in state.cursor


def test_reduced_records_rebuild_the_same_contract():
    tender = {'ocid': 'ocds-h6vhtk-000009', 'release_id': '000009-2023', 'title': 'Fire alarm maintenance', 'buyer': 'Council', 'published': '2023-01-01', 'updated': '2023-01-01', 'description': 'Servicing.', 'cpv': [], 'region': '', 'postcode': '',
              'tender_seen': True, 'status': 'active', 'deadline': '2023-02-01', 'framework': False, 'lots': [{'id': '1', 'title': '', 'start': '', 'end': '', 'days': 1460, 'renewal': ''}]}
    process = {'checked': None, 'releases': [{'id': '000010-2023', 'date': '2023-06-01T00:00:00Z', 'awards': [{'id': 'a', 'relatedLots': ['1'], 'date': '2023-06-01T00:00:00Z', 'suppliers': [{'id': 'GB-COH-01234567', 'name': 'Acme Ltd'}]}], 'contracts': []}]}
    records = list(tender_records({'tenders': {tender['ocid']: tender}, 'processes': {tender['ocid']: process}, 'planning': {}}, NOW))
    with make_db() as db:
        for record in records:
            ingest_market_release(db, record)
        refresh_market_opportunities(db, now=NOW)
        contract = db.scalar(select(MarketContract))
        assert contract.facts['estimated_end_date'] == '2027-05-31' and contract.facts['company_numbers'] == ['01234567'] and contract.facts['identity_status'] == 'published_company_number'


def test_search_row_becomes_a_contract_without_inventing_identifiers():
    record = search_record({'id': '55555555-0000-4000-8000-000000000001', 'title': 'CCTV maintenance', 'buyer': 'Council', 'type': 'Contract', 'status': 'Awarded', 'published': '2024-01-01', 'start': '', 'end': '2027-06-30', 'suppliers': ['A Ltd']}, NOW)
    assert record['ocid'] == 'ocds-b5fd17-55555555-0000-4000-8000-000000000001' and record['raw']['awards'][0]['suppliers'] == [{'name': 'A Ltd'}] and 'parties' in record['raw']


def test_scottish_empty_month_is_a_valid_package_but_garbage_is_not():
    empty = {'uri': 'x', 'publishedDate': '2026-11-01T19:26:46Z', 'publisher': {'name': 'The Scottish Government'}}
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=empty))) as client:
        assert fetch_month(2026, 11, 3, client=client) == []
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'unexpected': True}))) as client:
        with pytest.raises(ValueError):
            fetch_month(2026, 11, 3, client=client)


def test_scottish_rollover_reads_last_month_and_one_failure_is_not_reported_as_success():
    calls = []

    def handler(request):
        calls.append((request.url.params['dateFrom'], request.url.params['noticeType']))
        if request.url.params['noticeType'] == '2':
            return httpx.Response(503)
        return httpx.Response(200, json={'publisher': {'name': 'x'}, 'publishedDate': 'x'})

    with make_db() as db, httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            run_scotland_current(db, client=client, now=NOW)
        assert {x[0] for x in calls} == {'11-2026', '10-2026'} and len(calls) == 10
        assert db.get(MarketSourceState, 'pcs_2026_11_2').failure_count == 1 and db.get(MarketSourceState, 'pcs_2026_11_3').last_success_at


def test_monitors_keep_records_the_radar_needs():
    release = {'tender': {'title': 'Building services', 'lots': [{'title': 'Emergency lighting testing'}]}}
    assert monitored(release) is True and monitored({'tender': {'title': 'Catering'}}) is False


def test_refresh_runs_only_when_records_or_the_day_change():
    with make_db() as db:
        load(db, [award('000001-2024', 'ocds-h6vhtk-000001')])
        assert refresh_if_due(db, now=NOW)['candidates'] == 1
        assert refresh_if_due(db, now=NOW + timedelta(hours=1)) is None
        assert refresh_if_due(db, now=NOW + timedelta(days=1)) is not None
        load(db, [award('000002-2024', 'ocds-h6vhtk-000002', title='CCTV maintenance')])
        assert refresh_if_due(db, now=NOW + timedelta(days=1, hours=1))['candidates'] == 2


def test_failed_evaluation_keeps_the_last_good_list_and_recovers(monkeypatch):
    import app.services.renewal_radar as radar
    with make_db() as db:
        load(db, [award('000001-2024', 'ocds-h6vhtk-000001')])
        refresh_if_due(db, now=NOW)

        def broken(*args, **kwargs):
            db.add(MarketOpportunity(dedup_key='half-written', state='suggested', review_state='unreviewed', first_seen=NOW, last_evaluated=NOW))
            db.flush()
            raise RuntimeError('killed part way')

        monkeypatch.setattr(radar, 'refresh_market_opportunities', broken)
        with pytest.raises(RuntimeError):
            refresh_if_due(db, now=NOW + timedelta(days=1))
        assert db.scalar(select(func.count()).select_from(MarketOpportunity)) == 1 and db.get(MarketSourceState, 'renewal_radar').last_error == 'RuntimeError'
        monkeypatch.undo()
        assert refresh_if_due(db, now=NOW + timedelta(days=1)) is not None and db.get(MarketSourceState, 'renewal_radar').failure_count == 0


def test_health_marks_stale_failing_and_missing_sources():
    with make_db() as db:
        db.add_all([MarketSourceState(source_key='find_a_tender', last_success_at=NOW - timedelta(hours=1)), MarketSourceState(source_key='contracts_finder', last_success_at=NOW - timedelta(days=2)),
                    MarketSourceState(source_key='public_contracts_scotland', last_success_at=NOW - timedelta(hours=1), failure_count=5, last_error='ValueError')])
        db.commit()
        health = {x['source_key']: x['status'] for x in source_health(db, now=NOW)}
        assert health == {'find_a_tender': 'fresh', 'contracts_finder': 'stale', 'public_contracts_scotland': 'failing', 'renewal_radar': 'never_run'}


def test_selective_history_targets_large_contracts_known_only_from_elsewhere():
    with make_db() as db:
        load(db, [award('66666666-0000-4000-8000-000000000001-1', 'ocds-b5fd17-66666666-0000-4000-8000-000000000001', 'contracts_finder', value=2000000)])
        refresh_market_opportunities(db, now=NOW)
        contract = db.scalar(select(MarketContract))
        contract.facts = {**contract.facts, 'published': '2022-03-09'}
        db.add(MarketSourceState(source_key='find_a_tender_history', window_from=datetime(2022, 10, 10, tzinfo=UTC), cursor='{"weeks_outside_run": []}'))
        db.commit()
        assert selective_weeks(db) == [(date(2022, 3, 7), date(2022, 3, 13))]
        fetched = []
        result = run_daily_cycle(db, now=NOW, fetch=lambda cache, today, weeks, budget: fetched.append(weeks) or {'requests': 1})
        assert fetched == [[(date(2022, 3, 7), date(2022, 3, 13))]] and result['history'] == {'requests': 1}
        run_daily_cycle(db, now=NOW + timedelta(hours=1), fetch=lambda *a: fetched.append(a))
        assert len(fetched) == 1
