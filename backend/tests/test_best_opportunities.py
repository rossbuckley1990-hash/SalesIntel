"""The daily intelligence layer: best opportunities, research on demand, contact confidence, guided plays and attribution.

Runs on synthetic and replayed research only (no network, no credit), on SQLite and PostgreSQL with row-level security."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.crm import Account, Contact
from app.models.gaps import GapRequest
from app.services import committee, jobs
from app.services.shadow_fixtures import load
from tenancy_support import hosted  # noqa: F401
from test_shadow_radar import workspace


def harbourside(c):
    return next(x for x in c.get('/api/si/discover', params={'source': 'shadow'}).json()['items'] if x['organisation'].startswith('Harbourside'))


def investigated(h, c):
    lead = harbourside(c)
    account = c.post(f"/api/si/radar/hypotheses/{lead['key'][3:]}/investigate", json={}).json()['account_id']
    jobs.drain(h.engine)
    return lead, account


def ask(h, c, account, gap, subject, **extra):
    r = c.post(f'/api/si/accounts/{account}/gaps', json={'gap': gap, 'subject': subject, **extra})
    assert r.status_code == 200, r.text
    jobs.drain(h.engine)
    return c.get(f"/api/si/gaps/{r.json()['id']}").json()


def test_best_opportunities_are_ranked_by_explained_tiers_never_by_a_score(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    best = alice.get('/api/si/best').json()
    assert best['items'] and set(best['tiers']) <= {'act_now', 'this_week', 'watch'}
    text = json.dumps(best).lower()
    assert 'probability' not in text.replace('no probability is shown', '') and '"score"' not in text and '%' not in json.dumps(best['items'])
    order = {'act_now': 0, 'this_week': 1, 'watch': 2}
    assert [order[x['tier']] for x in best['items']] == sorted(order[x['tier']] for x in best['items'])
    for x in best['items']:
        assert x['why_now'] and x['next'] and x['tier_label']
        if x['tier'] != 'watch':
            assert x['reasons'], x['organisation']  # every promoted lead says why
    h_item = next(x for x in best['items'] if x['organisation'].startswith('Harbourside'))
    assert any('Corroborated by 2 independent sources' in r for r in h_item['reasons'])
    assert h_item['cautions'][0].startswith('Inferred, not advertised')  # an inference is never presented as confirmed
    assert len({x['organisation'] for x in best['items']}) == len(best['items'])  # one row per organisation
    assert best['profile']['basis'] == 'stated' and best['profile']['minimum_won'] == 5  # too few wins to learn from
    # A lead counts as presented only when the interface reports it on screen, once a day (not when the API is read).
    keys = [x['key'] for x in best['items']]
    alice.post('/api/si/best/seen', json={'keys': keys})
    alice.post('/api/si/best/seen', json={'keys': keys})
    from app.models.crm import FunnelEvent
    with h.system() as db:
        refs = [e.ref for e in db.scalars(select(FunnelEvent).where(FunnelEvent.event == 'lead_presented'))]
        assert len(refs) == len(set(refs)) == len(best['items'])


def test_resolve_this_gap_answers_only_from_sources_and_says_so_when_it_cannot(hosted, monkeypatch):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    lead, account = investigated(h, alice)
    alice.patch(f'/api/si/accounts/{account}', json={'website': 'https://www.harbourside-health.example'})

    incumbent = ask(h, alice, account, 'incumbent', 'Current fire and security supplier', lead_key=lead['key'])
    assert incumbent['status'] == 'resolved' and 'Coastline Fire Services' in incumbent['summary']
    assert any(r['reason'].startswith('The page tried to give instructions') for r in incumbent['rejected'])  # injected page refused
    assert all(f['quote'] for f in incumbent['findings']) and incumbent['cost_cents'] > 0 and incumbent['sources'] > 0

    ending = ask(h, alice, account, 'contract_end', 'Contract end date')
    assert ending['status'] == 'conflicting' and {f['answer'] for f in ending['findings']} == {'March 2028', '2027'}  # both shown, neither chosen

    operator = ask(h, alice, account, 'site_operator', 'Who will run the site')
    assert operator['status'] == 'not_found' and operator['findings'] == [] and 'guessed' in operator['summary']  # unknown stays unknown

    role = ask(h, alice, account, 'find_role', 'Estates or property director')
    assert role['status'] == 'resolved' and 'Morgan Reid' in role['summary']

    with h.system() as db:
        email = db.scalar(select(Contact).where(Contact.account_id == account, Contact.email == 'estates@harbourside-health.example'))
        email_id = email.id
    verified = ask(h, alice, account, 'verify_contact', str(email_id))
    assert verified['status'] == 'resolved'
    with h.system() as db:
        c = db.get(Contact, email_id)
        assert c.verified_at is not None and 'harbourside-health.example' in c.verification_method and c.status == 'unverified'  # confirmed published, not "verified" by us

    # A repeated click returns the same request; an explicit refresh asks again.
    again = alice.post(f'/api/si/accounts/{account}/gaps', json={'gap': 'incumbent', 'subject': 'Current fire and security supplier'}).json()
    assert again['id'] == incumbent['id'] and again['reused'] is True
    fresh = alice.post(f'/api/si/accounts/{account}/gaps', json={'gap': 'incumbent', 'subject': 'Current fire and security supplier', 'refresh': True}).json()
    assert fresh['id'] != incumbent['id']
    jobs.drain(h.engine)

    # No research provider here: nothing is searched, nothing is guessed, nothing is charged.
    monkeypatch.setenv('RESEARCH_PROVIDER', 'anthropic')
    monkeypatch.setenv('ANTHROPIC_API_KEY', '')
    from app.config import get_settings
    get_settings.cache_clear()
    offline = ask(h, alice, account, 'site_status', 'Site status')
    assert offline['status'] == 'provider_unavailable' and offline['cost_cents'] == 0 and offline['findings'] == []
    get_settings.cache_clear()

    # The play reads its progress from what was recorded.
    play = alice.get(f'/api/si/accounts/{account}/play').json()
    assert play['play'] == 'new_site' and play['label'] == 'New site'
    steps = {s['key']: s['state'] for s in play['steps']}
    assert steps['evidence'] == 'done' and steps['investigate'] == 'done' and steps['people'] == 'done' and steps['qualify'] == 'todo'
    assert play['next']['key'] == 'approach'  # missing information supports the play, it does not block it
    estates = next(r for r in play['committee']['roles'] if r['key'] == 'estates')
    assert estates['status'] == 'covered' and estates['people'][0]['name'] == 'Morgan Reid' and estates['people'][0]['level'] <= 3

    # Another company sees none of it.
    bob, b_org = workspace(h, 'bob', 'Beta Security Ltd')
    assert bob.get(f"/api/si/gaps/{incumbent['id']}").status_code == 404
    assert bob.post(f'/api/si/accounts/{account}/gaps', json={'gap': 'incumbent', 'subject': 'x'}).status_code == 404
    assert bob.get(f'/api/si/accounts/{account}/play').status_code == 404
    with h.system() as db:
        assert db.scalar(select(GapRequest).where(GapRequest.id == incumbent['id'])).organisation_id != b_org


def test_an_opted_out_contact_is_never_researched(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    _, account = investigated(h, alice)
    with h.system() as db:
        cid = db.scalar(select(Contact.id).where(Contact.account_id == account, Contact.name == 'Morgan Reid'))
    alice.patch(f'/api/si/contacts/{cid}', json={'status': 'do_not_contact'})
    assert alice.post(f'/api/si/accounts/{account}/gaps', json={'gap': 'verify_contact', 'subject': str(cid)}).status_code == 409


def test_contact_confidence_levels_are_stated_not_implied():
    now = datetime.now(UTC)
    base = dict(account_id=1, basis='published', status='unverified', flags=[], use_restriction='', created_at=now, updated_at=now, route_kind='')
    named_public = Contact(name='Morgan Reid', role='Director of Estates', email=None, quality='public_source', source_url='https://x.example/a', source_quote='Morgan Reid, Director', **base)
    role_only = Contact(name=None, role='', label='Estates enquiries', email='estates@x.example', quality='public_source', **{**base, 'route_kind': 'departmental_email'})
    guessed = Contact(name='Pat Lee', role='Facilities Manager', email='pat.lee@x.example', quality='unverified', **{**base, 'basis': 'user_entered'})
    rechecked = Contact(name='Sam Patel', role='Head of Property', quality='public_source', verified_at=now - timedelta(days=10), **{**base, 'status': 'verified'})
    stale = Contact(name='Jo Bloggs', role='Facilities Manager', quality='public_source', source_url='https://x.example/b', source_quote='Jo', source_date='2023-01-01', **base)
    blocked = Contact(name='Al Smith', role='Procurement', quality='public_source', **{**base, 'status': 'do_not_contact'})
    assert committee.level(named_public)['level'] == 3 and committee.level(role_only)['level'] == 5 and committee.level(guessed)['level'] == 4
    assert committee.level(rechecked)['level'] == 1 and committee.level(rechecked)['freshness'] == 'fresh'
    assert committee.level(stale)['freshness'] == 'stale' and committee.level(stale)['usable'] is False
    assert committee.level(blocked)['usable'] is False and committee.level(blocked)['label'] == 'Do not contact'


def test_the_journey_is_attributed_to_its_discovery_without_claiming_causation(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    lead, account = investigated(h, alice)
    with h.system() as db:
        cid = db.scalar(select(Contact.id).where(Contact.account_id == account, Contact.name == 'Morgan Reid'))
    alice.post(f'/api/si/accounts/{account}/drafts', json={'subject': 'Introduction', 'body': 'Dear Morgan Reid, ...', 'contact_id': cid})
    alice.post(f'/api/si/accounts/{account}/activities', json={'kind': 'call', 'summary': 'Spoke to the estates team', 'outcome': 'requirement_captured',
                                                                'requirements': 'Fire alarm and access control for the new centre', 'contact_id': cid})
    deal = alice.post(f'/api/si/accounts/{account}/deals', json={'source_key': lead['key'], 'services': ['fire_alarm'],
                                                                 'qualification': {'requirement': 'Fire alarm for the new centre'}}).json()
    assert alice.patch(f"/api/si/deals/{deal['id']}", json={'stage': 'lost', 'reason': 'Main contractor appointed its own supply chain'}).status_code == 200
    res = alice.get('/api/si/results').json()
    shadow = {s['key']: s['accounts'] for s in res['sources']['shadow']['steps']}
    assert shadow['accepted'] == shadow['investigated'] == shadow['contacts'] == shadow['prepared'] == 1
    assert shadow['outreach'] == shadow['requirement'] == shadow['qualified'] == shadow['lost'] == 1 and shadow['won'] == 0
    assert res['sources']['shadow']['research_cents'] > 0 and 'does not prove' in res['note']
    bob, _ = workspace(h, 'bob', 'Beta Security Ltd')
    assert bob.get('/api/si/results').json()['sources'] == {}  # another company's outcomes are never visible or learned from


def test_an_existing_customer_s_new_site_is_one_account_and_an_expansion_play(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    made = alice.post('/api/si/accounts', json={'name': 'Harbourside Community Health'}).json()
    with h.system() as db:
        db.get(Account, made['account_id']).status = 'customer'  # an existing customer (won before this test)
        db.commit()
    item = next(x for x in alice.get('/api/si/best').json()['items'] if x['organisation'].startswith('Harbourside'))
    lead, account = investigated(h, alice)
    assert account == made['account_id']  # linked to the customer, not a duplicate
    assert len([a for a in alice.get('/api/si/accounts').json()['items'] if a['name'].startswith('Harbourside')]) == 1
    item = next(x for x in alice.get('/api/si/best').json()['items'] if x['organisation'].startswith('Harbourside'))
    assert item['kind'] == 'customer_expansion' and item['relationship']['status'] == 'customer'
    assert 'Existing customer with a new signal' in item['reasons'] and item['tier'] in ('act_now', 'this_week')
    play = alice.get(f'/api/si/accounts/{account}/play').json()
    assert play['play'] == 'expansion' and play['label'] == 'Estate expansion'


def test_an_account_without_evidence_is_never_assumed_to_be_a_new_site_or_a_tender(hosted):
    h = hosted
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    made = alice.post('/api/si/accounts', json={'name': 'Example Hand Added Ltd'}).json()
    play = alice.get(f"/api/si/accounts/{made['account_id']}/play").json()
    assert play['play'] == 'develop' and 'establish directly' in play['hypothesis'] and 'new site' not in play['label'].lower()
    steps = {s['key']: s['state'] for s in play['steps']}
    assert steps['evidence'] == 'todo' and steps['qualify'] == 'todo' and play['done'] == 0


def test_one_person_fills_one_seat_on_the_buying_committee(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, _ = workspace(h, 'alice', 'Alpha Fire Ltd')
    _, account = investigated(h, alice)
    roles = {r['key']: r for r in alice.get(f'/api/si/accounts/{account}/play').json()['committee']['roles']}
    seated = [k for k, r in roles.items() if any(p['name'] == 'Morgan Reid' for p in r['people'])]
    assert seated == ['estates']  # a Director of Estates and Facilities is not also counted as procurement or facilities
    assert roles['procurement']['status'] == 'gap' and roles['procurement']['gap'] == {'gap': 'find_role', 'subject': 'Procurement or category manager'}
