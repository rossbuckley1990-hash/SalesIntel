"""Regression tests for the opportunity-quality defects found in the PR #9 adversarial review.

Each test was written to fail against the code before its fix, so the defect it describes cannot quietly return."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.ingestion import adjacent_works as aw
from app.models.crm import Contact, FunnelEvent
from app.models.prospect import Prospect
from app.services import committee, jobs, navigator
from app.services.shadow_fixtures import load
from tenancy_support import hosted  # noqa: F401
from test_shadow_radar import workspace

NOW = datetime(2026, 11, 5, tzinfo=UTC)
CAPTURE = json.loads((Path(__file__).parents[1] / 'reference_data' / 'adjacent_works_capture_2026-11-05.json').read_text())


def prospect(h, org, name, signals, services=('fire_alarm',)):
    data = {"name": name, "website": "", "sector": "Logistics", "location": "Leeds, West Yorkshire", "company_number": "", "size": "",
            "headline": signals[0]['title'] if signals else '', "summary": "s", "signals": signals, "timing_clues": [],
            "incumbent": {"name": "", "detail": "", "basis": "unknown", "source_url": ""}, "competitors": [], "people": [], "contact_routes": [],
            "approach": {"angle": "", "opening_line": "", "offer": "", "questions": []}, "services": list(services), "unknowns": []}
    with h.as_workspace(org) as db:
        row = Prospect(dedup_key=name.lower(), name=name, status='new', data=data, created_at=NOW, updated_at=NOW)
        db.add(row)
        db.commit()
        return row.id


def signal(kind, title, url='https://news.example/story', basis='stated'):
    return {"type": kind, "title": title, "detail": "d", "date": "2026-10-01", "basis": basis, "direction": "supports", "source_url": url}


# 1 ------------------------------------------------------------------ plays follow the evidence

def test_a_private_prospect_is_a_new_site_play_only_with_sourced_new_site_evidence(hosted):
    h = hosted
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    cases = {
        'Example Leader Change Ltd': ([signal('leadership_change', 'New operations director')], 'develop'),
        'Example Unsourced Site Ltd': ([signal('new_site', 'Rumoured new depot', url='')], 'develop'),
        'Example Supplier Trouble Ltd': ([signal('incumbent_poor_performance', 'Alarm contractor criticised in audit')], 'supplier_review'),
        'Example New Hub Ltd': ([signal('new_site', 'New Wakefield distribution centre announced')], 'new_site'),
    }
    for name, (signals, expected) in cases.items():
        pid = prospect(h, org, name, signals)
        account = alice.post(f'/api/si/discover/pr:{pid}/account', json={}).json()['account_id']
        play = alice.get(f'/api/si/accounts/{account}/play').json()
        assert play['play'] == expected, name


# 2 ------------------------------------------------------------------ a contact detail belongs to a person only if its source says so

def test_a_route_is_never_tied_to_a_person_its_source_does_not_name(hosted):
    h = hosted
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    account = alice.post('/api/si/accounts', json={'name': 'Harbourside Community Health'}).json()['account_id']
    person = navigator.Candidate('person', 'Morgan Reid', role='Director of Estates and Facilities', source='web_research',
                                 source_url='https://www.harbourside-health.example/about/estates',
                                 quote='Morgan Reid, Director of Estates and Facilities at Harbourside Community Health')
    email = navigator.Candidate('email', 'estates@harbourside-health.example', person='Morgan Reid', label='Estates enquiries', source='web_research',
                                source_url='https://www.harbourside-health.example/about/estates', quote='Estates enquiries: estates@harbourside-health.example')
    with h.as_workspace(org) as db:
        from app.models.crm import Account
        navigator.save(db, db.get(Account, account), [(person, 'public_source', ['named']), (email, 'public_source', ['stated'])], 0, '')
        db.commit()
        route = db.scalar(select(Contact).where(Contact.account_id == account, Contact.email == 'estates@harbourside-health.example'))
        assert route.name is None  # the model said it was Morgan's; the page does not
        assert committee.level(route)['level'] == 5  # a departmental route, not a named person's address


def test_an_address_on_a_page_does_not_verify_the_person_it_is_attached_to(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    account = alice.post('/api/si/accounts', json={'name': 'Harbourside Community Health', 'website': 'https://www.harbourside-health.example'}).json()['account_id']
    added = alice.post(f'/api/si/accounts/{account}/contacts', json={'name': 'Pat Lee', 'role': 'Facilities Manager', 'email': 'estates@harbourside-health.example'}).json()
    r = alice.post(f'/api/si/accounts/{account}/gaps', json={'gap': 'verify_contact', 'subject': str(added['id'])}).json()
    jobs.drain(h.engine)
    result = alice.get(f"/api/si/gaps/{r['id']}").json()
    assert result['status'] == 'partial' and 'Pat Lee' in result['summary']  # the address is published, but not as Pat Lee's
    with h.system() as db:
        c = db.get(Contact, added['id'])
        assert c.verified_at is None and c.quality != 'public_source'  # not upgraded on an unproven association


def test_a_named_contact_whose_source_does_not_name_them_is_not_publicly_sourced():
    c = Contact(account_id=1, name='Jo Bloggs', role='Facilities Manager', email='jo@x.example', basis='published', status='unverified', quality='public_source',
                source_url='https://x.example/a', source_quote='Facilities enquiries: jo@x.example', flags=[], use_restriction='', route_kind='direct_email',
                created_at=NOW, updated_at=NOW)
    assert committee.level(c)['level'] == 4 and 'does not name' in committee.level(c)['detail']


# 3 ------------------------------------------------------------------ identity is never merged on a name alone

def test_two_organisations_with_the_same_name_are_not_merged_on_the_list(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    prospect(h, org, 'Harbourside Community Health', [signal('expansion', 'A logistics firm of the same name expands its fleet')])
    rows = [x for x in alice.get('/api/si/best', params={'limit': 40}).json()['items'] if x['organisation'] == 'Harbourside Community Health']
    assert len(rows) == 2 and {r['type'] for r in rows} == {'shadow', 'private'}  # a public trust and a private firm stay separate


# 4 ------------------------------------------------------------------ exposure, not API reads

def test_reading_the_list_is_not_counted_as_showing_it(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    items = alice.get('/api/si/best').json()['items']
    alice.get('/api/si/best')
    with h.system() as db:
        assert not db.scalars(select(FunnelEvent).where(FunnelEvent.event == 'lead_presented')).all()  # an API read is not exposure
    key = items[0]['key']
    assert alice.post('/api/si/best/seen', json={'keys': [key]}).status_code == 200
    alice.post('/api/si/best/seen', json={'keys': [key]})
    assert alice.post('/api/si/best/seen', json={'keys': ['DROP TABLE']}).status_code == 422
    with h.system() as db:
        assert [e.ref for e in db.scalars(select(FunnelEvent).where(FunnelEvent.event == 'lead_presented'))] == [key]  # once a day


# 5 ------------------------------------------------------------------ the classifier

def test_a_golf_course_irrigation_system_is_not_building_works():
    notice = next(n for n in CAPTURE['notices'] if 'Irrigation' in n['title'])
    assert 'Golf Course' in notice['title'] and aw.classify(notice) is None


# ------------------------------------------------------------------ paid research needs an approved budget, with a hard ceiling

def test_live_paid_research_needs_an_approved_budget_and_stops_at_it(hosted, monkeypatch):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    from app.services import spend
    monkeypatch.setattr(spend, 'live_provider', lambda: True)  # as if a real, paid provider were configured
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    account = alice.post('/api/si/accounts', json={'name': 'Example Budget Test Ltd'}).json()['account_id']
    refused = alice.post(f'/api/si/accounts/{account}/investigate', json={})
    assert refused.status_code == 409 and 'approved by an administrator' in refused.json()['detail']
    with h.system() as db:
        from app.models.acquisition import ResearchJob
        assert not db.scalars(select(ResearchJob)).all()  # nothing queued, nothing charged
    assert alice.get('/api/si/research-budget').json()['approved'] is False
    # A salesperson cannot approve spending; an administrator can, and it is audited.
    bob = h.client('bob', 'bob@alpha.example', 'Bob')
    token = alice.post('/api/workspace/invitations', json={'email': 'bob@alpha.example', 'role': 'salesperson'}).json()['token']
    bob.post('/api/invitations/accept', json={'token': token})
    bob = h.client('bob', 'bob@alpha.example', 'Bob', workspace=org)
    assert bob.post('/api/si/research-budget', json={'amount_cents': 500}).status_code == 403
    approved = alice.post('/api/si/research-budget', json={'amount_cents': 500, 'note': 'Pilot evaluation, five investigations max'}).json()
    assert approved['approved_cents'] == 500 and approved['remaining_cents'] == 500
    started = alice.post(f'/api/si/accounts/{account}/investigate', json={}).json()
    assert started['job']['status'] == 'queued' and alice.get('/api/si/research-budget').json()['reserved_cents'] == 400
    second = alice.post('/api/si/accounts', json={'name': 'Example Second Ltd'}).json()['account_id']
    over = alice.post(f'/api/si/accounts/{second}/investigate', json={})
    assert over.status_code == 409 and 'used up' in over.json()['detail']  # the ceiling holds: 400 + 400 > 500
    jobs.drain(h.engine)  # the job settles: the reservation becomes what it actually cost
    after = alice.get('/api/si/research-budget').json()
    assert after['reserved_cents'] == 0 and after['spent_cents'] > 0 and after['spent_cents'] <= 500
    with h.system() as db:
        from app.models.tenancy import WorkspaceAuditEvent
        assert db.scalar(select(WorkspaceAuditEvent).where(WorkspaceAuditEvent.action == 'budget_up')).detail['added_cents'] == 500


# ------------------------------------------------------------------ a focused day, with one grounded next step

def test_the_daily_list_is_focused_and_counts_the_rest(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=True)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    best = alice.get('/api/si/best').json()
    urgent = [x for x in best['items'] if x['tier'] != 'watch']
    assert len(best['items']) <= 10 and best['in_view'] > 0
    assert len(urgent) == len(best['items']) or len(urgent) < 3  # "keep in view" leads fill the list only on a quiet day
    assert best['total'] == sum(best['tiers'].values())


def test_next_actions_are_built_from_the_lead_s_own_evidence():
    from app.services.best import next_action
    who = {'roles': ['Procurement or category manager'], 'routes_saved': 0, 'summary': ''}
    ending = {'organisation': 'Example Council', 'kind': 'contract_ending', 'type': 'public', 'supplier': 'Sample Fire Services Ltd', 'timing': '2027-04-04',
              'brief': {'who': who, 'next': 'generic'}, 'why_now': 'x', 'title': 'Fire alarm maintenance'}
    step = next_action(ending, None, {'capabilities': []})
    assert 'Sample Fire Services Ltd' in step and '4 April 2027' in step and 're-tender' in step
    tender = {**ending, 'kind': 'published_procurement', 'timing': '2026-11-20'}
    step = next_action(tender, None, {'capabilities': ['BAFE SP203-1', 'NSI Gold']})
    assert '20 November 2026' in step and 'BAFE SP203-1' in step and "buyer's portal" in step
    promised = next_action(ending, {'requirement': {'text': 'Annual servicing at 14 schemes', 'on': '2026-11-01'}, 'open_deals': 0, 'overdue': []}, {})
    assert promised.startswith('Qualify it') and 'Annual servicing at 14 schemes' in promised


def test_an_investigation_without_a_radar_hypothesis_tests_the_account_s_own_evidence(hosted):
    h = hosted
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    pid = prospect(h, org, 'Example New Hub Ltd', [signal('new_site', 'New Wakefield distribution centre announced')])
    account = alice.post(f'/api/si/discover/pr:{pid}/account', json={}).json()['account_id']
    from app.models.crm import Account
    from app.services import investigator
    with h.as_workspace(org) as db:
        questions = investigator.plan(None, investigator.evidence_questions(db, db.get(Account, account)))
    texts = [q['question'] for q in questions]
    assert any('New Wakefield distribution centre announced' in t for t in texts)
    assert any(q['purpose'] == 'challenge' and 'already contracted' in q['question'] for q in questions)  # it tries to undo its own reason


# ------------------------------------------------------------------ found by the evaluation: adjacent services are not "what you sell"

def test_adjacent_fire_work_is_its_own_service_not_fire_alarms():
    from app.services.si_core import _services_from_title
    assert _services_from_title('Fire Risk Assessments - Domestic') == ['fire_risk_assessment']
    assert _services_from_title('Service, Maintenance and Purchase of Fire Extinguishers') == ['extinguishers']
    assert _services_from_title('Fire doors and compartmentation works') == ['passive_fire']
    assert _services_from_title('Fire Alarms & Emergency Lighting') == ['emergency_lighting', 'fire_alarm']


def test_a_near_deadline_does_not_put_an_unmatched_service_on_the_daily_list(hosted, monkeypatch):
    h = hosted
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')  # sells fire alarm and access control, in England
    from app.services import best, si_core

    def lead(key, title, services, nation='England'):
        x = {'key': key, 'type': 'public', 'organisation': f'Example {key}', 'title': title, 'kind': 'published_procurement', 'kind_label': 'Published procurement',
             'basis': 'published', 'status': 'new', 'account_id': None, 'days': 5, 'timing': '2026-11-10', 'services': services, 'nation': nation,
             'region': None, 'value': None, 'category': 'live_procurement', 'why_now': 'Tender open now.'}
        x['brief'] = si_core._brief(x, x['kind'], {'services': ['fire_alarm', 'access_control'], 'territory': ['England'], 'sectors': []}, '', [], [], 0, 0)
        return x
    monkeypatch.setattr(si_core, 'discover_items', lambda db, **kw: [lead('mo:1', 'Fire risk assessments', ['fire_risk_assessment']),
                                                                     lead('mo:2', 'Fire alarm servicing', ['fire_alarm']), lead('mo:3', 'Fire safety works', []),
                                                                     lead('mo:4', 'Fire alarm servicing, Belfast', ['fire_alarm'], nation='Northern Ireland')])
    strict = {x['key']: x for x in alice.get('/api/si/best').json()['items']}
    assert strict['mo:2']['tier'] == 'act_now'
    assert 'mo:1' not in strict  # outside what you sell: set aside
    assert 'mo:3' not in strict or strict['mo:3']['tier'] == 'watch'  # unknown service is not promoted by a deadline
    assert 'mo:4' not in strict or strict['mo:4']['tier'] == 'watch'  # outside the territory you cover: never promoted by a deadline
    with h.system() as db:  # PR #8's behaviour, kept as an evaluation arm
        loose = {x['key']: x['tier'] for x in best.opportunities(db, strict_service=False)['items']}
    assert loose['mo:3'] == 'act_now'  # what PR #8 did: a deadline alone promoted an unidentified service


def test_a_free_text_location_is_matched_to_territory_without_guessing():
    from app.services.si_core import _fit
    prefs = {'services': ['fire_alarm'], 'territory': ['England'], 'sectors': []}
    fit = lambda place: _fit({'services': ['fire_alarm'], 'nation': None, 'region': place, 'title': 'x'}, prefs, '')  # noqa: E731
    assert 'In your territory: England' in fit('Selby, North Yorkshire')['matched']  # an English region is England
    assert 'Outside your recorded territory' in fit('Cardiff, Wales')['gaps']  # a named nation outside it
    assert not fit('Glasgow')['gaps'] and 'Location not confirmed against your territory' in fit('Glasgow')['unknown']  # unknown, not "outside"


def test_an_expected_tender_date_is_not_called_a_deadline():
    from app.services.best import _tier
    lead = {'kind': 'published_procurement', 'days': 5, 'type': 'public', 'timing_label': 'published expected date', 'category': 'official_early_signal'}
    assert _tier(lead, None) == ('act_now', ['Published expected tender date in 5 days'])
    assert _tier({**lead, 'timing_label': 'published deadline'}, None)[1] == ['Published deadline in 5 days']
