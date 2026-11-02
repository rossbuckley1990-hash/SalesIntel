"""The inference engine, including its demonstrations against false claims."""
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import Base, get_db
from app.ingestion.market_public_signals import judgement_links, parse_gazette, read_judgement
from app.intelligence.signal_backtest import fisher_greater, prospective_scorecard, run_backtest, wilson
from app.intelligence.signal_inference import (TAXONOMY, apply_contradictions, arbitrate, assess, buyer_hypotheses, competitor_group, competitor_hypotheses, contract_hypotheses, council_key, evidence_state, fire_service_rises, observation, procurement_observations)
from app.main import create_app
from app.models.market_inference import MarketHypothesis, MarketHypothesisRevision, MarketObservation
from app.models.market_network import MarketSourceState
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.services.market_inference import collect_company_signals, collect_public_signals, curated_observations, store_observations
from app.services.market_network import ingest_market_release
from app.services.market_opportunities import refresh_market_opportunities
from app.services.renewal_radar import run_daily_cycle

TODAY = date(2026, 11, 2)
NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)


def make_db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def view(**fields):
    base = {'id': 'a', 'url': 'https://example.test/contract', 'ocid': 'ocds-h6vhtk-000001', 'lot': '', 'title': 'Fire alarm maintenance', 'buyer': 'Example Council', 'published': '2024-01-01', 'start': '2024-01-01', 'end': '2027-06-30', 'value': 300000.0,
            'fit': 'core', 'suppliers': ['Acme Fire Ltd'], 'incumbent': 'Acme Fire Ltd', 'own_group': False, 'extension_mentioned': False, 'successor_url': None, 'end_estimated': False, 'timing': 'act_now'}
    return {**base, **fields}


def seen(signal, group='fire_service', day=date(2026, 8, 1), **fields):
    fields.setdefault('buyer', 'Example Council')
    fields.setdefault('fams', ['fire_alarm'])
    return {**observation(signal, statement=f'{signal} statement', occurred=day, url=f'https://example.test/{signal}/{group}/{day}', group=group, reliability='statutory_record', **fields), 'retracted_on': None}


def test_two_signals_from_one_source_are_not_independent():
    assert evidence_state([seen('remedial_programme', 'procurement'), seen('tender_abandoned', 'procurement')], [])[0] == 'same_source_repeated'
    assert evidence_state([seen('remedial_programme', 'procurement'), seen('false_alarm_rise')], [])[0] == 'independently_corroborated'


def test_corroborated_problem_near_renewal_is_pursue_and_makes_no_allegation():
    found = contract_hypotheses([view()], [seen('false_alarm_rise'), seen('remedial_programme', 'procurement')], TODAY)
    assessment = found['vulnerability:ocds-h6vhtk-000001:'][0]
    assert assessment['decision'] == 'pursue' and assessment['label'].startswith('Potential incumbent vulnerability')
    contractor = next(x for x in assessment['explanations'] if x['explanation'] == 'contractor_delivery')
    assert contractor['status'] == 'not_established' and 'Whether the named contractor is responsible.' in assessment['unknowns'] and 'not a finding' in assessment['caution']
    assert not any('poor' in x.lower() for x in assessment['actions'])


def test_one_line_of_evidence_is_only_verify():
    assert contract_hypotheses([view()], [seen('false_alarm_rise')], TODAY)['vulnerability:ocds-h6vhtk-000001:'][0]['decision'] == 'verify'


def test_test_e_ordinary_events_never_become_an_underperformance_claim():
    # Spending, recruitment and reviews have no signal type at all, so they cannot enter.
    with pytest.raises(ValueError):
        with make_db() as db:
            store_observations(db, [{**seen('false_alarm_rise'), 'signal_type': 'recruitment_advert'}], NOW)
    # An unsubstantiated complaint can only ever ask a question.
    complaint = seen('customer_concern_published', 'local_press', attribution='none')
    assessment = contract_hypotheses([view()], [complaint], TODAY)['vulnerability:ocds-h6vhtk-000001:'][0]
    assert assessment['decision'] == 'verify' and next(x for x in assessment['explanations'] if x['explanation'] == 'contractor_delivery')['status'] == 'not_established'


