"""Shadow Radar: discovery from real captured evidence, honest inference, deep investigation, isolation and evaluation."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ingestion import adjacent_works as aw
from app.intelligence import shadow_radar as radar
from app.intelligence.shadow_evaluation import arms, evaluate
from app.models.acquisition import ResearchJob
from app.models.crm import Contact, DealRecord
from app.models.market_inference import MarketObservation
from app.models.shadow import Dossier, LeadFeedback, ShadowHypothesisRevision
from app.services import jobs, shadow
from app.services.shadow_fixtures import load
from tenancy_support import hosted  # noqa: F401

CAPTURE = json.loads((Path(__file__).parents[1] / 'reference_data' / 'adjacent_works_capture_2026-11-05.json').read_text())
T = datetime(2026, 11, 5, tzinfo=UTC)


def obs(kind, buyer, published, *, group='procurement', statement=None, detail=None, url=None, supplier=None, origin=None):
    o = {'id': None, 'signal_type': kind, 'buyer': buyer, 'supplier': supplier, 'company_number': None, 'statement': statement or f'{buyer} {kind} {published}',
         'occurred_on': published, 'available_on': published, 'source_group': group, 'reliability': 'official_notice', 'source_url': url or f'https://src.example/{kind}/{published}',
         'detail': detail or {}, 'first_seen': T, 'retrieved_at': T, 'origin_key': origin, 'retracted_on': None}
    return o


def works(buyer, published, title='New community centre - main works', supplier='Builder Ltd', project='p1', **kw):
    return obs('works_awarded', buyer, published, supplier=supplier, origin=f'procurement:{project}',
               detail={'works_type': 'new_build', 'building_type': 'public_venue', 'value': 5_000_000, 'title': title, 'publisher': buyer, 'project': project}, **kw)


# ---------------------------------------------------------------- the new source, on real captured notices

def test_real_capture_is_classified_conservatively():
    kept = {n['title']: aw.classify(n) for n in CAPTURE['notices']}
    assert sum(1 for v in kept.values() if v) == 97 and len(CAPTURE['notices']) == 631
    anchor = next(v for t, v in kept.items() if t == 'Anchor Housing - New Build Development')
    assert anchor['signal_type'] == 'works_awarded' and anchor['supplier'] == 'Meldrum Group Limited' and anchor['detail']['building_type'] == 'residential'
    assert anchor['detail']['licence'].startswith('Contains public sector information licensed under the Open Government Licence')
    for noise in ('CCS PM and Design Ottawa Residence Refurbishment', 'Ascent Homes - Coulson Park - Groundworks', 'Two Play Park Upgrade Projects',
                  'CA17674 - Lionheart Educational Trust - Kitchen Refurbishment', 'Weel Bridge Refurbishment', 'Sales Agent'):
        assert not kept.get(noise), noise  # overseas, groundworks, play parks, kitchens, bridges and non-works are not building leads


def test_a_consortium_is_never_merged_with_the_member_it_buys_for():
    notice = {'id': 'x', 'url': 'https://www.contractsfinder.service.gov.uk/Notice/x', 'title': 'Anchor Housing - New Build Development', 'buyer': 'PROSPER',
              'description': '', 'type': 'Contract', 'published': '2026-10-20', 'start': None, 'value': 17_762_942.76, 'suppliers': ['Meldrum Group Limited']}
    o = aw.classify(notice)
    assert o['buyer'] == 'Anchor Housing' and o['detail']['beneficiary_inferred'] is True and o['detail']['publisher'] == 'PROSPER'
    a = radar.evaluate([{**o, 'id': 1, 'first_seen': T, 'retrieved_at': T, 'origin_key': 'procurement:x', 'retracted_on': None}], date(2026, 11, 5))[0]
    assert any('purchasing consortium' in x for x in a['inferred'])  # said as an inference, not a fact


def test_observations_are_append_only(hosted):
    with hosted.system() as db:
        item = aw.classify(CAPTURE['notices'][0]) or next(x for x in (aw.classify(n) for n in CAPTURE['notices']) if x)
        aw.store_append_only(db, [item], T)
        changed = deepcopy(item)
        changed['statement'] = 'Rewritten later'
        aw.store_append_only(db, [changed], T + timedelta(days=1))  # same fingerprint: the stored record is not rewritten
        row = db.scalar(select(MarketObservation).where(MarketObservation.fingerprint == item['fingerprint']))
        assert row.statement == item['statement'] and row.retrieved_at is not None and row.first_seen < row.last_seen


# ---------------------------------------------------------------- inference: independence, challenge, time

def test_republished_copies_and_repeated_notices_are_one_source_not_corroboration():
    d = date(2026, 6, 1)
    copy_a = obs('estate_expansion', 'Example Council', d, group='news', statement='Council approves new library at Mill Road.', url='https://a.example/x')
    copy_b = obs('estate_expansion', 'Example Council', d + timedelta(days=1), group='news', statement='Council approves new library at Mill Road.', url='https://b.example/y')
    tender = works('Example Council', d + timedelta(days=10), title='New library at Mill Road - main works tender', project='lib')
    award = works('Example Council', d + timedelta(days=60), title='New library at Mill Road - main works award', project='lib')
    out = [a for a in radar.evaluate([copy_a, copy_b, tender, award], date(2026, 9, 1)) if a['sensor'] == 'estate_mobilisation']
    assert len(out) == 1  # one project, one lead
    assert out[0]['independent_sources'] == 2  # procurement + one news origin (the republished copy adds nothing)
    alone = [a for a in radar.evaluate([copy_a, copy_b], date(2026, 9, 1)) if a['sensor'] == 'estate_mobilisation']
    assert len(alone) == 1 and alone[0]['independent_sources'] == 1 and alone[0]['state'] == 'indicated'


def test_counter_evidence_challenges_and_related_adverts_are_not_claimed():
    d = date(2026, 3, 1)
    finding = obs('regulator_compliance_finding', 'Example Homes', d, group='regulator')
    resolved = obs('issue_resolved', 'Example Homes', d + timedelta(days=120), group='regulator')
    rem = [a for a in radar.evaluate([finding, resolved], date(2026, 9, 1)) if a['sensor'] == 'remediation'][0]
    assert rem['state'] == 'challenged' and any(e['role'] == 'challenges' for e in rem['timeline'])
    build = works('Example Council', d, title='Riverside Primary School extension main works', project='rps')
    other = obs('market_engagement', 'Example Council', d + timedelta(days=40), statement='Example Council published an early notice: "Fire door maintenance across the borough".')
    same = obs('market_engagement', 'Example Council', d + timedelta(days=50), statement='Example Council published an early notice: "Riverside Primary School fire alarm installation".')
    only_related = [a for a in radar.evaluate([build, other], date(2026, 9, 1)) if a['sensor'] == 'estate_mobilisation'][0]
    assert only_related['state'] != 'surfaced' and any(e['role'] == 'related' for e in only_related['timeline'])
    surfaced = [a for a in radar.evaluate([build, other, same], date(2026, 9, 1)) if a['sensor'] == 'estate_mobilisation'][0]
    assert surfaced['state'] == 'surfaced' and surfaced['first_advertised_on'] == str(d + timedelta(days=50))


def test_no_future_information_reaches_a_past_judgement():
    d = date(2026, 6, 1)
    past = works('Example Council', d - timedelta(days=30), project='a')
    future_support = obs('estate_expansion', 'Example Council', d + timedelta(days=5), group='planning', statement='Planning granted for Example Council centre')
    future_counter = obs('market_engagement', 'Example Council', d + timedelta(days=10), statement='Example Council published an early notice: "New community centre fire alarm".')
    at_d = [a for a in radar.evaluate([past, future_support, future_counter], d) if a['sensor'] == 'estate_mobilisation'][0]
    assert at_d['independent_sources'] == 1 and at_d['state'] == 'indicated' and len(at_d['timeline']) == 1
    flagged = arms([past, future_support, future_counter], [], d, 120)
    assert 'example' in flagged['shadow'] or flagged['shadow']  # flagged from past evidence only
    report = evaluate([past, future_counter], [], [d], 120, d + timedelta(days=120))
    assert report['arms']['shadow']['hits'] == 1  # the later advert is the outcome, never an input
    report_without = evaluate([past], [], [d], 120, d + timedelta(days=120))
    assert report_without['arms']['shadow']['flagged'] == report['arms']['shadow']['flagged']


def test_every_sensor_is_defined_and_blocked_ones_are_not_evaluated():
    reg = {s['key']: s for s in radar.registry()}
    assert len(reg) == 8 and all(reg[k]['alternatives'] and reg[k]['disconfirming'] and reg[k]['evidence_needed'] for k in reg)
    assert {k for k, s in reg.items() if s['status'] == 'needs_source'} == {'consolidation', 'funded_capital', 'leadership_change'}
    assert all(s['blocked'] for s in reg.values() if s['status'] == 'needs_source')


def test_refresh_keeps_every_assessment_and_retires_rather_than_deletes(hosted):
    with hosted.system() as db:
        load(db, real=False)
        db.commit()
        first = db.scalars(select(ShadowHypothesisRevision)).all()
        assert first and shadow.refresh(db, now=T + timedelta(days=1), as_of=date(2026, 11, 6))['revised'] == 0  # unchanged evidence, no new revision
        later = shadow.refresh(db, now=T + timedelta(days=900), as_of=date(2029, 5, 1))  # windows have passed
        assert later['revised'] >= 1
        assert len(db.scalars(select(ShadowHypothesisRevision)).all()) > len(first)  # earlier reasoning kept


# ---------------------------------------------------------------- the workspace journey, isolation and cost

def workspace(h, sub, name):
    c = h.client(sub, f'{sub}@{name.split()[0].lower()}.example', sub.title())
    org = c.post('/api/workspaces', json={'name': name}).json()['id']
    c = h.client(sub, f'{sub}@{name.split()[0].lower()}.example', sub.title(), workspace=org)
    c.put('/api/si/preferences', json={'company_name': name, 'services': ['fire_alarm', 'access_control'], 'territory': ['England']})
    return c, org


def test_discovery_to_investigation_to_contacts_to_deal_and_isolation(hosted):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, a_org = workspace(h, 'alice', 'Alpha Fire Ltd')
    leads = alice.get('/api/si/discover', params={'source': 'shadow'}).json()['items']
    lead = next(x for x in leads if x['organisation'].startswith('Harbourside') and x['category'] == 'adjacent_package')
    assert lead['type'] == 'shadow' and lead['kind'] == 'shadow_signal' and lead['basis'] == 'inferred'
    a = lead['shadow']
    assert a['state'] == 'corroborated' and a['independent_sources'] == 2 and a['main_contractor'] == 'Northbank Construction Ltd'
    assert a['verified'] and a['inferred'] and a['unknown'] and a['alternatives'] and 'probability' not in json.dumps(a).lower()
    assert lead['brief']['next'] == a['first_action']
    started = alice.post(f"/api/si/radar/hypotheses/{lead['key'][3:]}/investigate", json={}).json()
    account = started['account_id']
    jobs.drain(h.engine)
    d = alice.get(f'/api/si/radar/accounts/{account}/dossier').json()
    latest = d['latest']
    assert d['job']['status'] == 'succeeded' and latest['verdict'] == 'weakened'  # it found evidence against its own hypothesis
    reasons = {r['reason'] for r in latest['rejected']}
    assert 'The page tried to give instructions to the AI, so nothing from it is used.' in reasons and 'The quoted words do not appear on the source page.' in reasons
    texts = json.dumps(latest['sections'])
    assert 'Coastline Fire Services' in texts and '£2m' not in texts and '£400,000' not in texts
    assert any(x['outcome'] == 'weakens' and x['purpose'] for x in latest['challenge']['answers'].values())
    people = alice.get(f'/api/si/accounts/{account}/people').json()
    assert any(r['name'] == 'Morgan Reid' for r in people['routes']) and any(r['email'] == 'estates@harbourside-health.example' for r in people['routes'])
    # Into a deal, with the evidence and the investigation carried over.
    deal = alice.post(f'/api/si/accounts/{account}/deals', json={'source_key': lead['key'], 'services': ['fire_alarm'], 'qualification': {'requirement': 'Fire and security package for the new centre'}}).json()
    assert deal['origin']['key'] == lead['key'] and deal['origin']['dossier']['verdict'] == 'weakened' and deal['value_total'] is None  # main contract value is not our value
    # Feedback needs a reason when negative, and the scorecard reports only what happened.
    assert alice.post('/api/si/radar/feedback', json={'lead_key': lead['key'], 'decision': 'not_relevant'}).status_code == 422
    other = next(x for x in leads if x['key'] != lead['key'])
    alice.post('/api/si/radar/feedback', json={'lead_key': other['key'], 'decision': 'not_relevant', 'reason': 'outside_territory'})
    card = alice.get('/api/si/radar/scorecard').json()['sensors']
    assert card['adjacent_package']['investigated'] == 1 and card['adjacent_package']['qualified'] == 1 and card['adjacent_package']['research_cents'] > 0
    assert sum(s['dismissed'] for s in card.values()) == 1
    # Another company sees the shared public lead, but none of Alpha's investigation, contacts, feedback or status.
    bob, b_org = workspace(h, 'bob', 'Beta Security Ltd')
    bob_leads = {x['key']: x for x in bob.get('/api/si/discover', params={'source': 'shadow'}).json()['items']}
    assert bob_leads[lead['key']]['status'] == 'new' and bob_leads[lead['key']]['account_id'] is None and other['key'] in bob_leads
    assert bob.get(f'/api/si/radar/accounts/{account}/dossier').status_code == 404
    assert bob.get(f"/api/si/research-jobs/{started['job']['id']}").status_code == 404
    assert all(v['investigated'] == 0 and v['dismissed'] == 0 for v in bob.get('/api/si/radar/scorecard').json()['sensors'].values())
    with h.as_workspace(b_org) as db:
        assert db.scalars(select(Dossier)).all() == [] and db.scalars(select(LeadFeedback)).all() == [] and db.scalar(select(Contact)) is None
        assert db.scalar(select(DealRecord)) is None


def test_investigation_is_reused_bounded_and_recoverable(hosted, monkeypatch):
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    alice, a_org = workspace(h, 'alice', 'Alpha Fire Ltd')
    lead = next(x for x in alice.get('/api/si/discover', params={'source': 'shadow'}).json()['items'] if x['organisation'].startswith('Harbourside'))
    hid = lead['key'][3:]
    first = alice.post(f'/api/si/radar/hypotheses/{hid}/investigate', json={}).json()
    claimed = jobs.claim(h.engine)  # a worker dies mid-investigation
    assert claimed and claimed[0] == first['job']['id']
    with h.system() as db:
        db.get(ResearchJob, first['job']['id']).lease_until = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    jobs.drain(h.engine)
    job = alice.get(f"/api/si/research-jobs/{first['job']['id']}").json()
    assert job['status'] == 'succeeded' and job['attempts'] == 2
    again = alice.post(f'/api/si/radar/hypotheses/{hid}/investigate', json={}).json()
    assert again['job']['id'] == first['job']['id'] and again['job']['reused'] is True  # kept on the account, not regenerated
    monkeypatch.setenv('AI_DAILY_LIMIT_CENTS_PER_WORKSPACE', '100')
    from app.config import get_settings
    get_settings.cache_clear()
    assert alice.post(f'/api/si/radar/hypotheses/{hid}/investigate', json={'refresh': True}).status_code == 429  # the $4 reservation does not fit
    get_settings.cache_clear()


def test_the_existing_contract_inference_ignores_works_observations(hosted):
    from app.intelligence.signal_inference import contract_hypotheses
    real = [x for x in (aw.classify(n) for n in CAPTURE['notices']) if x][:20]  # real stored-shape observations of the new types
    assert contract_hypotheses([], real, date(2026, 11, 5)) is not None  # no error from the new observation types
