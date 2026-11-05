from datetime import date

from app.ingestion.market_find_tender_radar import ingest, notices
from app.intelligence.contract_lifecycle import contract_lifecycle
from app.intelligence.contract_terms import award_term, extension_months, framework_stage, stated_term_months

TODAY = date(2026, 11, 2)


def release(**fields):
    return {'tender': {'title': 'Fire alarm maintenance'}, **fields}


def test_published_contract_end_date_is_read_and_not_estimated():
    raw = release(awards=[{'id': '1'}], contracts=[{'id': 'c', 'awardID': '1', 'period': {'startDate': '2024-01-01', 'endDate': '2027-12-31'}}])
    term = award_term(raw, raw['awards'][0], raw['contracts'][0])
    assert (term['end'], term['end_basis'], term['end_estimated'], term['estimated_end']) == ('2027-12-31', 'contract_period', False, '')


def test_award_contract_period_is_read_when_no_contract_record_exists():
    raw = release(awards=[{'id': '1', 'contractPeriod': {'startDate': '2023-02-28T00:00:00Z', 'endDate': '2026-02-27T23:59:59Z'}}])
    result = contract_lifecycle(raw, '1')
    assert result['end_date'] == '2026-02-27' and result['end_basis'] == 'award_contract_period' and result['status'] == 'award_period_published'
    assert 'awards[0].contractPeriod' in result['evidence_paths']


def test_tender_duration_is_an_estimate_and_never_a_published_end():
    raw = {'tender': {'lots': [{'id': '1', 'contractPeriod': {'durationInDays': 1095}}]}, 'awards': [{'id': '1', 'relatedLots': ['1'], 'date': '2024-01-01T00:00:00Z'}]}
    term = award_term(raw, raw['awards'][0])
    assert term['end'] == '' and term['estimated_end'] == '2026-12-31' and term['end_estimated'] is True and term['end_basis'] == 'tender_duration'
    assert contract_lifecycle(raw, '1')['end_date'] is None and contract_lifecycle(raw, '1')['estimated_end_date'] == '2026-12-31'


def test_tender_planned_end_is_an_estimate():
    raw = {'tender': {'contractPeriod': {'startDate': '2024-04-01', 'endDate': '2027-03-31'}}, 'awards': [{'id': '1'}]}
    term = award_term(raw, raw['awards'][0])
    assert term['end'] == '' and term['estimated_end'] == '2027-03-31' and term['end_basis'] == 'tender_planned_end'


def test_term_stated_in_wording_is_used_only_with_a_start_date():
    worded = {'tender': {'description': 'The contract period is 36 months with an option to extend for 24 months.'}}
    assert award_term(worded, {'id': '1', 'date': '2024-01-15'})['estimated_end'] == '2027-01-15'
    assert award_term(worded, {'id': '1'})['estimated_end'] == ''


def test_stated_term_and_extension_wording():
    assert stated_term_months('A 3+1+1 year contract') == 36 and extension_months('A 3+1+1 year contract') == 24
    assert stated_term_months('Contract term of three (3) years') == 36
    assert stated_term_months('A 24 hour call-out service') is None and stated_term_months('Paid in 30 days') is None
    assert extension_months('Option to extend by a further 12 months') == 12


def test_published_extension_limit_outranks_wording():
    raw = release(awards=[{'id': '1', 'contractPeriod': {'endDate': '2027-01-01', 'maxExtentDate': '2029-01-01'}}])
    term = award_term(raw, raw['awards'][0])
    assert term['latest_end'] == '2029-01-01' and term['latest_end_basis'] == 'published_max_extent'


def test_extension_wording_gives_a_possible_latest_end():
    raw = {'tender': {'description': 'Initial term with an option to extend for 2 years.'}, 'awards': [{'id': '1', 'contractPeriod': {'endDate': '2027-01-01'}}]}
    term = award_term(raw, raw['awards'][0])
    assert term['latest_end'] == '2029-01-01' and term['latest_end_basis'] == 'extension_wording' and term['end'] == '2027-01-01'


