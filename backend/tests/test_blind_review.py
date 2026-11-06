"""The blind review from a reviewer's side.

- Only the source records are served.
- Each reviewer's answers are their own, and an unfinished judgement does not count.
- Another workspace sees nothing.
- The committed set follows its published protocol.

The integrity rules (sealed key, two reviews, adjudication, locked unblinding) are in test_evaluation_integrity.py."""
from __future__ import annotations

import json
from pathlib import Path

from app.intelligence import opportunity_review as review
from tenancy_support import hosted  # noqa: F401
from test_evaluation_integrity import FULL, S, colleague, frozen  # noqa: F401  (frozen is a fixture)
from test_shadow_radar import workspace

FOLDER = Path(__file__).parents[1] / 'reference_data' / 'evaluation'
SERVED = {'id', 'organisation', 'site', 'location', 'title', 'record_type', 'facts'}


def test_reviewers_see_the_records_only_and_their_answers_are_their_own(hosted, frozen):
    h = hosted
    alice, org = workspace(h, 'alice', 'Alpha Fire Ltd')
    data = alice.get(f'/api/si/review/{S}').json()
    assert set(data) == {'set_key', 'as_of', 'rubric', 'items', 'instructions', 'mine', 'progress', 'state', 'fingerprint'}
    assert all(set(i) == SERVED for i in data['items'])  # nothing about how an item was found
    first = data['items'][0]['id']
    assert alice.put(f'/api/si/review/{S}/{first}', json={'answers': {'relevance': 'maybe'}}).status_code == 422
    assert alice.put(f'/api/si/review/{S}/{first}', json={'answers': {'colour': 'red'}}).status_code == 422
    assert alice.put(f'/api/si/review/{S}/{first}', json={'answers': {'relevance': 'yes', 'pursue': 'this_week'}, 'minutes': 3}).status_code == 200
    assert alice.get(f'/api/si/review/{S}').json()['progress']['done'] == 0  # saved, but an unfinished judgement is not counted
    assert alice.put(f'/api/si/review/{S}/E-99', json={'answers': FULL}).status_code == 404
    ben = colleague(h, alice, org)
    assert ben.get(f'/api/si/review/{S}').json()['mine'] == {}  # another reviewer starts blank: no anchoring on a colleague
    assert ben.put(f'/api/si/review/{S}/{first}', json={'answers': FULL}).status_code == 200
    assert ben.get(f'/api/si/review/{S}').json()['progress']['done'] == 1
    bob, _ = workspace(h, 'bob', 'Beta Security Ltd')
    assert bob.get(f'/api/si/review/{S}').json()['mine'] == {} and bob.get(f'/api/si/review/{S}/status').json()['reviews'] == 0


def test_agreement_and_intervals_are_computed_not_assumed():
    assert review.kappa([('yes', 'yes'), ('no', 'no'), ('yes', 'no'), ('possibly', 'possibly')]) == 0.636
    assert review.kappa([('yes', 'yes')]) is None
    low, high = review.wilson(3, 10)
    assert 0.1 < low < 0.3 and 0.55 < high < 0.65


def test_the_committed_set_follows_its_published_protocol():
    sets = [p for p in FOLDER.glob('*.json') if not p.name.endswith('.commitment.json')]
    assert [p.stem for p in sets] == ['opportunities-2026-11-05-v2']  # v1 was withdrawn unjudged once its key was found to be public
    data = json.loads(sets[0].read_text())
    commitment = json.loads(sets[0].with_name(sets[0].stem + '.commitment.json').read_text())
    assert commitment['protocol']['version'] == review.VERSION and commitment['protocol']['withdrawn'][0]['set_key'] == 'opportunities-2026-11-05'
    assert commitment['items_served'] == len(data['items']) and not {'seed', 'salt'} & set(data) and data['rubric'] == review.RUBRIC
    assert all(set(i) == SERVED and i['facts'] for i in data['items'])
    assert all(f['date'] <= data['as_of'] for i in data['items'] for f in i['facts'] if f['date'])  # no later evidence
    assert '@' not in json.dumps(data)  # no personal contact details
    text = json.dumps(data).lower()
    for word in ('radar:', 'shadow radar', 'salesintel', 'window open', 'research says', 'not necessarily today'):
        assert word not in text, word
    # Nothing published names a reviewed organisation with the method that found it: the showcase skips them all.
    showcase = (Path(__file__).parents[2] / 'docs' / 'saas' / 'evaluation' / 'SHOWCASE.md').read_text()
    featured = {line[4:].strip().lower() for line in showcase.splitlines() if line.startswith('### ')}
    assert featured and not featured & {i['organisation'].lower() for i in data['items']}
