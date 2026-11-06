"""Evaluation integrity: the blind review has to be independently defensible before anyone relies on what it says.

Written to fail against PR #9 as first opened (1b37e42). Then the sealed key sat in a public repository. Results used the
first reviewer's answer and called one review "complete". Unblinding was a confirmation dialog. Served items carried
SalesIntel's own reasoning and service list, and "missed" leads were counted against a sample instead of the list."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.intelligence import opportunity_review as review
from app.routers import review as review_router
from tenancy_support import hosted  # noqa: F401
from test_opportunity_quality import prospect, signal
from test_shadow_radar import workspace

FOLDER = Path(__file__).parents[1] / 'reference_data' / 'evaluation'
REPO = Path(__file__).parents[2]
S = 'test-set-v2'
FULL = {'relevance': 'yes', 'identity': 'yes', 'requirement': 'hypothesised', 'advertised': 'not_advertised', 'reason': 'yes',
        'stakeholders': 'role', 'route': 'unsure', 'evidence': 'adequate', 'pursue': 'this_month'}


def answers(**changes):
    return {**FULL, **changes}


def dec(item, reviewer, name, **changes):
    return {'item_id': item, 'reviewer': reviewer, 'reviewer_name': name, 'answers': answers(**changes), 'minutes': 2}


def synthetic(n=4):
    """A small frozen set: the served items, the private key (with its salt) and the public commitment."""
    items = [{'id': f'E-{i:02d}', 'organisation': f'Example Org {i}', 'site': None, 'location': None, 'title': f'Fire alarm servicing {i}',
              'record_type': 'Tender notice', 'facts': [{'text': f'Tender notice {i}', 'date': '2026-10-01', 'url': f'https://example.org/{i}', 'basis': 'Published record'}]}
             for i in range(1, n + 1)]
    review_set = {'set_key': S, 'as_of': '2026-11-05', 'rubric': review.RUBRIC, 'items': items, 'instructions': 'Judge each item on its evidence.'}
    sampled = {'E-01': ['keyword', 'qualified'], 'E-02': ['pr8'], 'E-03': ['renewal'], 'E-04': ['exploratory']}
    pools = {'E-01': ['keyword', 'pr8', 'qualified'], 'E-02': ['pr8', 'qualified'], 'E-03': ['renewal'], 'E-04': ['exploratory']}
    key = {'set_key': S, 'salt': '5a' * 32, 'seed': 1, 'pools': {a: 10 for a in review.ARMS}, 'frames': {a: 10 for a in review.ARMS},
           'items': {i: {'lead_key': f'mo:{n}', 'sampled_by': sampled[i], 'in_pools': pools[i],
                         'objective': {'evidence_age_days': 10, 'type': 'public', 'kind': 'published_procurement', 'advertised': True, 'sources': 1, 'routes_on_record': 1}}
                     for n, i in enumerate(sampled, 1)}}
    return review_set, key, review.commit(review_set, key)


# ------------------------------------------------------------------ the key is private, the commitment is public

def test_no_evaluation_key_is_kept_in_the_repository_and_every_served_set_is_committed():
    assert not list(FOLDER.glob('*key*.json'))  # the method-to-lead mapping never lives in a public repository
    sets = [p for p in FOLDER.glob('*.json') if not p.name.endswith('.commitment.json')]
    assert sets, 'a frozen review set is served'
    for path in sets:
        commitment = json.loads(path.with_name(path.stem + '.commitment.json').read_text())
        assert review.digest(json.loads(path.read_text())) == commitment['dataset_sha256']  # what reviewers judge is what was committed
        assert len(commitment['key_sha256']) == 64 and 'salt' not in commitment and 'items' not in commitment and 'seed' not in commitment
    assert '*.key.json' in (REPO / '.gitignore').read_text()


def test_the_commitment_binds_the_private_key_without_revealing_it():
    review_set, key, commitment = synthetic()
    review.verify_key(commitment, key)
    forged = json.loads(json.dumps(key))
    forged['items']['E-02']['sampled_by'] = ['qualified']
    with pytest.raises(ValueError):
        review.verify_key(commitment, forged)
    assert review.commit(review_set, {**key, 'salt': '6b' * 32})['key_sha256'] != commitment['key_sha256']  # salted: not guessable from the hash
    with pytest.raises(ValueError):
        review.commit(review_set, {k: v for k, v in key.items() if k != 'salt'})
    assert commitment['dataset_sha256'] == review.digest(review_set)


# ------------------------------------------------------------------ two independent reviews, explicit adjudication

def test_an_item_needs_two_complete_independent_reviews():
    review_set, key, _ = synthetic()
    ids = [i['id'] for i in review_set['items']]
    one = [dec(i, 1, 'Ann') for i in ids]
    state = review.status(review_set, one, [])
    assert not state['complete'] and state['items_with_two_reviews'] == 0
    with pytest.raises(ValueError):
        review.results(review_set, key, one, [])  # never a result from a single reviewer
    partial = one + [{**dec(i, 2, 'Ben'), 'answers': {'relevance': 'yes'}} for i in ids]  # an unfinished review does not count
    assert not review.status(review_set, partial, [])['complete']
    assert not review.status(review_set, one + one, [])['complete']  # the same reviewer twice is still one reviewer
    state = review.status(review_set, one + [dec(i, 2, 'Ben') for i in ids], [])
    assert state['complete'] and state['items_with_two_reviews'] == len(ids) and state['pending'] == []


def test_every_disagreement_needs_a_recorded_adjudication():
    review_set, key, _ = synthetic()
    ids = [i['id'] for i in review_set['items']]
    decisions = [dec(i, 1, 'Ann') for i in ids] + [dec(i, 2, 'Ben', **({'relevance': 'no', 'pursue': 'no'} if i == 'E-01' else {})) for i in ids]
    state = review.status(review_set, decisions, [])
    assert not state['complete'] and {(p['item_id'], p['question']) for p in state['pending']} == {('E-01', 'relevance'), ('E-01', 'pursue')}
    ruling = {'item_id': 'E-01', 'question': 'relevance', 'answer': 'no', 'method': 'third_reviewer', 'adjudicator': 'Cat', 'rationale': 'The notice is for cleaning only.'}
    with pytest.raises(ValueError):  # an independent third reviewer is not one of the two who disagreed
        review.check_adjudication(state, {**ruling, 'adjudicator': 'ann'})
    with pytest.raises(ValueError):  # the reason is recorded, not implied
        review.check_adjudication(state, {**ruling, 'rationale': ''})
    with pytest.raises(ValueError):  # only a real disagreement is adjudicated
        review.check_adjudication(state, {**ruling, 'item_id': 'E-02'})
    with pytest.raises(ValueError):  # the final answer is one of the rubric's own answers
        review.check_adjudication(state, {**ruling, 'answer': 'maybe'})
    rulings = [ruling, {'item_id': 'E-01', 'question': 'pursue', 'answer': 'no', 'method': 'consensus', 'adjudicator': 'Ann and Ben', 'rationale': 'Agreed: nothing to sell.'}]
    for r in rulings:
        review.check_adjudication(state, r)
    assert review.status(review_set, decisions, rulings)['complete']
    final = review.final_labels(review_set, decisions, rulings)
    assert final['E-01']['relevance'] == 'no' and final['E-02']['relevance'] == 'yes'


def test_reported_rates_come_from_final_labels_whatever_order_reviews_arrive_in():
    review_set, key, _ = synthetic()
    ids = [i['id'] for i in review_set['items']]
    decisions = [dec(i, 1, 'Ann') for i in ids] + [dec(i, 2, 'Ben', **({'relevance': 'no', 'pursue': 'no'} if i == 'E-01' else {})) for i in ids]
    rulings = [{'item_id': 'E-01', 'question': q, 'answer': 'no', 'method': 'consensus', 'adjudicator': 'Ann and Ben', 'rationale': 'Agreed after discussion.'}
               for q in ('relevance', 'pursue')]
    first = review.results(review_set, key, decisions, rulings)
    assert first['arms'] == review.results(review_set, key, list(reversed(decisions)), rulings)['arms']  # no reviewer is "first"
    assert first['arms']['qualified']['relevant']['hits'] == 0  # E-01 was adjudicated not relevant: Ann's "yes" is not used
    assert first['agreement']['relevance']['items'] == len(ids)
    (row,) = first['disagreements']
    assert row['item_id'] == 'E-01' and {q['question']: q['final'] for q in row['questions']} == {'relevance': 'no', 'pursue': 'no'}
    assert all(q['method'] == 'consensus' and q['rationale'] for q in row['questions'])


# ------------------------------------------------------------------ shared leads and uncertainty

def test_shared_leads_count_in_each_arm_that_sampled_them_and_missed_means_not_on_the_list():
    review_set, key, _ = synthetic()
    res = review.results(review_set, key, [dec(i['id'], r, n) for i in review_set['items'] for r, n in ((1, 'Ann'), (2, 'Ben'))], [])
    arms = res['arms']
    assert arms['qualified']['n'] == 1 and arms['keyword']['n'] == 1  # E-01 was sampled by both: judged once, counted in each
    assert arms['pr8']['n'] == 1  # E-02 is on the qualified list but was sampled only for PR #8: it is not a qualified sample
    assert res['overlap']['keyword|qualified'] == 1
    assert set(res['missed_by_qualified']) == {'E-03', 'E-04'}  # E-02 is on the qualified list, so it was not missed
    assert set(res['missed_by_salesintel']) == {'E-03'}  # E-04 was found by the exploratory pathway
    for arm in arms.values():
        assert {'hits', 'n', 'rate', 'interval'} <= set(arm['relevant']) and arm['pool'] == 10 and arm['frame'] == 10


def test_a_difference_is_claimed_only_when_its_adjusted_interval_excludes_zero():
    low, high = review.newcombe(9, 10, 1, 10)
    assert 0.35 < low < 0.39 and 0.9 < high < 0.93
    low, high = review.newcombe(6, 10, 4, 10)
    assert low < 0 < high
    review_set, key, _ = synthetic()
    res = review.results(review_set, key, [dec(i['id'], r, n) for i in review_set['items'] for r, n in ((1, 'Ann'), (2, 'Ben'))], [])
    assert res['comparisons']
    for c in res['comparisons']:
        assert {'arms', 'measure', 'difference', 'interval', 'adjusted_interval', 'supported', 'overlap'} <= set(c)
        assert c['supported'] is False  # one item per arm supports nothing
    assert all('no statistically supported difference' in v.lower() for v in res['verdicts'])


# ------------------------------------------------------------------ what reviewers see

def lead(**kw):
    base = {'key': 'mo:1', 'type': 'public', 'organisation': 'Example Borough Council', 'title': 'CCTV Maintenance, Repair and Upgrade Contract',
            'why_now': 'Published contract with Example Vision Ltd ends 15 December 2026; the buyer is likely to plan its replacement before then.',
            'kind': 'contract_ending', 'category': 'pre_tender', 'services': ['cctv'], 'nation': 'England', 'region': None, 'value': None, 'shadow': None,
            'brief': {'known': [
                {'text': 'Contracts Finder notice radar:42a3793c-14ba', 'source_url': 'https://www.contractsfinder.service.gov.uk/Notice/42a3793c', 'date': '2026-03-01', 'basis': 'published'},
                {'text': 'Contracts Finder notice 42a3793c-14ba', 'source_url': 'https://www.contractsfinder.service.gov.uk/Notice/42a3793c', 'date': '2026-03-01', 'basis': 'published'},
                {'text': "Supplier named on the published record: Example Vision Ltd (reported, not necessarily today's incumbent)", 'source_url': None, 'date': '', 'basis': 'published'},
                {'text': 'published award contract period: 2026-12-15', 'source_url': None, 'date': '', 'basis': 'published'}]}}
    return {**base, **kw}


TENDER = lead(key='mo:2', kind='published_procurement', category='live_procurement', title='Invitation to tender for maintenance of CCTV and door entry',
              why_now='Tender open now, deadline 11 November 2026.',
              brief={'known': [{'text': 'Find a Tender notice radar:096863-2026', 'source_url': 'https://www.find-tender.service.gov.uk/Notice/096863-2026', 'date': '2026-10-20', 'basis': 'published'},
                               {'text': 'published deadline: 2026-11-11', 'source_url': None, 'date': '', 'basis': 'published'}]})
PRIVATE = lead(key='pr:7', type='private', organisation='Example Logistics Ltd', kind='private_signal', category='private_engage_now', nation=None,
               title='Example Logistics has four automated depots still to open, and new sites need fire and security', region='Leeds, West Yorkshire',
               why_now='New site opening: fire and security for a new site is usually procured three to twelve months before it opens. Window open until April 2027.',
               services=['fire_alarm', 'cctv', 'access_control', 'general'],
               brief={'known': [{'text': '£330m programme for seven new automated depots', 'source_url': 'https://news.example/depots', 'date': '2026-09-12', 'basis': 'stated'},
                                {'text': 'Likely supplier consolidation after integration', 'source_url': None, 'date': '', 'basis': 'inferred'},
                                {'text': 'Darlington depot opens', 'source_url': 'https://news.example/later', 'date': '2026-12-01', 'basis': 'stated'}]})
SHADOW = lead(key='sh:3', type='shadow', organisation='Example Council', kind='shadow_signal', category='supplier_transition', nation=None,
              title='Supplier transition: A disrupted contract creates a short window in which a buyer looks for a new supplier',
              why_now='Example Council published "Fire Risk Assessments" 322 days before the published end of "Fire Risk Assessment Lot 8". A disrupted contract creates a short window.',
              services=['fire_alarm', 'cctv', 'access_control'],
              shadow={'site': None, 'sensor': 'supplier_transition', 'state': 'surfaced', 'timeline': [{'role': 'anchor', 'type': 'out_of_cycle_relet'}]},
              brief={'known': [{'text': 'Replacement before the published end: Example Council published "Fire Risk Assessments" 322 days before the published end of "Fire Risk Assessment Lot 8"',
                                'source_url': 'https://www.contractsfinder.service.gov.uk/Notice/abc', 'date': '2026-08-02', 'basis': 'derived'},
                               {'text': 'Fire or security work advertised: Fire Risk Assessments', 'source_url': 'https://www.contractsfinder.service.gov.uk/Notice/def', 'date': '2026-08-02', 'basis': 'published'}]})
BANNED = ('radar', 'shadow', 'salesintel', 'keyword', 'renewal', 'window open', 'likely', 'usually', 'commonly', 'research says', 'engage now',
          'supplier transition', 'indirect', 'company research', 'hypothes', 'inferred', 'not necessarily')


def test_served_items_show_the_evidence_and_nothing_about_how_they_were_found():
    shown = [review.present(x, date(2026, 11, 5)) for x in (lead(), TENDER, PRIVATE, SHADOW)]
    for (item, _), x in zip(shown, (lead(), TENDER, PRIVATE, SHADOW)):
        assert set(item) == {'organisation', 'site', 'location', 'title', 'record_type', 'facts'}  # no summary, no service list, no source method
        assert item['record_type'] in review.RECORD_TYPES and item['facts']
        text = json.dumps(item).lower()
        for word in BANNED:
            assert word not in text, (x['key'], word)
        assert all(f['basis'] in review.FACT_BASIS.values() for f in item['facts'])
    notices = [f for f in shown[0][0]['facts'] if 'notice' in f['text'].lower()]
    assert len(notices) == 1  # one record, listed once, with no collector's internal name
    private, dropped = shown[2]
    assert private['title'] == '£330m programme for seven new automated depots'  # the source's claim, not a sales headline
    assert all('consolidation' not in f['text'] for f in private['facts'])  # an inference is not evidence
    assert dropped == 1  # the December story is later than the as-of date
    assert shown[3][0]['record_type'] == 'Public procurement record'  # indirect evidence is described by the records it rests on


def test_each_arm_is_a_simple_random_sample_of_its_own_list_without_exposed_leads():
    pools = {'qualified': [f'mo:{i}' for i in range(30)], 'exploratory': [f'pr:{i}' for i in range(5)], 'pr8': [f'mo:{i}' for i in range(60)],
             'renewal': [f'mo:{i}' for i in range(40, 80)], 'keyword': [f'mo:{i}' for i in range(0, 400, 3)]}
    exposed = {f'mo:{i}' for i in range(25)}
    picked = review.sample_arms(pools, per_arm=10, seed=7, exclude=exposed)
    for arm, keys in picked.items():
        frame = [k for k in pools[arm] if k not in exposed]
        assert len(keys) == min(10, len(frame)) and set(keys) <= set(frame) and len(set(keys)) == len(keys)
    assert len(picked['qualified']) == 5  # only five of the thirty were never published
    assert picked == review.sample_arms(pools, per_arm=10, seed=7, exclude=exposed)  # reproducible from the private seed
    assert picked != review.sample_arms(pools, per_arm=10, seed=8, exclude=exposed)


def test_a_review_set_built_from_data_is_blinded_committed_and_reproducible(hosted):
    from app.services.shadow_fixtures import load
    h = hosted
    with h.system() as db:
        load(db, real=False)
        db.commit()
    _, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    prospect(h, org, 'Example Distribution Ltd', [signal('new_site', 'New distribution centre in Doncaster opening in 2027')], services=())
    with h.as_workspace(org) as db:
        first, key = review.build(db, date(2026, 11, 5), seed=11, salt='7c' * 32, exclude=set())
        again, key2 = review.build(db, date(2026, 11, 5), seed=11, salt='7c' * 32, exclude=set())
    assert first == again and key == key2  # reproducible from the private seed and salt
    review.verify_key(review.commit(first, key), key)
    assert first['items'] and {a for k in key['items'].values() for a in k['sampled_by']} <= set(review.ARMS)
    assert all(set(k['sampled_by']) <= set(k['in_pools']) for k in key['items'].values())
    assert not {'seed', 'salt'} & set(first)
    assert all(set(i) == {'id', 'organisation', 'site', 'location', 'title', 'record_type', 'facts'} for i in first['items'])
    served = json.dumps(first)
    for secret in ('sampled_by', 'in_pools', '"mo:', '"pr:', '"sh:', key['salt']):
        assert secret not in served


# ------------------------------------------------------------------ the server keeps the seal

@pytest.fixture
def frozen(tmp_path, monkeypatch):
    review_set, key, commitment = synthetic()
    (tmp_path / f'{S}.json').write_text(json.dumps(review_set))
    (tmp_path / f'{S}.commitment.json').write_text(json.dumps(commitment))
    monkeypatch.setattr(review_router, 'DIR', tmp_path)
    return review_set, key, commitment


def colleague(h, alice, org, sub='ben'):
    token = alice.post('/api/workspace/invitations', json={'email': f'{sub}@alpha.example', 'role': 'salesperson'}).json()['token']
    c = h.client(sub, f'{sub}@alpha.example', sub.title())
    c.post('/api/invitations/accept', json={'token': token})
    return h.client(sub, f'{sub}@alpha.example', sub.title(), workspace=org)


def test_results_stay_sealed_until_the_review_is_complete_locked_and_the_key_verifies(hosted, frozen):
    h = hosted
    review_set, key, _ = frozen
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    ben = colleague(h, alice, org)
    assert alice.get(f'/api/si/review/{S}/results').status_code == 409  # not even an administrator can unblind early
    assert ben.get(f'/api/si/review/{S}/results').status_code == 403
    assert alice.post(f'/api/si/review/{S}/lock').status_code == 409
    assert alice.post(f'/api/si/review/{S}/reveal', json=key).status_code == 409
    for item in review_set['items']:
        assert alice.put(f'/api/si/review/{S}/{item["id"]}', json={'answers': FULL}).status_code == 200
        mine = answers(relevance='no', pursue='no') if item['id'] == 'E-01' else FULL
        assert ben.put(f'/api/si/review/{S}/{item["id"]}', json={'answers': mine}).status_code == 200
    status = alice.get(f'/api/si/review/{S}/status').json()
    assert status['state'] == 'open' and not status['ready_to_lock']
    assert {(p['item_id'], p['question']) for p in status['pending']} == {('E-01', 'relevance'), ('E-01', 'pursue')}
    assert 'sampled_by' not in json.dumps(status) and 'qualified' not in json.dumps(status)  # progress never unblinds
    assert ben.get(f'/api/si/review/{S}/status').status_code == 403
    ruling = {'item_id': 'E-01', 'question': 'relevance', 'answer': 'no', 'method': 'third_reviewer', 'adjudicator': 'Alice', 'rationale': 'Cleaning only, no fire or security scope.'}
    assert alice.post(f'/api/si/review/{S}/adjudications', json=ruling).status_code == 422  # Alice reviewed it, so she is not an independent third reviewer
    for q in ('relevance', 'pursue'):
        r = alice.post(f'/api/si/review/{S}/adjudications', json={**ruling, 'question': q, 'method': 'consensus', 'adjudicator': 'Alice and Ben'})
        assert r.status_code == 200, r.text
    assert alice.get(f'/api/si/review/{S}/status').json()['ready_to_lock']
    assert alice.post(f'/api/si/review/{S}/lock').status_code == 200
    assert ben.put(f'/api/si/review/{S}/E-02', json={'answers': FULL}).status_code == 409  # closed: no answer changes once locked
    forged = json.loads(json.dumps(key))
    forged['items']['E-03']['sampled_by'] = ['qualified']
    assert alice.post(f'/api/si/review/{S}/reveal', json=forged).status_code == 409  # a key that does not match the commitment is refused
    assert alice.get(f'/api/si/review/{S}/results').status_code == 409
    assert alice.post(f'/api/si/review/{S}/reveal', json=key).status_code == 200
    res = alice.get(f'/api/si/review/{S}/results').json()
    assert res['arms']['qualified']['n'] == 1 and res['disagreements'][0]['item_id'] == 'E-01'
    assert res['diagnosis']['registered'] == review.DIAGNOSIS['registered']  # the pre-registered diagnosis comes with the results
    bob, _ = workspace(h, 'bob', 'Beta Security Ltd')
    assert bob.get(f'/api/si/review/{S}/results').status_code == 409 and bob.get(f'/api/si/review/{S}/status').json()['reviews'] == 0


def test_an_offline_review_pack_carries_no_key_and_its_answers_are_verified_on_import(hosted, frozen):
    from app.intelligence import review_pack
    h = hosted
    review_set, key, commitment = frozen
    html = review_pack.render(review_set, commitment, reviewer='Reviewer A')
    assert "default-src 'none'" in html and commitment['dataset_sha256'] in html  # the pack makes no network requests
    for secret in ('sampled_by', 'in_pools', 'lead_key', key['salt'], 'qualified', 'exploratory'):
        assert secret not in html
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')

    def submission(name, **changes):
        return {'format': 'salesintel-review/1', 'kind': 'review', 'set_key': S, 'dataset_sha256': commitment['dataset_sha256'],
                'reviewer': {'label': 'Reviewer A', 'name': name}, 'attested': True, 'started_at': '2026-11-06T09:00:00Z', 'finished_at': '2026-11-06T10:10:00Z',
                'decisions': [{'item_id': i['id'], 'answers': FULL, 'seconds': 120, 'note': ''} for i in review_set['items']], **changes}
    assert alice.post(f'/api/si/review/{S}/import', json=submission('Dana', dataset_sha256='0' * 64)).status_code == 422  # answers to another dataset
    assert alice.post(f'/api/si/review/{S}/import', json=submission('Dana', attested=False)).status_code == 422
    wrong = submission('Dana')
    wrong['decisions'][0]['answers'] = {**FULL, 'relevance': 'maybe'}
    assert alice.post(f'/api/si/review/{S}/import', json=wrong).status_code == 422
    stray = submission('Dana')
    stray['decisions'][0]['item_id'] = 'E-99'
    assert alice.post(f'/api/si/review/{S}/import', json=stray).status_code == 422
    assert alice.post(f'/api/si/review/{S}/import', json=submission('Dana')).status_code == 200
    assert alice.post(f'/api/si/review/{S}/import', json=submission('Dana')).status_code == 200  # the same file again changes nothing
    status = alice.get(f'/api/si/review/{S}/status').json()
    assert status['reviewers'] == 1 and status['items_with_two_reviews'] == 0
    assert alice.post(f'/api/si/review/{S}/import', json=submission('Evan')).status_code == 200
    assert alice.get(f'/api/si/review/{S}/status').json()['ready_to_lock']  # two independent reviewers who agree on every item
    ben = colleague(h, alice, org)
    assert ben.post(f'/api/si/review/{S}/import', json=submission('Ben')).status_code == 403
