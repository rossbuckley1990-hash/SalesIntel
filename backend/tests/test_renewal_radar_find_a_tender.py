from datetime import date

import httpx
import pytest

from app.ingestion.find_a_tender import API_URL
from app.ingestion.market_contracts_search import Budget
from app.ingestion.market_find_tender_radar import (collect_window, fetch_process, ingest, merge_tender, needs_process, notices, planning_notice,
                                                    relevant, stage_of, tender_record)
from app.intelligence.renewal_radar import backtest, classify, early_signals, renewal_leads

TODAY = date(2026, 11, 1)
OCID = 'ocds-h6vhtk-03ae49'


def tender_release(**tender):
    base = {'title': 'Fire alarm maintenance', 'description': 'Planned servicing of fire alarm systems.', 'status': 'active',
            'tenderPeriod': {'endDate': '2023-04-05T12:00:00+01:00'}, 'classification': {'scheme': 'CPV', 'id': '50413200-0'},
            'lots': [{'id': '1', 'contractPeriod': {'durationInDays': 1460}, 'hasRenewal': True, 'renewal': {'description': 'Up to 24 months.'}}]}
    return {'ocid': OCID, 'id': '006414-2023', 'date': '2023-03-06T11:23:04Z', 'tag': ['tender'], 'buyer': {'id': 'B1', 'name': 'Example Council'},
            'parties': [{'id': 'B1', 'address': {'region': 'UKC2', 'postalCode': 'G1 1RD'}}], 'tender': {**base, **tender}}


def award_release(*awards, contracts=()):
    return {'id': '019272-2023', 'date': '2023-07-06T00:00:00Z', 'awards': list(awards), 'contracts': list(contracts)}


def award(award_id='A1', suppliers=('Acme Fire Ltd',), lot='1', status='active'):
    return {'id': award_id, 'status': status, 'relatedLots': [lot], 'suppliers': [{'name': x} for x in suppliers]}


def contract(award_id='A1', signed='2023-07-06T00:00:00+01:00', amount=400000, currency='GBP'):
    return {'awardID': award_id, 'dateSigned': signed, 'value': {'amount': amount, 'currency': currency}}


def record(**tender):
    return tender_record(tender_release(**tender))


def test_relevance_uses_wording_or_a_core_code():
    assert relevant(tender_release())
    assert relevant(tender_release(title='Estate upkeep', description='General work.', classification={'id': '50610000-4'}))
    assert not relevant(tender_release(title='Payroll system', description='Software.', classification={'id': '72000000-5'}))


def test_tender_record_keeps_term_and_renewal():
    result = record()
    assert result['lots'] == [{'id': '1', 'title': '', 'start': '', 'end': '', 'days': 1460, 'renewal': 'Up to 24 months.'}]
    assert result['region'] == 'UKC2' and result['deadline'] == '2023-04-05' and result['cpv'] == ['50413200']


def test_invalid_identifier_is_rejected():
    assert tender_record({**tender_release(), 'id': '../secret'}) is None


def test_end_date_is_signature_plus_duration_and_marked_estimated():
    found = notices(record(), [award_release(award(), contracts=[contract()])], TODAY)[0]
    assert found['end'] == '2027-07-05' and found['end_estimated'] is True
    assert found['status'] == 'Awarded' and found['suppliers'] == ['Acme Fire Ltd'] and found['value'] == 400000.0
    assert found['approach'] == '2023-03-06' and found['extension_note'] == 'Up to 24 months.'


def test_published_end_date_beats_the_estimate():
    period = {**contract(), 'period': {'endDate': '2026-12-31T00:00:00Z'}}
    found = notices(record(), [award_release(award(), contracts=[period])], TODAY)[0]
    assert found['end'] == '2026-12-31' and found['end_estimated'] is False


def test_published_extension_limit_reaches_the_lead():
    period = {**contract(), 'period': {'endDate': '2027-06-30T00:00:00Z', 'maxExtentDate': '2029-06-30T00:00:00Z'}}
    lead = renewal_leads(notices(record(), [award_release(award(), contracts=[period])], TODAY), TODAY)[0]
    assert lead['end'] == '2027-06-30' and lead['latest_end'] == '2029-06-30' and lead['extension_mentioned'] is True


def test_no_duration_means_no_invented_end_date():
    plain = record(lots=[{'id': '1'}])
    found = notices(plain, [award_release(award(), contracts=[contract()])], TODAY)[0]
    assert found['end'] == '' and found['end_estimated'] is False


def test_framework_suppliers_stay_on_one_lot():
    names = [f'Supplier {n}' for n in range(6)]
    awards = [award(f'A{n}', [name]) for n, name in enumerate(names)]
    found = notices(record(), [award_release(*awards, contracts=[contract(f'A{n}') for n in range(6)])], TODAY)
    assert len(found) == 1 and found[0]['suppliers'] == names and classify(found[0])[0] == 'exclude'


