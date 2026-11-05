"""A reproducible, blinded evaluation of discovered opportunities: SalesIntel's daily list against a renewal-date
baseline and a keyword baseline, across public procurement, private-company research and Shadow Radar.

Protocol (fixed in code before anything was sampled):
- One as-of date. Only evidence published on or before it is used; any later evidence is dropped and counted.
- One reference profile (a generic UK fire and security installer), the same for every arm, so no arm is tuned to a reviewer.
- Arms:
  salesintel      the focused daily list (act now and this week), up to PER_SOURCE items per source, sampled with SEED
  salesintel_pr8  the same list as PR #8 built it (no positive service match required), sampled the same way
  renewal     published contract ends within the same 120 days, sampled with SEED
  keyword     any lead whose title names a fire or security system, sampled with SEED
- The review set is the union, shuffled with SEED, with opaque ids. Reviewers see only neutral evidence: no arm, rank,
  tier, reasons, fit or next action. The sealed key (which arms produced each item, and objective measures) is not
  served to reviewers.
- Judgements come only from human reviewers. Objective measures (evidence age, sources, advertised or not, identity
  basis, routes on record) are computed, never judged by the model that produced the leads.
- No named individuals are included: people and contact routes are counted, not listed.
"""
from __future__ import annotations

import math
import random
import re
from collections import Counter
from contextlib import contextmanager
from datetime import date

SEED = 20261105
PER_SOURCE = 6
PER_BASELINE = 12
RENEWAL_DAYS = 120
REFERENCE_PROFILE = {'company_name': 'Reference UK fire and security installer', 'sender_name': '',
                     'services': ['fire_alarm', 'access_control', 'cctv', 'intruder', 'emergency_lighting'],
                     'territory': ['England', 'Scotland', 'Wales'], 'sectors': [], 'capabilities': [], 'deal_size_min': None, 'deal_size_max': None}
KEYWORDS = re.compile(r'\b(fire alarms?|fire detection|fire safety|fire risk|sprinklers?|cctv|access control|intruder|security systems?|'
                      r'emergency lighting|door entry|fire doors?)\b', re.I)
SOURCE_KIND = {'public': 'Public procurement record', 'private': 'Company research (news and company pages)', 'shadow': 'Building works record (indirect)'}

RUBRIC = [
    {'key': 'relevance', 'question': 'Is there a genuine fire or security commercial opportunity here for a firm like yours?',
     'options': [['yes', 'Yes'], ['possibly', 'Possibly'], ['no', 'No']]},
    {'key': 'identity', 'question': 'Is the organisation (and site, if named) correctly identified from the evidence?',
     'options': [['yes', 'Yes'], ['unsure', 'Unsure'], ['no', 'No']]},
    {'key': 'requirement', 'question': 'Is a customer requirement confirmed, or only hypothesised?',
     'options': [['confirmed', 'Confirmed'], ['hypothesised', 'Hypothesised'], ['none', 'No requirement']]},
    {'key': 'advertised', 'question': 'Has it already been advertised (an open tender or published notice)?',
     'options': [['advertised', 'Advertised'], ['not_advertised', 'Not advertised'], ['unclear', 'Unclear']]},
    {'key': 'reason', 'question': 'Is there a legitimate reason to contact them now?', 'options': [['yes', 'Yes'], ['no', 'No']]},
    {'key': 'stakeholders', 'question': 'Can you tell who to speak to?', 'options': [['named', 'A named person'], ['role', 'A role only'], ['none', 'No']]},
    {'key': 'route', 'question': 'Is a reliable business contact route available?', 'options': [['yes', 'Yes'], ['unsure', 'Unsure'], ['no', 'No']]},
    {'key': 'evidence', 'question': 'How strong and current is the evidence?', 'options': [['strong', 'Strong'], ['adequate', 'Adequate'], ['weak', 'Weak']]},
    {'key': 'pursue', 'question': 'Would you pursue it?',
     'options': [['this_week', 'Yes, this week'], ['this_month', 'Yes, this month'], ['later', 'Later'], ['no', 'No']]},
]
VALID = {q['key']: {o[0] for o in q['options']} for q in RUBRIC}


