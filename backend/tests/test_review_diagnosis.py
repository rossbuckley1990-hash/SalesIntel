"""How the blind review diagnoses discovery. Registered on 6 November 2026, before any reviewer's answer was imported.

The product's north star treats the 44-item review as a quality gate and a diagnosis, not the measure of commercial
success. Two questions are fixed here before anyone has seen an answer, so the answers cannot shape them:
- Otherwise missed: how many leads were a genuine (or possible) opportunity that had not been advertised. A tender
  search would not find these.
- Where leads drop out: each method's leads, step by step along the acceptance test (the right organisation, a real
  opportunity, a reason to contact now, someone to speak to, a way to reach them, worth pursuing).

Neither adds a comparison or a verdict. The frozen protocol and its public commitment are unchanged."""
from __future__ import annotations

import json
import os

from app.intelligence import opportunity_review as review
from test_evaluation_integrity import FOLDER, REPO, dec, synthetic

STEPS = ['identity', 'opportunity', 'reason', 'person', 'route', 'pursue']
SCREEN = REPO / 'frontend' / 'tests' / 'fixtures' / 'review-results.json'
RULING = {'item_id': 'E-01', 'method': 'consensus', 'adjudicator': 'Ann and Ben', 'rationale': 'Agreed: the notice includes the fire alarms.'}
OVERRULED = [{**RULING, 'question': 'relevance', 'answer': 'yes'}, {**RULING, 'question': 'pursue', 'answer': 'this_month'}]


def judged(ann=None, ben=None, rulings=()):
    """Two reviewers judge the synthetic set (E-01 qualified and keyword, E-02 PR #8, E-03 renewal, E-04 exploratory)."""
    review_set, key, _ = synthetic()
    ids = [i['id'] for i in review_set['items']]
    decisions = [dec(i, 1, 'Ann', **(ann or {}).get(i, {})) for i in ids] + [dec(i, 2, 'Ben', **(ben or {}).get(i, {})) for i in ids]
    return review.results(review_set, key, decisions, list(rulings))


def rates(chain):
    return [s['rate'] for s in chain['steps']]


def test_the_diagnosis_is_registered_in_the_results_and_adds_no_comparison_or_verdict():
    plain = judged()
    d = plain['diagnosis']
    assert d['registered'] == '2026-11-06' == review.DIAGNOSIS['registered']
    assert [s['key'] for s in d['steps']] == STEPS  # the acceptance test, in its own order
    assert set(d['otherwise_missed']) == set(d['chain']) == set(review.ARMS)
    assert 'fresh' in d['rule'] and 'pilot' in d['rule']  # what it suggests is tested elsewhere before anything is claimed
    assert 'supported' not in json.dumps(d) and 'difference' not in json.dumps(d)  # it never claims a difference between methods
    pre_specified = {(a, b, m) for a, b, m in review.PRIMARY_COMPARISONS + review.SECONDARY_COMPARISONS}
    assert {(*c['arms'], c['measure']) for c in plain['comparisons']} == pre_specified
    assert len(plain['verdicts']) == len(pre_specified)


def test_otherwise_missed_is_a_genuine_opportunity_that_had_not_been_advertised():
    res = judged(ann={'E-02': {'advertised': 'advertised'}, 'E-03': {'advertised': 'unclear'}, 'E-04': {'relevance': 'possibly'}},
                 ben={'E-03': {'advertised': 'unclear'}, 'E-04': {'relevance': 'possibly'}})
    missed = res['diagnosis']['otherwise_missed']
    assert missed['qualified']['relevant']['rate'] == 1.0 and missed['keyword']['relevant']['rate'] == 1.0  # E-01: shared, counted in both
    assert missed['pr8']['relevant']['rate'] == 0.5  # one reviewer of two judged E-02 already advertised: every reviewer counts equally
    assert missed['renewal']['relevant_or_possible']['rate'] == 0.0  # "Unclear" is not evidence that it was unadvertised
    assert missed['exploratory']['relevant']['rate'] == 0.0 and missed['exploratory']['relevant_or_possible']['rate'] == 1.0
    for arm in missed.values():
        for m in arm.values():
            assert {'n', 'rate', 'interval', 'label'} <= set(m) and m['n'] == 1 and len(m['interval']) == 2


def test_relevance_comes_from_the_final_label_so_one_reviewer_cannot_hide_a_missed_opportunity():
    res = judged(ben={'E-01': {'relevance': 'no', 'pursue': 'no'}}, rulings=OVERRULED)
    assert res['diagnosis']['otherwise_missed']['qualified']['relevant']['rate'] == 1.0  # Ben's "no" was overruled


def stepwise():
    return judged(ann={'E-01': {'route': 'yes'}, 'E-02': {'identity': 'no'}, 'E-04': {'stakeholders': 'none'}},
                  ben={'E-01': {'relevance': 'no', 'pursue': 'no'}, 'E-04': {'stakeholders': 'none'}}, rulings=OVERRULED)


def test_where_leads_drop_out_follows_the_acceptance_test_step_by_step():
    chain = stepwise()['diagnosis']['chain']
    # E-01: relevance and pursue use the final labels; the route is each reviewer's own answer (Ann: yes, Ben: unsure).
    assert rates(chain['qualified']) == [1.0, 1.0, 1.0, 1.0, 0.5, 0.5]
    assert [s['drop'] for s in chain['qualified']['steps']] == [0.0, 0.0, 0.0, 0.0, 0.5, 0.0]
    # E-02: Ann says it is the wrong organisation, so her chain stops at once; Ben's stops at the route ("Unsure").
    assert rates(chain['pr8']) == [0.5, 0.5, 0.5, 0.5, 0.0, 0.0]
    # E-04: nobody to speak to, so the lead stops there however good the rest is.
    assert rates(chain['exploratory']) == [1.0, 1.0, 1.0, 0.0, 0.0, 0.0]
    for arm in chain.values():
        values = rates(arm)
        assert values == sorted(values, reverse=True)  # a lead passes a step only if it passed every earlier one
        assert arm['n'] == 1 and [s['key'] for s in arm['steps']] == STEPS


def test_the_results_screen_is_tested_against_what_the_server_returns():
    """`frontend/tests/si-review-results.test.ts` renders this fixture. Regenerate it with UPDATE_FIXTURES=1 when the results change."""
    current = json.loads(json.dumps(stepwise()))
    if os.environ.get('UPDATE_FIXTURES'):
        SCREEN.parent.mkdir(parents=True, exist_ok=True)
        SCREEN.write_text(json.dumps(current, indent=1, ensure_ascii=False) + '\n')
    assert json.loads(SCREEN.read_text()) == current


def test_adding_the_diagnosis_left_the_frozen_protocol_and_its_commitment_unchanged():
    for path in FOLDER.glob('*.commitment.json'):
        commitment = json.loads(path.read_text())
        assert commitment['protocol'] == json.loads(json.dumps(review.PROTOCOL))  # what was committed is still what is run
        assert 'diagnosis' not in json.dumps(commitment).lower()
        assert commitment['created_at'][:10] <= review.DIAGNOSIS['registered']  # registered after the set was frozen