def test_each_lot_gets_its_own_term():
    lots = [{'id': '1', 'contractPeriod': {'durationInDays': 365}}, {'id': '2', 'contractPeriod': {'durationInDays': 730}}]
    release = award_release(award('A1', lot='1'), award('A2', ['Other Ltd'], lot='2'), contracts=[contract('A1'), contract('A2')])
    assert sorted(x['end'] for x in notices(record(lots=lots), [release], TODAY)) == ['2024-07-05', '2025-07-05']


def test_unsuccessful_award_is_ignored():
    found = notices(record(), [award_release(award(status='unsuccessful'))], TODAY)
    assert found[0]['status'] == 'Closed' and found[0]['end'] == ''


def test_foreign_currency_value_is_not_treated_as_sterling():
    found = notices(record(), [award_release(award(), contracts=[contract(currency='EUR')])], TODAY)[0]
    assert found['value'] is None


def test_open_tender_is_kept_for_relet_checks_but_is_not_a_lead():
    live = record(tenderPeriod={'endDate': '2026-12-01T12:00:00Z'})
    found = notices(live, [], TODAY)
    assert found[0]['status'] == 'Open' and renewal_leads(found, TODAY) == []


def test_cancelled_tender_gives_nothing():
    assert notices(record(status='cancelled'), [], TODAY) == []


def test_process_is_fetched_only_for_an_award_missing_its_term():
    orphan = {**record(lots=[{'id': '1'}]), 'tender_seen': False}
    assert needs_process(orphan, TODAY) is True
    assert needs_process(record(), TODAY) is False
    assert needs_process({**record(), 'tender_seen': False}, TODAY) is False
    assert needs_process({**record(title='Payroll', description='Software.', lots=[{'id': '1'}]), 'tender_seen': False}, TODAY) is False
    assert needs_process({**record(lots=[{'id': '1'}]), 'tender_seen': False, 'published': '2015-01-01'}, TODAY) is False


def test_award_tags_win_over_older_stage_tags():
    assert stage_of({'tag': ['award', 'contract']}) == 'award'
    assert stage_of({'tag': ['tenderUpdate']}) == 'tender'
    assert stage_of({'tag': ['planningUpdate']}) == 'planning'
    assert stage_of({'tag': ['implementation']}) is None


def test_update_keeps_the_first_market_date_and_newest_wording():
    original = record()
    update = {**record(title='Fire alarm maintenance (amended)'), 'published': '2023-04-01', 'updated': '2023-04-01'}
    for merged in (merge_tender(original, update), merge_tender(update, original)):
        assert merged['title'] == 'Fire alarm maintenance (amended)' and merged['published'] == '2023-03-06'


def test_update_without_a_term_keeps_the_earlier_term():
    update = {**record(lots=[{'id': '1'}]), 'published': '2023-04-01', 'updated': '2023-04-01'}
    assert merge_tender(record(), update)['lots'][0]['days'] == 1460


def test_ingest_joins_stages_arriving_newest_first():
    cache = {'tenders': {}, 'processes': {}, 'planning': {}}
    award_notice = {**award_release(award(), contracts=[contract()]), 'ocid': OCID, 'tag': ['award', 'contract'], 'date': '2023-07-06T00:00:00Z',
                    'buyer': {'id': 'B1', 'name': 'Example Council'}, 'tender': {'title': 'Fire alarm maintenance', 'lots': [{'id': '1'}]}}
    ingest(cache, award_notice)
    ingest(cache, award_notice)
    assert cache['tenders'][OCID]['tender_seen'] is False and len(cache['processes'][OCID]['releases']) == 1
    assert notices(cache['tenders'][OCID], cache['processes'][OCID]['releases'], TODAY)[0]['approach'] == ''
    ingest(cache, tender_release())
    found = notices(cache['tenders'][OCID], cache['processes'][OCID]['releases'], TODAY)[0]
    assert found['end'] == '2027-07-05' and found['approach'] == '2023-03-06'


def test_ingest_routes_planning_notices():
    cache = {'tenders': {}, 'processes': {}, 'planning': {}}
    ingest(cache, {**tender_release(), 'id': '103449-2026', 'tag': ['planning']})
    assert list(cache['planning']) == ['find_a_tender:103449-2026'] and cache['tenders'] == {}


def test_planning_notice_carries_expected_tender_date():
    release = {**tender_release(status='planned', communication={'futureNoticeDate': '2026-11-30T00:00:00Z'}, value={'amount': 5000, 'currency': 'GBP'}),
               'id': '103449-2026', 'date': '2026-10-30T00:00:00Z'}
    found = planning_notice(release)
    assert found['type'] == 'Pipeline' and found['approach'] == '2026-11-30' and found['value'] == 5000.0
    assert found['url'].endswith('/103449-2026')


