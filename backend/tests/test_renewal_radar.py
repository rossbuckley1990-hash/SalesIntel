from datetime import date

import httpx

from app.ingestion.market_contracts_search import API_URL, Budget, collect, normalise
from app.intelligence.renewal_radar import backtest, bucket, classify, early_signals, renewal_leads

TODAY = date(2026, 11, 1)


def notice(**fields):
    base = {'id': '1', 'url': 'https://example.test/1', 'title': 'Fire alarm servicing and maintenance', 'buyer': 'Example Council',
            'description': '', 'type': 'Contract', 'status': 'Awarded', 'published': '2023-04-01', 'start': '2023-04-01',
            'end': '2027-03-31', 'approach': '', 'value': 400000.0, 'suppliers': ['Acme Fire Ltd'], 'cpv': [], 'region': 'London', 'postcode': ''}
    return {**base, **fields}


def item(**fields):
    base = {'id': '0280c816-0000-4000-8000-000000000001', 'title': 'Alarm &amp; CCTV upkeep', 'organisationName': 'Acme &amp; Co',
            'awardedSupplier': 'One Ltd,One Ltd,Two &amp; Sons', 'publishedDate': '2023-07-05T10:00:00Z', 'start': '2023-08-01T00:00:00Z',
            'end': '2026-02-28T00:00:00+01:00', 'awardedValue': 57000, 'cpvCodes': '50413200 50000000'}
    return {'item': {**base, **fields}}


def test_title_with_system_and_service_is_core():
    assert classify(notice())[0] == 'core'


def test_description_can_confirm_service_for_named_system():
    assert classify(notice(title='CCTV contract', description='Planned maintenance of CCTV across all sites.'))[0] == 'core'


def test_one_off_replacement_is_excluded():
    fit, reason = classify(notice(title='Replacement fire alarm at town hall'))
    assert fit == 'exclude' and 'one-off' in reason


def test_installation_with_maintenance_stays_a_service_contract():
    assert classify(notice(title='Supply, installation and maintenance of CCTV'))[0] == 'core'


def test_fire_service_supplies_are_not_fire_systems():
    assert classify(notice(title='Fire Authority Occupational Health Physician services'))[0] == 'exclude'


def test_many_suppliers_is_treated_as_a_framework():
    assert classify(notice(suppliers=[f'Supplier {n}' for n in range(5)]))[0] == 'exclude'


def test_short_term_cannot_be_recurring_maintenance():
    assert classify(notice(start='2026-01-01', end='2026-03-01'))[0] == 'exclude'


def test_wider_maintenance_with_fire_service_is_bundled():
    described = notice(title='Provision of statutory maintenance', description='Includes servicing of fire alarms and sprinklers.')
    assert classify(described)[0] == 'bundled'


def test_passive_fire_work_is_adjacent():
    assert classify(notice(title='Fire door inspection programme'))[0] == 'adjacent'


def test_timing_buckets():
    assert bucket(date(2027, 3, 1), TODAY) == 'act_now'
    assert bucket(date(2028, 1, 1), TODAY) == 'plan'
    assert bucket(date(2026, 12, 1), TODAY) == 'closing'
    assert bucket(date(2026, 10, 1), TODAY) == 'overdue_check'
    assert bucket(date(2026, 1, 1), TODAY) is None
    assert bucket(date(2029, 1, 1), TODAY) is None


def test_lead_carries_annual_value_and_incumbent():
    lead = renewal_leads([notice()], TODAY)[0]
    assert lead['bucket'] == 'act_now' and lead['incumbent'] == 'Acme Fire Ltd' and lead['annual_value'] == round(400000 / (1460 / 365.25), 2)


def test_own_group_contract_is_tagged_for_defence():
    assert renewal_leads([notice(suppliers=['Marlowe Fire & Security Ltd'])], TODAY)[0]['own_group'] is True


def test_newer_notice_for_same_system_marks_contract_relet():
    newer = notice(id='2', published='2026-05-01', start='2026-06-01', end='2030-05-31', title='Fire alarm maintenance contract')
    old = next(x for x in renewal_leads([notice(), newer], TODAY) if x['id'] == '1')
    assert old['bucket'] == 'relet_seen' and old['successor_published'] == '2026-05-01'


def test_newer_notice_for_a_different_system_does_not_mark_relet():
    other = notice(id='2', published='2026-05-01', end='2030-05-31', title='CCTV maintenance contract')
    assert next(x for x in renewal_leads([notice(), other], TODAY) if x['id'] == '1')['bucket'] == 'act_now'


