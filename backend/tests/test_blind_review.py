"""The blind review: reviewers never see which arm produced an item, decisions are kept per reviewer, results unblind only
for administrators, and agreement is measured rather than assumed."""
from __future__ import annotations

import json
from pathlib import Path

from app.intelligence import opportunity_review as review
from tenancy_support import hosted  # noqa: F401
from test_shadow_radar import workspace

SET = 'opportunities-2026-11-05'


def test_reviewers_see_neutral_evidence_only_and_decisions_are_their_own(hosted):
    h = hosted
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    data = alice.get(f'/api/si/review/{SET}').json()
    # Nothing tells a reviewer where an item came from: only these fields are served, for the set and for each item.
    assert set(data) == {'set_key', 'as_of', 'rubric', 'items', 'instructions', 'mine', 'progress'}
    assert all(set(i) <= {'id', 'organisation', 'site', 'title', 'source_kind', 'summary', 'evidence', 'services_mentioned'} for i in data['items'])
    first = data['items'][0]['id']
    assert alice.put(f'/api/si/review/{SET}/{first}', json={'answers': {'relevance': 'maybe'}}).status_code == 422
    assert alice.put(f'/api/si/review/{SET}/{first}', json={'answers': {'relevance': 'yes', 'pursue': 'this_week'}, 'minutes': 3}).status_code == 200
    assert alice.put(f'/api/si/review/{SET}/R-999', json={'answers': {'relevance': 'yes'}}).status_code == 404
    token = alice.post('/api/workspace/invitations', json={'email': 'rev@alpha.example', 'role': 'salesperson'}).json()['token']
    rev = h.client('rev', 'rev@alpha.example', 'Rev')
    rev.post('/api/invitations/accept', json={'token': token})
    rev = h.client('rev', 'rev@alpha.example', 'Rev', workspace=org)
    assert rev.get(f'/api/si/review/{SET}').json()['mine'] == {}  # another reviewer starts blank: no anchoring on a colleague
    rev.put(f'/api/si/review/{SET}/{first}', json={'answers': {'relevance': 'no', 'pursue': 'no'}})
    assert rev.get(f'/api/si/review/{SET}/results').status_code == 403  # results unblind the arms
    res = alice.get(f'/api/si/review/{SET}/results').json()
    assert res['judged'] == 1 and res['reviewers'] == 2 and res['agreement']['items_with_two_reviews'] == 1
    assert res['disagreements'][0]['item_id'] == first and not res['complete']
    bob, _ = workspace(h, 'bob', 'Beta Security Ltd')
    assert bob.get(f'/api/si/review/{SET}').json()['mine'] == {} and bob.get(f'/api/si/review/{SET}/results').json()['judged'] == 0


def test_agreement_and_intervals_are_computed_not_assumed():
    assert review.kappa([('yes', 'yes'), ('no', 'no'), ('yes', 'no'), ('possibly', 'possibly')]) == 0.636
    assert review.kappa([('yes', 'yes')]) is None
    low, high = review.wilson(3, 10)
    assert 0.1 < low < 0.3 and 0.55 < high < 0.65


def test_the_frozen_set_follows_its_protocol():
    folder = Path(__file__).parents[1] / 'reference_data' / 'evaluation'
    data, key = json.loads((folder / f'{SET}.json').read_text()), json.loads((folder / f'{SET}.key.json').read_text())
    assert key['seed'] == review.SEED and 'seed' not in data and key['as_of'] == '2026-11-05' and len(data['items']) == len(key['items'])
    assert all(e['date'] <= key['as_of'] for i in data['items'] for e in i['evidence'] if e['date'])  # no later evidence
    assert '@' not in json.dumps(data)  # no personal contact details in the dataset
    assert {a for k in key['items'].values() for a in k['arms']} == {'salesintel', 'salesintel_pr8', 'renewal', 'keyword'}