def test_emergency_lighting_is_not_an_emergency_procurement():
    class Row:
        id, ocid, source_url, published_at = 1, 'ocds-x', 'https://example.test/1', datetime(2026, 1, 1, tzinfo=UTC)
        raw = {'tag': ['award'], 'buyer': {'name': 'Example Council'}, 'tender': {'title': 'Emergency lighting and emergency call-out maintenance', 'description': 'Emergency repairs to fire alarms.'}}
    assert not [x for x in procurement_observations([Row]) if x['signal_type'] == 'emergency_procurement']
    Row.raw = {'tag': ['award'], 'buyer': {'name': 'Example Council'}, 'tender': {'title': 'Emergency appointment for fire alarm maintenance', 'description': ''}}
    assert [x for x in procurement_observations([Row]) if x['signal_type'] == 'emergency_procurement']


def test_test_f_contradiction_withdraws_a_hypothesis_and_keeps_the_history():
    with make_db() as db:
        ingest_market_release(db, {'source_key': 'find_a_tender', 'release_id': '000001-2024', 'ocid': 'ocds-h6vhtk-000001', 'source_url': 'https://www.find-tender.service.gov.uk/Notice/000001-2024', 'published_at': datetime(2024, 7, 1, tzinfo=UTC), 'retrieved_at': NOW,
                                   'raw': {'id': '000001-2024', 'ocid': 'ocds-h6vhtk-000001', 'date': '2024-07-01T00:00:00Z', 'tag': ['award'], 'buyer': {'name': 'Example Council'}, 'tender': {'title': 'Fire alarm maintenance', 'status': 'complete'},
                                           'awards': [{'id': '1', 'status': 'active', 'value': {'amount': 300000, 'currency': 'GBP'}, 'contractPeriod': {'startDate': '2024-07-01', 'endDate': '2027-06-30'}, 'suppliers': [{'name': 'Acme Fire Ltd'}]}]}})
        store_observations(db, [{k: v for k, v in x.items() if k != 'retracted_on'} for x in (seen('false_alarm_rise'), seen('remedial_programme', 'public_document'))], NOW)
        db.commit()
        refresh_market_opportunities(db, now=NOW)
        db.commit()
        item = db.scalar(select(MarketHypothesis))
        assert item.decision == 'pursue'
        opportunity = db.scalar(select(MarketOpportunity))
        assert db.get(MarketOpportunityRevision, opportunity.current_revision_id).result['signals'][0]['decision'] == 'pursue'
        resolved = seen('issue_resolved', 'public_document', day=date(2026, 10, 1), attribution='customer')
        resolved['statement'] = 'The customer reports the alarm faults were caused by building works and are resolved.'
        store_observations(db, [{k: v for k, v in resolved.items() if k != 'retracted_on'}], NOW)
        db.commit()
        refresh_market_opportunities(db, now=NOW + timedelta(days=1))
        db.commit()
        assert item.decision == 'dismiss' and item.state == 'withdrawn' and item.evidence_state == 'contradicted'
        assert db.scalar(select(func.count()).select_from(MarketHypothesisRevision).where(MarketHypothesisRevision.hypothesis_id == item.id)) == 2
        assert 'signals' not in db.get(MarketOpportunityRevision, opportunity.current_revision_id).result and opportunity.state == 'suggested'


def test_a_good_grade_answers_only_the_regulator_finding():
    finding, rise = seen('regulator_compliance_finding', 'regulator', day=date(2026, 1, 1)), seen('false_alarm_rise')
    grade = seen('issue_resolved', 'regulator', day=date(2026, 9, 1))
    grade['detail'] = {'answers': ['regulator_compliance_finding']}
    standing, against = apply_contradictions([finding, rise], [grade])
    assert [x['signal_type'] for x in standing] == ['false_alarm_rise'] and against == [grade]


def test_a_signal_does_not_spread_to_a_different_service_or_customer():
    cctv = view(title='CCTV maintenance')
    assert not contract_hypotheses([cctv], [seen('remedial_programme', 'procurement')], TODAY)
    assert not contract_hypotheses([view(buyer='Other Council')], [seen('false_alarm_rise')], TODAY)


def test_a_finding_about_the_customer_never_marks_its_contractor():
    finding = seen('regulator_compliance_finding', 'regulator', fams=['fire_risk_assessment'])
    assert not contract_hypotheses([view()], [finding], TODAY)
    assessment = buyer_hypotheses([view()], [finding], [], TODAY)[f"requirement:{council_key('Example Council')}"][0]
    assert next(x for x in assessment['explanations'] if x['explanation'] == 'deferred_compliance')['status'] == 'supported' and assessment['supplier'] is None