# PR #8's title-to-service mapping, kept so its arm reproduces PR #8 exactly (it counted extinguishers and passive fire as
# fire alarms and missed plural family names, so adjacent work was "services not stated" and not set aside).
PR8_FAMILY_SERVICE = {"fire_alarm": "fire_alarm", "cctv": "cctv", "access": "access_control", "access_control": "access_control", "intruder": "intruder",
                      "emergency_lighting": "emergency_lighting", "sprinkler": "sprinkler", "suppression": "sprinkler", "extinguisher": "fire_alarm",
                      "passive_fire": "fire_alarm", "door_entry": "access_control"}


@contextmanager
def pr8_rules():
    from app.services import si_core
    current = si_core.FAMILY_SERVICE
    si_core.FAMILY_SERVICE = PR8_FAMILY_SERVICE
    try:
        yield
    finally:
        si_core.FAMILY_SERVICE = current


@contextmanager
def reference_profile():
    """Every arm is computed against the same reference profile, never a workspace's own settings."""
    from app.services import best, si_core
    original = si_core.preferences
    si_core.preferences = lambda db: dict(REFERENCE_PROFILE)
    best.core.preferences = si_core.preferences
    try:
        yield
    finally:
        si_core.preferences = original
        best.core.preferences = original


def _evidence(x: dict, as_of: date) -> tuple[list[dict], int]:
    rows, dropped = [], 0
    for k in x['brief']['known']:
        day = (k.get('date') or '')[:10]
        if day and day > as_of.isoformat():
            dropped += 1  # never let later evidence into a judgement made as of this date
            continue
        rows.append({'text': k['text'][:300], 'date': day, 'url': k.get('source_url') or '', 'basis': k.get('basis') or ''})
    return rows, dropped


def _objective(x: dict, evidence: list[dict], as_of: date) -> dict:
    days = [date.fromisoformat(e['date']) for e in evidence if re.fullmatch(r'\d{4}-\d{2}-\d{2}', e['date'] or '')]
    shadow = x.get('shadow') or {}
    identity = ('official buyer name' if x['type'] == 'public' else 'inferred beneficiary' if any('purchasing consortium' in i for i in shadow.get('inferred', []))
                else 'organisation named in its own evidence' if x['type'] == 'shadow' else 'named in company research')
    routes = (x.get('contact_routes') or 0) if x['type'] == 'private' else 1 if x['type'] == 'public' else 0  # a public notice always gives an official route
    return {'evidence_age_days': (as_of - max(days)).days if days else None, 'sources': len({e['url'] for e in evidence if e['url']}),
            'advertised': x['kind'] == 'published_procurement', 'identity_basis': identity, 'routes_on_record': routes,
            'people_named_in_research': x.get('people') or 0, 'kind': x['kind'], 'type': x['type']}