def test_missing_period_invents_nothing():
    raw = release(awards=[{'id': '1'}])
    term = award_term(raw, raw['awards'][0])
    assert term['end'] == term['estimated_end'] == '' and term['end_basis'] == 'none'


def test_impossible_published_end_is_rejected_and_flagged():
    raw = release(awards=[{'id': '1', 'contractPeriod': {'startDate': '2027-01-01', 'endDate': '2026-01-01'}}])
    term = award_term(raw, raw['awards'][0])
    assert term['end'] == '' and term['conflict'] is True


def test_conflicting_published_dates_are_flagged():
    raw = release(awards=[{'id': '1', 'contractPeriod': {'endDate': '2027-01-01'}}], contracts=[{'id': 'c', 'awardID': '1', 'period': {'endDate': '2028-01-01'}}])
    result = contract_lifecycle(raw, '1')
    assert result['end_date'] == '2028-01-01' and any('conflicting' in x for x in result['limitations'])


def test_framework_agreement_and_call_off_are_distinct():
    assert framework_stage({'tender': {'techniques': {'hasFrameworkAgreement': True}}})[0] == 'framework_first_stage'
    assert framework_stage({'tender': {}, 'relatedProcesses': [{'relationship': ['framework']}]})[0] == 'framework_second_stage'
    assert framework_stage({'tender': {'procurementMethodDetails': 'Call-off from a framework agreement'}})[0] == 'framework_second_stage'
    assert framework_stage({'tender': {'description': 'Call-off contract via the NHS SBS framework.'}})[0] == 'framework_second_stage'
    assert framework_stage({'tender': {'description': 'Maintenance of alarms.'}})[0] is None


def _process(*releases):
    cache = {'tenders': {}, 'processes': {}, 'planning': {}}
    for item in releases:
        ingest(cache, {'ocid': 'ocds-h6vhtk-000001', 'tag': ['award'], 'buyer': {'name': 'Council'}, 'tender': {'title': 'Fire alarm maintenance', 'status': 'complete', 'lots': [{'id': '1'}]}, **item})
    return notices(cache['tenders']['ocds-h6vhtk-000001'], cache['processes']['ocds-h6vhtk-000001']['releases'], TODAY)


def test_amended_notice_replaces_the_end_date_and_supplier():
    first = {'id': '000001-2024', 'date': '2024-01-01T00:00:00Z', 'awards': [{'id': 'a', 'relatedLots': ['1'], 'suppliers': [{'name': 'Old Ltd'}], 'contractPeriod': {'endDate': '2026-12-31'}}]}
    second = {'id': '000002-2026', 'date': '2026-06-01T00:00:00Z', 'tag': ['contractAmendment'], 'awards': [{'id': 'a', 'relatedLots': ['1'], 'suppliers': [{'name': 'New Ltd'}], 'contractPeriod': {'endDate': '2028-12-31'}}]}
    found = _process(second, first)[0]
    assert found['end'] == '2028-12-31' and found['suppliers'] == ['New Ltd'] and found['url'].endswith('000002-2026')


def test_terminated_contract_stops_being_a_contract():
    first = {'id': '000001-2024', 'date': '2024-01-01T00:00:00Z', 'awards': [{'id': 'a', 'relatedLots': ['1'], 'suppliers': [{'name': 'Old Ltd'}]}], 'contracts': [{'id': 'c', 'awardID': 'a', 'period': {'endDate': '2027-12-31'}}]}
    second = {'id': '000002-2026', 'date': '2026-06-01T00:00:00Z', 'awards': [{'id': 'a', 'relatedLots': ['1'], 'suppliers': [{'name': 'Old Ltd'}]}], 'contracts': [{'id': 'c', 'awardID': 'a', 'status': 'terminated'}]}
    assert _process(first, second) == []