def test_a_cctv_notice_does_not_corroborate_a_fire_safety_finding():
    finding, cctv = seen('regulator_compliance_finding', 'regulator', fams=[]), seen('market_engagement', 'procurement', fams=['cctv'])
    assert buyer_hypotheses([view()], [finding, cctv], [], TODAY)[f"requirement:{council_key('Example Council')}"][0]['decision'] == 'verify'


def test_a_supplier_change_stays_with_the_contract_it_describes():
    change = seen('supplier_replaced', 'procurement', fams=['cctv'])
    change['detail'] = {'old_title': 'CCTV network maintenance', 'new_title': 'CCTV network repairs'}
    assert not contract_hypotheses([view(title='CCTV hub staffing')], [change], TODAY)


def test_a_same_system_notice_at_another_site_is_not_this_contract():
    award = seen('short_term_award', 'procurement')
    award['detail'] = {'title': 'Battersea Sports Centre fire alarm panel'}
    assert not contract_hypotheses([view(title='Housing fire alarm and emergency lighting maintenance')], [award], TODAY)


def test_a_spelling_difference_is_not_a_supplier_change():
    from app.intelligence.signal_inference import sequence_observations
    first = view(title='CCTV network maintenance', suppliers=['Net View Systems'], incumbent='Net View Systems', end='2026-12-31', published='2023-01-01')
    second = view(title='CCTV network maintenance', suppliers=['NetView Systems Ltd'], incumbent='NetView Systems Ltd', end='2030-12-31', published='2026-06-01', url='https://example.test/new')
    assert not [x for x in sequence_observations([first, second], []) if x['signal_type'] == 'supplier_replaced']


def test_stale_evidence_is_ignored_and_future_evidence_is_invisible():
    assert not contract_hypotheses([view()], [seen('false_alarm_rise', day=date(2024, 6, 1))], TODAY)
    assert not contract_hypotheses([view()], [seen('false_alarm_rise', day=date(2026, 11, 20))], TODAY)


def test_mitie_contract_is_retention_not_a_competitive_opening():
    found = contract_hypotheses([view(own_group=True, suppliers=['Mitie Security Limited'], incumbent='Mitie Security Limited')], [seen('false_alarm_rise')], TODAY)
    assert list(found) == ['retention:ocds-h6vhtk-000001:'] and found['retention:ocds-h6vhtk-000001:'][0]['actions'][0].startswith('Escalate')


def test_replaced_contract_and_contract_beyond_window_are_not_leads():
    assert contract_hypotheses([view(successor_url='https://example.test/new')], [seen('false_alarm_rise')], TODAY)['vulnerability:ocds-h6vhtk-000001:'][0]['decision'] == 'dismiss'
    assert contract_hypotheses([view(end='2029-06-30')], [seen('false_alarm_rise')], TODAY)['vulnerability:ocds-h6vhtk-000001:'][0]['decision'] == 'monitor'


def test_arbitration_never_promotes_a_framework_or_competitor_note():
    shared = dict(timing='renewal_window', state='independently_corroborated', attribution_found=False, has_value=True, stale=False, replaced=False, own_group=False)
    assert arbitrate('incumbent_vulnerability', fit='framework', **shared)[0] == 'monitor' and arbitrate('competitor_strength', fit=None, **shared)[0] == 'monitor'


def test_hidden_requirement_needs_real_pressure_and_a_contract_is_not_corroboration():
    views = [view()]
    regulator = seen('regulator_compliance_finding', 'regulator', fams=[])
    assert buyer_hypotheses(views, [regulator], [], TODAY)[f"requirement:{council_key('Example Council')}"][0]['evidence_state'] == 'single_source'
    assert not buyer_hypotheses(views, [seen('market_engagement', 'procurement')], [], TODAY)
    both = buyer_hypotheses(views, [regulator, seen('remedial_programme', 'procurement')], [], TODAY)[f"requirement:{council_key('Example Council')}"][0]
    assert both['decision'] == 'pursue'
    live = [{'type': 'Contract', 'status': 'Open', 'published': '2026-10-01', 'buyer': 'Example Council'}]
    assert not buyer_hypotheses(views, [regulator], live, TODAY)


def test_council_name_variants_join_but_housing_associations_do_not():
    assert council_key('London Borough of Newham') == council_key('Newham London Borough Council') == council_key('LONDON BOROUGH OF NEWHAM') == 'newham'
    assert council_key('Leeds City Council') != council_key('Leeds Federated Housing Association')