def build(db, as_of: date, *, seed: int = SEED) -> tuple[dict, dict]:
    """Return (review_set, sealed_key) for the data visible in this session."""
    from app.services import best, si_core
    with reference_profile():
        items = [x for x in si_core.discover_items(db, limit=None) if x['status'] != 'dismissed']
        focus = best.opportunities(db, limit=200)
        with pr8_rules():
            focus_pr8 = best.opportunities(db, limit=200, strict_service=False)
    by_key = {x['key']: x for x in items}
    rng = random.Random(seed)
    pools: dict[str, list[str]] = {}
    chosen: dict[str, set[str]] = {}

    salesintel = [x['key'] for x in focus['items'] if x['tier'] != 'watch' and x['key'] in by_key]
    pools['salesintel'] = salesintel
    picked = []
    for kind in ('public', 'private', 'shadow'):
        mine = [k for k in salesintel if by_key[k]['type'] == kind]
        picked += rng.sample(mine, min(PER_SOURCE, len(mine)))
    chosen['salesintel'] = set(picked)

    pr8 = [x['key'] for x in focus_pr8['items'] if x['tier'] != 'watch' and x['key'] in by_key]
    pools['salesintel_pr8'] = pr8
    picked = []
    for kind in ('public', 'private', 'shadow'):
        mine = [k for k in pr8 if by_key[k]['type'] == kind]
        picked += rng.sample(mine, min(PER_SOURCE, len(mine)))
    chosen['salesintel_pr8'] = set(picked)

    renewal = [x['key'] for x in items if x['kind'] == 'contract_ending' and x.get('days') is not None and 0 <= x['days'] <= RENEWAL_DAYS]
    pools['renewal'] = renewal
    chosen['renewal'] = set(rng.sample(renewal, min(PER_BASELINE, len(renewal))))

    keyword = [x['key'] for x in items if KEYWORDS.search(f"{x['title']} {x.get('why_now') or ''}")]
    pools['keyword'] = keyword
    chosen['keyword'] = set(rng.sample(keyword, min(PER_BASELINE, len(keyword))))

    # Objective measures over each arm's whole pool (facts from the records, not judgements).
    sells = set(REFERENCE_PROFILE['services'])
    def pool_facts(keys: list[str]) -> dict:
        xs = [by_key[k] for k in keys]
        ages = sorted(a for a in (_objective(x, _evidence(x, as_of)[0], as_of)['evidence_age_days'] for x in xs) if a is not None)
        return {'size': len(xs), 'names_a_service_you_sell': round(sum(1 for x in xs if set(x['services']) & sells) / len(xs), 3) if xs else None,
                'adjacent_or_unidentified_service': round(sum(1 for x in xs if not set(x['services']) & sells) / len(xs), 3) if xs else None,
                'advertised': round(sum(1 for x in xs if x['kind'] == 'published_procurement') / len(xs), 3) if xs else None,
                'median_evidence_age_days': ages[len(ages) // 2] if ages else None, 'by_source': dict(Counter(x['type'] for x in xs))}
    pool_metrics = {a: pool_facts(v) for a, v in pools.items()}

    union = sorted(set().union(*chosen.values()))
    rng.shuffle(union)
    review_items, key_items, dropped_total = [], {}, 0
    for n, lead in enumerate(union, 1):
        x = by_key[lead]
        evidence, dropped = _evidence(x, as_of)
        dropped_total += dropped
        item_id = f'R-{n:03d}'
        review_items.append({'id': item_id, 'organisation': x['organisation'], 'site': (x.get('shadow') or {}).get('site') or None,
                             'title': x['title'][:240], 'source_kind': SOURCE_KIND[x['type']], 'summary': (x.get('why_now') or '')[:400],
                             'evidence': evidence, 'services_mentioned': x['services']})
        rank = next((i + 1 for i, y in enumerate(focus['items']) if y['key'] == lead), None)
        key_items[item_id] = {'lead_key': lead, 'arms': sorted(a for a, keys in chosen.items() if lead in keys), 'salesintel_rank': rank,
                              'tier': next((y['tier'] for y in focus['items'] if y['key'] == lead), None), 'objective': _objective(x, evidence, as_of)}
    meta = {'set_key': f'opportunities-{as_of.isoformat()}', 'as_of': as_of.isoformat(), 'seed': seed, 'per_source': PER_SOURCE, 'per_baseline': PER_BASELINE,
            'renewal_days': RENEWAL_DAYS, 'reference_profile': {k: v for k, v in REFERENCE_PROFILE.items() if k in ('services', 'territory')}}
    # Reviewers get only what they need: the protocol (arms, windows, sample sizes, seed) stays in the sealed key.
    review_set = {'set_key': meta['set_key'], 'as_of': meta['as_of'], 'rubric': RUBRIC, 'items': review_items,
                  'instructions': ('Judge each item only on the evidence shown, as a fire and security salesperson would. You are not told where it came from. '
                                   'Record your own view; do not discuss items with other reviewers until everyone has finished.')}
    key = {**meta, 'items': key_items, 'pools': {a: len(v) for a, v in pools.items()}, 'pool_by_source': dict(Counter(by_key[k]['type'] for k in salesintel)),
           'future_evidence_dropped': dropped_total, 'candidates': len(items), 'pool_metrics': pool_metrics}
    return review_set, key


def validate(answers: dict) -> dict:
    clean = {}
    for k, options in VALID.items():
        v = answers.get(k)
        if v is not None and v not in options:
            raise ValueError(f'Unknown answer for {k}.')
        if v is not None:
            clean[k] = v
    return clean


def wilson(hits: int, n: int) -> list[float] | None:
    if not n:
        return None
    z, p = 1.96, hits / n
    centre, spread = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(max(0.0, (centre - spread) / (1 + z * z / n)), 3), round(min(1.0, (centre + spread) / (1 + z * z / n)), 3)]


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for two reviewers' categorical answers."""
    if len(pairs) < 2:
        return None
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(left[c] * right[c] for c in set(left) | set(right)) / (n * n)
    return round((observed - expected) / (1 - expected), 3) if expected < 1 else None


def results(review_set: dict, key: dict, decisions: list[dict]) -> dict:
    """Per-arm adjudicated measures from human decisions, plus the objective measures. Nothing is reported as adjudicated
    until a human has judged it."""
    by_item: dict[str, list[dict]] = {}
    for d in decisions:
        by_item.setdefault(d['item_id'], []).append(d)
    arms = {}
    for arm in ('salesintel', 'salesintel_pr8', 'renewal', 'keyword'):
        ids = [i for i, k in key['items'].items() if arm in k['arms']]
        judged = [i for i in ids if by_item.get(i)]
        first = {i: by_item[i][0]['answers'] for i in judged}  # the first decision per item for rates; agreement is reported separately
        count = lambda q, vals: sum(1 for a in first.values() if a.get(q) in vals)  # noqa: E731
        n = len(judged)
        relevant, actionable = count('relevance', {'yes'}), count('pursue', {'this_week', 'this_month'})
        obj = [key['items'][i]['objective'] for i in ids]
        ages = sorted(o['evidence_age_days'] for o in obj if o['evidence_age_days'] is not None)
        arms[arm] = {
            'items': len(ids), 'judged': n,
            'precision': round(relevant / n, 3) if n else None, 'precision_interval': wilson(relevant, n),
            'precision_lenient': round(count('relevance', {'yes', 'possibly'}) / n, 3) if n else None,
            'actionable_yield': round(actionable / n, 3) if n else None, 'actionable_interval': wilson(actionable, n),
            'reason_to_contact': round(count('reason', {'yes'}) / n, 3) if n else None,
            'identity_correct': round(count('identity', {'yes'}) / n, 3) if n else None,
            'requirement_confirmed': round(count('requirement', {'confirmed'}) / n, 3) if n else None,
            'judged_advertised': round(count('advertised', {'advertised'}) / n, 3) if n else None,
            'stakeholders_identifiable': round(count('stakeholders', {'named', 'role'}) / n, 3) if n else None,
            'route_available': round(count('route', {'yes'}) / n, 3) if n else None,
            'minutes_per_item': round(sum((by_item[i][0].get('minutes') or 0) for i in judged) / n, 1) if n else None,
            'objective': {'median_evidence_age_days': ages[len(ages) // 2] if ages else None, 'advertised_share': round(sum(o['advertised'] for o in obj) / len(obj), 3) if obj else None,
                          'with_route_on_record': round(sum(1 for o in obj if o['routes_on_record']) / len(obj), 3) if obj else None,
                          'mean_sources': round(sum(o['sources'] for o in obj) / len(obj), 2) if obj else None,
                          'by_source': dict(Counter(o['type'] for o in obj))},
        }
    pairs = [(v[0]['answers'].get('relevance'), v[1]['answers'].get('relevance')) for v in by_item.values() if len(v) >= 2]
    disagreements = [{'item_id': i, 'answers': [{'reviewer': d['reviewer'], 'relevance': d['answers'].get('relevance'), 'pursue': d['answers'].get('pursue')} for d in v]}
                     for i, v in by_item.items() if len(v) >= 2 and len({d['answers'].get('relevance') for d in v}) > 1]
    relevant_ids = {i for i, v in by_item.items() if v[0]['answers'].get('relevance') == 'yes'}
    missed = sorted(i for i in relevant_ids if 'salesintel' not in key['items'][i]['arms'])
    reviewers = sorted({d['reviewer'] for d in decisions})
    complete = all(by_item.get(i['id']) for i in review_set['items'])
    return {'set_key': review_set['set_key'], 'items': len(review_set['items']), 'judged': len(by_item), 'reviewers': len(reviewers), 'complete': complete,
            'arms': arms, 'agreement': {'items_with_two_reviews': len(pairs), 'relevance_kappa': kappa(pairs),
                                        'percent_agreement': round(sum(1 for a, b in pairs if a == b) / len(pairs), 3) if pairs else None},
            'disagreements': disagreements, 'missed_by_salesintel': missed, 'pools': key['pools'], 'future_evidence_dropped': key['future_evidence_dropped'],
            'note': ('Adjudicated measures count only items a human reviewer judged; with few judgements the intervals are wide. '
                     'Do not claim an improvement unless the intervals separate.')}