def _lead(**fields):
    base = {'id': '1', 'url': 'https://example.test/1', 'title': 'Fire alarm servicing and maintenance', 'buyer': 'Example Council', 'description': '',
            'type': 'Contract', 'status': 'Awarded', 'published': '2023-04-01', 'start': '2023-04-01', 'end': '2027-03-31', 'approach': '',
            'value': 400000.0, 'suppliers': ['Acme Fire Ltd'], 'cpv': [], 'region': '', 'postcode': ''}
    return {**base, **fields}


def test_same_contract_on_both_sources_keeps_the_published_date():
    exact = _lead()
    estimated = _lead(id='2', source='find_a_tender', end='2027-05-01', end_estimated=True)
    assert [x['id'] for x in renewal_leads([estimated, exact], TODAY)] == ['1']


def test_framework_flag_excludes_a_notice():
    assert classify(_lead(framework=True))[0] == 'exclude'


def test_early_signal_drops_once_the_process_reaches_tender():
    planned = _lead(id='p', type='Pipeline', status='Planned', published='2026-06-01', end='', start='', ocid=OCID)
    tendered = _lead(id='t', status='Open', published='2026-09-01', end='', ocid=OCID)
    assert early_signals([planned, tendered], TODAY) == []
    assert [x['id'] for x in early_signals([planned], TODAY)] == ['p']


def test_early_signal_past_its_expected_tender_goes_stale():
    late = _lead(id='p', type='Pipeline', status='Planned', published='2026-01-01', end='', start='', approach='2026-02-01')
    assert early_signals([late], TODAY) == []


def test_backtest_times_only_market_dates():
    ended = _lead(end='2025-06-30', start='2022-07-01', published='2022-06-01')
    award_only = _lead(id='2', published='2025-02-01', start='2025-07-01', end='2029-06-30')
    result = backtest([ended, award_only], TODAY)
    assert result['with_visible_successor'] == 1 and result['timed_replacements'] == 0 and result['median_days_before_end'] is None


def page(*releases, cursor=None):
    links = {'next': f'{API_URL}?cursor={cursor}'} if cursor else {}
    return {'releases': list(releases), 'links': links}


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _window(handler, budget):
    with _client(handler) as http:
        return collect_window(http, date(2023, 3, 1), date(2023, 3, 31), budget, pause=0, sleep=lambda _: None)


def test_window_pages_every_stage_and_filters_locally():
    irrelevant = tender_release(title='Payroll', description='Software.', classification={'id': '72000000-5'})

    def handler(request):
        assert 'stages' not in request.url.params
        if 'cursor' not in request.url.params:
            return httpx.Response(200, json=page(tender_release(), irrelevant, cursor='MTAw'))
        return httpx.Response(200, json=page(tender_release()))

    assert len(_window(handler, Budget(requests_left=5))) == 2


def test_window_returns_none_when_the_budget_ends_midway():
    budget = Budget(requests_left=1)

    def handler(request):
        return httpx.Response(200, json=page(tender_release(), cursor='MTAw'))

    assert _window(handler, budget) is None and budget.exhausted is True


def test_repeated_cursor_stops_the_run():
    def handler(request):
        return httpx.Response(200, json=page(cursor='MTAw'))

    with pytest.raises(ValueError):
        _window(handler, Budget(requests_left=5))


def test_retry_after_is_honoured_and_counted():
    waits, replies = [], [httpx.Response(429, headers={'Retry-After': '11'}), httpx.Response(200, json=page(tender_release()))]
    budget = Budget(requests_left=5)
    with _client(lambda request: replies.pop(0)) as http:
        found = collect_window(http, date(2023, 3, 1), date(2023, 3, 31), budget, pause=0, sleep=waits.append)
    assert len(found) == 1 and waits[0] == 11 and budget.requests_made == 2 and budget.waits == 1


def test_process_fetch_returns_every_stage():
    def handler(request):
        assert request.url.path.endswith(f'/{OCID}')
        return httpx.Response(200, json={'releases': [tender_release(), award_release(award())]})

    with _client(handler) as http:
        found = fetch_process(http, OCID, Budget(requests_left=2), pause=0, sleep=lambda _: None)
    assert len(found) == 2


def test_missing_process_is_empty_not_an_error():
    with _client(lambda request: httpx.Response(404)) as http:
        assert fetch_process(http, OCID, Budget(requests_left=2), pause=0, sleep=lambda _: None) == []


def test_process_fetch_rejects_an_unsafe_identifier():
    with _client(lambda request: httpx.Response(200, json=page())) as http:
        with pytest.raises(ValueError):
            fetch_process(http, '../../etc', Budget(requests_left=2), pause=0, sleep=lambda _: None)