def test_competitor_groups_join_spellings_and_keep_three_outputs_apart():
    assert competitor_group('Chubb Fire and Security Ltd') == competitor_group('CHUBB FIRE & SECURITY LIMITED') == 'Chubb Fire & Security'
    wins = [view(title=f'Fire alarm maintenance {n}', ocid=f'o{n}', published='2026-06-01', suppliers=['Trinity Fire and Security Systems Ltd']) for n in range(3)]
    insolvent = seen('supplier_insolvency', 'gazette', buyer=None, supplier='Weak Fire Ltd', fams=[])
    found = competitor_hypotheses(wins, [insolvent], TODAY)
    assert found['strength:Trinity Fire & Security'][0]['decision'] == 'monitor' and found['competitive-risk:weak fire'][0]['kind'] == 'competitor_vulnerability'


def test_mitie_is_never_scored_as_a_competitor():
    assert not competitor_hypotheses([view(title=f'CCTV {n}', published='2026-06-01', suppliers=['Mitie Security Ltd']) for n in range(4)], [], TODAY)


def test_fire_rise_needs_a_real_change_and_ignores_the_policy_period():
    stable = [('s', date(2025, 1, 1) + timedelta(days=30 * n)) for n in range(20)]
    assert not fire_service_rises(stable, as_of=TODAY)
    rising = [('s', date(2025, 3, 1)), *[('s', date(2026, 3, 1) + timedelta(days=9 * n)) for n in range(14)]]
    assert fire_service_rises(rising, as_of=TODAY)[0]['recent'] >= 6
    assert not fire_service_rises(rising, as_of=date(2025, 1, 1))


def test_future_incident_cannot_reach_an_earlier_decision():
    late = [('s', date(2026, 8, 1) + timedelta(days=n)) for n in range(10)]
    assert not fire_service_rises(late, as_of=date(2026, 8, 1))


def test_backtest_cannot_see_signals_published_after_the_decision():
    contract = view(end='2025-06-30', start='2022-07-01', published='2022-06-01')
    later = {'id': 'n', 'ocid': 'ocds-new', 'title': 'Fire alarm maintenance', 'buyer': 'Example Council', 'published': '2025-01-01', 'type': 'Contract', 'status': 'Closed'}
    early = seen('tender_abandoned', 'procurement', day=date(2024, 1, 1))
    leaked = seen('tender_abandoned', 'procurement', day=date(2024, 12, 1))
    assert run_backtest([contract], [later], [early])['arms']['indirect_signals']['flagged'] == 1
    assert run_backtest([contract], [later], [leaked])['arms']['indirect_signals']['flagged'] == 0


def test_statistics_and_prospective_scorecard():
    assert wilson(0, 0) is None and wilson(5, 10)[0] < 0.5 < wilson(5, 10)[1]
    assert fisher_greater(1, 0, 0, 1) == 0.5
    notices = [{'title': 'Fire alarm maintenance', 'buyer': 'Example Council', 'published': '2027-01-01', 'id': 'n', 'type': 'Contract'}]
    made = [{'decision': 'pursue', 'buyer': 'Example Council', 'kind': 'hidden_requirement', 'first_seen': TODAY}, {'decision': 'monitor', 'buyer': 'Example Council', 'kind': 'x', 'first_seen': TODAY}]
    assert prospective_scorecard(made, notices, date(2027, 2, 1))['followed_by_a_notice'] == 1 and prospective_scorecard(made, notices, date(2027, 2, 1))['hypotheses_on_record'] == 1