def test_same_system_at_a_different_site_does_not_mark_relet():
    site = notice(id='2', published='2026-05-01', end='2030-05-31', title='Fire alarm upgrade programme for Queens Road Hospital west wing estate')
    assert next(x for x in renewal_leads([notice(), site], TODAY) if x['id'] == '1')['bucket'] == 'act_now'


def test_newer_notice_that_ends_first_does_not_mark_relet():
    interim = notice(id='2', published='2026-05-01', end='2027-04-30', title='Fire alarm maintenance contract')
    assert next(x for x in renewal_leads([notice(), interim], TODAY) if x['id'] == '1')['bucket'] == 'act_now'


def test_description_alone_cannot_link_a_replacement():
    doors = notice(id='2', published='2026-05-01', end='2030-05-31', title='Maintenance of automatic doors',
                   description='Includes servicing of fire alarm interfaces.')
    assert next(x for x in renewal_leads([notice(), doors], TODAY) if x['id'] == '1')['bucket'] == 'act_now'


def test_drain_cctv_is_not_security_cctv():
    assert classify(notice(title='Culvert repairs, CCTV inspection and maintenance'))[0] == 'exclude'


def test_telecare_alarms_are_not_fire_or_security_systems():
    assert classify(notice(title='Community alarms and key safe installation and maintenance'))[0] == 'exclude'


def test_duplicate_lots_collapse_to_the_largest():
    leads = renewal_leads([notice(), notice(id='2', value=900000.0)], TODAY)
    assert [x['id'] for x in leads] == ['2']


def test_missing_end_date_gives_no_lead():
    assert renewal_leads([notice(end='')], TODAY) == []


def test_early_signal_needs_official_stage_and_recency():
    live = notice(id='2', type='Pipeline', status='Closed', published='2026-06-01', end='', title='Fire extinguisher servicing')
    stale = notice(id='3', type='PreProcurement', status='Closed', published='2023-01-01', end='', title='Sprinkler maintenance')
    assert [x['id'] for x in early_signals([live, stale, notice()], TODAY)] == ['2']


def test_backtest_counts_only_settled_core_contracts():
    ended = notice(end='2025-06-30', start='2022-07-01', published='2022-06-01')
    renewed = notice(id='2', published='2025-02-01', start='2025-07-01', end='2029-06-30', approach='2024-12-01')
    unrelated = notice(id='3', buyer='Other Council', end='2024-12-31', start='2022-01-01', published='2022-01-01')
    result = backtest([ended, renewed, unrelated], TODAY)
    assert result['contracts'] == 2 and result['with_visible_successor'] == 1
    assert result['median_days_before_end'] == 211


def test_normalise_decodes_and_deduplicates():
    result = normalise(item()['item'])
    assert result['buyer'] == 'Acme & Co' and result['suppliers'] == ['One Ltd', 'Two & Sons']
    assert result['end'] == '2026-02-28' and result['cpv'] == ['50000000', '50413200'] and result['value'] == 57000.0


def test_normalise_rejects_an_unsafe_id():
    assert normalise(item(id='../secret')['item']) is None


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_truncated_window_is_split_until_complete():
    calls = []

    def handler(request):
        assert str(request.url) == API_URL
        criteria = __import__('json').loads(request.content)['searchCriteria']
        calls.append(criteria['publishedFrom'])
        whole = criteria['publishedFrom'] == '2023-01-01' and criteria['publishedTo'] == '2023-06-30'
        rows = [item()] if not whole else [item(), item()]
        return httpx.Response(200, json={'hitCount': 3 if whole else 1, 'noticeList': rows})

    budget = Budget(requests_left=10)
    with _client(handler) as http:
        found = collect(http, {'keyword': 'fire'}, date(2023, 1, 1), date(2023, 6, 30), budget, pause=0, sleep=lambda _: None)
    assert budget.requests_made == 3 and len(found) == 2 and budget.truncated_hits == 0


def test_request_budget_is_never_exceeded():
    def handler(request):
        return httpx.Response(200, json={'hitCount': 9999, 'noticeList': [item()]})

    budget = Budget(requests_left=3)
    with _client(handler) as http:
        collect(http, {'keyword': 'fire'}, date(2021, 1, 1), date(2026, 1, 1), budget, pause=0, sleep=lambda _: None)
    assert budget.requests_made == 3 and budget.exhausted is True


def test_unsplittable_window_reports_lost_hits():
    def handler(request):
        return httpx.Response(200, json={'hitCount': 5, 'noticeList': [item()]})

    budget = Budget(requests_left=3)
    with _client(handler) as http:
        collect(http, {'keyword': 'fire'}, date(2023, 1, 1), date(2023, 1, 3), budget, pause=0, sleep=lambda _: None)
    assert budget.truncated_hits == 4