GAZETTE = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x</id><title>ACME FIRE LIMITED</title><published>2026-10-30T00:00:00Z</published><link href="https://www.thegazette.co.uk/notice/1"/><link rel="self" href="https://www.thegazette.co.uk/id/notice/1"/><content>Company Number: 01234567 appointed liquidator</content></entry></feed>'''


def test_gazette_feed_parses_name_link_and_number():
    assert parse_gazette(GAZETTE) == [{'title': 'ACME FIRE LIMITED', 'url': 'https://www.thegazette.co.uk/notice/1', 'published': '2026-10-30', 'summary': 'Company Number: 01234567 appointed liquidator', 'company_number': '01234567'}]


def _public_transport(request):
    url = str(request.url)
    if 'search.json' in url:
        return httpx.Response(200, json={'results': [{'title': 'Example Council', 'link': '/government/publications/example', 'public_timestamp': '2026-10-28T09:00:00Z'}, {'title': 'Unknown Housing Limited', 'link': '/government/publications/unknown', 'public_timestamp': '2026-10-28T09:00:00Z'}]})
    if url.endswith('/government/publications/example'):
        return httpx.Response(200, json={'details': {'attachments': [{'title': 'Example Council - Regulatory Judgement', 'url': '/government/publications/example/judgement'}]}})
    if url.endswith('/judgement'):
        return httpx.Response(200, json={'details': {'body': '<p>We have concluded C3.</p><p>The board reviewed fire doors.</p><p>Almost 900 fire safety remedial actions are overdue.</p>'}})
    if 'thegazette' in url:
        return httpx.Response(200, content=GAZETTE)
    return httpx.Response(404)


def test_judgement_reader_keeps_only_grade_and_fire_sentences():
    with httpx.Client(transport=httpx.MockTransport(_public_transport)) as http:
        assert [x['title'] for x in judgement_links(http)][0] == 'Example Council'
        result = read_judgement(http, '/government/publications/example', sleep=lambda _: None)
    assert result['grades'] == [3] and result['fire_sentences'] == ['Almost 900 fire safety remedial actions are overdue.']


def test_collection_links_only_known_customers_and_runs_once_a_day():
    from app.models.market_contract import MarketContract
    with make_db() as db, httpx.Client(transport=httpx.MockTransport(_public_transport)) as http:
        db.add(MarketContract(canonical_key='k', buyer='Example Council', supplier='Acme Fire Ltd', title='Fire alarm maintenance', fit='core', lifecycle_status='in_term_published', facts={}, first_seen=NOW, last_evaluated=NOW))
        db.commit()
        result = collect_public_signals(db, now=NOW, http=http, sleep=lambda _: None, curated=Path('no-such-file'))
        assert result['judgements_read'] == 1
        rows = db.scalars(select(MarketObservation)).all()
        assert {x.signal_type for x in rows} == {'regulator_compliance_finding', 'supplier_insolvency'} and next(x for x in rows if x.signal_type == 'supplier_insolvency').company_number == '01234567'
        assert collect_public_signals(db, now=NOW, http=http, sleep=lambda _: None) == {'skipped': 'already collected today'}


def test_curated_facts_are_labelled_and_name_a_real_source():
    rows = curated_observations()
    assert rows and all(x['capture'] == 'analyst_assisted' and x['source_url'].startswith('https://') and x['signal_type'] in TAXONOMY for x in rows)


def test_a_refused_source_is_recorded_as_failed_and_does_not_stop_the_cycle():
    with make_db() as db, httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403))) as http:
        with pytest.raises(httpx.HTTPStatusError):
            collect_public_signals(db, now=NOW, http=http, sleep=lambda _: None)
        assert db.get(MarketSourceState, 'market_inference').last_error == 'HTTPStatusError'

        def refused(database, now):
            raise RuntimeError('refused')

        assert run_daily_cycle(db, now=NOW, collect=refused, refresh=False, fetch=lambda *a: None)['incomplete'] is False


def test_same_observation_stored_once():
    with make_db() as db:
        item = {k: v for k, v in seen('false_alarm_rise').items() if k != 'retracted_on'}
        assert store_observations(db, [item], NOW)['new'] == 1 and store_observations(db, [item], NOW)['new'] == 0


def test_a_derived_observation_the_rules_no_longer_produce_is_retracted_with_a_date():
    with make_db() as db:
        store_observations(db, [{k: v for k, v in seen('remedial_programme', 'procurement').items() if k != 'retracted_on'}], NOW)
        db.commit()
        refresh_market_opportunities(db, now=NOW)
        assert db.scalar(select(MarketObservation)).retracted_on == NOW.date()


def test_signal_api_returns_reasoning_with_history():
    with make_db() as db:
        store_observations(db, [{k: v for k, v in x.items() if k != 'retracted_on'} for x in (seen('regulator_compliance_finding', 'regulator', fams=[]), seen('remedial_programme', 'fire_service'))], NOW)
        db.commit()
        refresh_market_opportunities(db, now=NOW)
        db.commit()
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            page = client.get('/api/market-network/signals', params={'decision': 'pursue'}).json()
            assert page['items'][0]['kind'] == 'hidden_requirement' and page['items'][0]['assessment']['explanations']
            assert client.get(f"/api/market-network/signals/{page['items'][0]['id']}/history").json()['items']
            assert client.get('/api/market-network/signals/summary').json()['by_decision']['pursue'] == 1
            found = client.get('/api/market-network/opportunities', params={'category': 'inferred_signal'}).json()
            assert found['total'] == 1 and found['items'][0]['suggestion']['signal']['decision'] == 'pursue'


def _register(company_status='active', overdue=False, controllers=()):
    def handler(request):
        assert request.url.host == 'api.company-information.service.gov.uk'
        if request.url.path.endswith('persons-with-significant-control'):
            return httpx.Response(200, json={'items': list(controllers), 'total_results': len(controllers)})
        return httpx.Response(200, json={'company_number': '01234567', 'company_name': 'ACME FIRE LIMITED', 'company_status': company_status, 'accounts': {'overdue': overdue}, 'has_insolvency_history': False})
    return handler


def _with_key(monkeypatch, value='test-key'):
    monkeypatch.setenv('COMPANIES_HOUSE_API_KEY', value)
    get_settings.cache_clear()


def _company_db():
    from app.models.market_contract import MarketContract
    db = make_db()
    db.add(MarketContract(canonical_key='k', buyer='Example Council', supplier='Acme Fire Ltd', title='Fire alarm maintenance', fit='core', lifecycle_status='in_term_published', category='pre_tender', facts={'company_numbers': ['01234567'], 'suppliers': ['Acme Fire Ltd']}, first_seen=NOW, last_evaluated=NOW))
    db.commit()
    return db


def test_register_status_filing_and_control_change_become_labelled_observations(monkeypatch):
    _with_key(monkeypatch)
    corporate = {'kind': 'corporate-entity-person-with-significant-control', 'name': 'Big Group Ltd', 'notified_on': '2026-03-01', 'natures_of_control': ['ownership-of-shares-75-to-100-percent'], 'identification': {'registration_number': '07654321', 'place_registered': 'Companies House'}}
    with _company_db() as db, httpx.Client(transport=httpx.MockTransport(_register('liquidation', True, [corporate]))) as client:
        result = collect_company_signals(db, now=NOW, client=client, sleep=lambda _: None)
        assert result['companies_checked'] == 1
        rows = {x.signal_type: x for x in db.scalars(select(MarketObservation))}
        assert set(rows) == {'supplier_insolvency', 'supplier_filing_overdue', 'control_change'} and rows['supplier_insolvency'].company_number == '01234567' and rows['supplier_insolvency'].source_group == 'companies_house'
        assert collect_company_signals(db, now=NOW + timedelta(days=1), client=client, sleep=lambda _: None)['companies_checked'] == 0


def test_no_key_means_no_request_and_no_failure(monkeypatch):
    monkeypatch.delenv('COMPANIES_HOUSE_API_KEY', raising=False)
    monkeypatch.setitem(Settings.model_config, 'env_file', None)
    with _company_db() as db:
        assert collect_company_signals(db, now=NOW, client=None) == {'skipped': 'no key configured'}
        assert db.get(MarketSourceState, 'companies_house_signals') is None


def test_a_rejected_key_is_recorded_and_stops_at_once(monkeypatch):
    _with_key(monkeypatch)
    calls = []

    def refused(request):
        calls.append(request.url.path)
        return httpx.Response(401)

    with _company_db() as db, httpx.Client(transport=httpx.MockTransport(refused)) as client:
        with pytest.raises(Exception):
            collect_company_signals(db, now=NOW, client=client, sleep=lambda _: None)
        assert len(calls) == 1 and 'HTTP 401' in db.get(MarketSourceState, 'companies_house_signals').last_error


def test_collect_all_keeps_going_when_one_source_fails(monkeypatch):
    import app.services.market_inference as service

    def broken(db, now=None):
        raise RuntimeError('refused')

    monkeypatch.setattr(service, 'collect_public_signals', broken)
    monkeypatch.setattr(service, 'collect_company_signals', lambda db, now=None: {'companies_checked': 1})
    assert service.collect_all(None, now=NOW) == {'public': {'error': 'RuntimeError'}, 'companies_house': {'companies_checked': 1}}


def test_insolvency_on_a_published_number_links_and_one_late_filing_is_only_watched():
    number = view(company_numbers=['01234567'])
    insolvent = seen('supplier_insolvency', 'companies_house', buyer=None, supplier='Different Trading Name Ltd', fams=[], company_number='01234567')
    found = contract_hypotheses([number], [insolvent], TODAY)['stress:ocds-h6vhtk-000001:'][0]
    assert found['link'] == 'Matched on a published company number.' and found['decision'] == 'verify'
    late = seen('supplier_filing_overdue', 'companies_house', buyer=None, supplier='Different Trading Name Ltd', fams=[], company_number='01234567')
    assert contract_hypotheses([number], [late], TODAY)['stress:ocds-h6vhtk-000001:'][0]['decision'] == 'monitor'
