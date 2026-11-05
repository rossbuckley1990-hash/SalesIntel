"""A reproducible, blinded evaluation of discovered opportunities, built to be independently defensible.

Protocol v2, fixed in code and committed publicly before any judgement. Version 1 (5 November 2026) was withdrawn unjudged
because its key had been published in a public repository.

Arms. Each is a simple random sample of PER_ARM leads from its own list, as of one date, for one reference profile:
  qualified    SalesIntel's daily list: an evidenced requirement for a service the profile sells (act now, this week)
  exploratory  SalesIntel's exploratory list: a sourced organisation, site or commercial change, need not confirmed
  pr8          the daily list as PR #8 built it (no service or evidence rule, no separate exploratory list)
  renewal      published contract ends within RENEWAL_DAYS
  keyword      leads whose own source text names a fire or security system
Excluded from every sampling frame, so nothing published reveals how any reviewed item was found:
- leads in the withdrawn v1 set, whose key is public;
- leads that v1's published documents or screenshots show with the method that found them.

Blinding.
- Reviewers see each item as its source records describe it: organisation, site, location, the record's own title, the
  kind of record, and dated facts with links.
- They never see an arm, rank, tier, SalesIntel's reasons, summary, service list or inferences.
- Items are ordered and numbered using a secret salt.
- The key is written outside the repository. It holds which arms sampled each item, which lists contain it, the seed,
  the salt and the objective measures.
- Only the key's salted SHA-256 commitment and the dataset's SHA-256 are published. So the key can be checked when it
  is revealed, and cannot be guessed before.

Judgement.
- Every item needs complete reviews from at least two independent reviewers.
- Disagreements on the primary questions (relevance, reason to contact, pursue) are adjudicated explicitly, with a
  written rationale. That is done by consensus of the reviewers, or by an independent third reviewer.
- Agreement (Cohen's kappa) is measured on the reviewers' own answers, before adjudication.
- Results unblind only once the review is complete and locked, and the revealed key matches the commitment.

Analysis (pre-specified).
- Per arm: n, pool and frame sizes, and Wilson 95% intervals for four measures:
  - relevant: relevance is yes;
  - actionable: pursue this week or this month;
  - worth investigating: there is a reason to contact, and pursue is not no;
  - noise: relevance is no, or pursue is no.
- Primary comparisons:
  - qualified against renewal and against keyword, on relevant and actionable;
  - Newcombe intervals for each difference, Bonferroni-adjusted over the four.
- Shared leads:
  - a lead counts in each arm that sampled it, so arms are not independent;
  - shared items make the intervals conservative;
  - a difference is claimed only if its adjusted interval excludes zero.
- Secondary:
  - qualified against PR #8, to see whether this PR helped;
  - exploratory against keyword;
  - leads judged relevant that neither SalesIntel list contains.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import Counter
from contextlib import contextmanager
from datetime import date
from itertools import combinations
from statistics import NormalDist

VERSION = 2
PER_ARM = 10
RENEWAL_DAYS = 120
ARMS = ('qualified', 'exploratory', 'pr8', 'renewal', 'keyword')
ARM_LABEL = {'qualified': 'SalesIntel qualified', 'exploratory': 'SalesIntel exploratory', 'pr8': 'SalesIntel (PR #8 rules)',
             'renewal': 'Renewal dates', 'keyword': 'Keywords'}
REFERENCE_PROFILE = {'company_name': 'Reference UK fire and security installer', 'sender_name': '',
                     'services': ['fire_alarm', 'access_control', 'cctv', 'intruder', 'emergency_lighting'],
                     'territory': ['England', 'Scotland', 'Wales'], 'sectors': [], 'capabilities': [], 'deal_size_min': None, 'deal_size_max': None}
KEYWORDS = re.compile(r'\b(fire alarms?|fire detection|fire safety|fire risk|sprinklers?|cctv|access control|intruder|security systems?|'
                      r'emergency lighting|door entry|fire doors?)\b', re.I)

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
PRIMARY = ('relevance', 'reason', 'pursue')
METHODS = {'consensus': 'Consensus of the reviewers after discussing it', 'third_reviewer': 'An independent third reviewer'}
INSTRUCTIONS = ('Judge each item only on the evidence shown, as a fire and security salesperson would. You are not told how it was found. '
                'Work alone: do not discuss items with anyone, or look for how they were found, until the review is closed.')

MEASURES = {
    'relevant': ('Genuine fire or security opportunity', lambda a: a['relevance'] == 'yes'),
    'relevant_or_possible': ('Genuine or possible opportunity', lambda a: a['relevance'] in ('yes', 'possibly')),
    'actionable': ('Worth pursuing this week or month', lambda a: a['pursue'] in ('this_week', 'this_month')),
    'worth_investigating': ('A reason to contact, worth pursuing at some point', lambda a: a['reason'] == 'yes' and a['pursue'] != 'no'),
    'noise': ('Not relevant, or not worth pursuing', lambda a: a['relevance'] == 'no' or a['pursue'] == 'no'),
}
# Secondary rates: every reviewer's answer counts equally (the mean over each item's reviewers), never one reviewer's.
SECONDARY = {'identity_correct': ('identity', {'yes'}), 'requirement_confirmed': ('requirement', {'confirmed'}),
             'judged_advertised': ('advertised', {'advertised'}), 'stakeholders_identifiable': ('stakeholders', {'named', 'role'}),
             'route_available': ('route', {'yes'}), 'evidence_strong': ('evidence', {'strong'})}
PRIMARY_COMPARISONS = [('qualified', 'renewal', 'relevant'), ('qualified', 'renewal', 'actionable'),
                       ('qualified', 'keyword', 'relevant'), ('qualified', 'keyword', 'actionable')]
SECONDARY_COMPARISONS = [('qualified', 'pr8', 'relevant'), ('qualified', 'pr8', 'noise'),
                         ('exploratory', 'keyword', 'worth_investigating'), ('exploratory', 'keyword', 'noise')]
Z = 1.96
Z_ADJ = round(NormalDist().inv_cdf(1 - 0.05 / (2 * len(PRIMARY_COMPARISONS))), 4)  # Bonferroni within each family of four
EXPLORATORY_RULE = 0.3  # pre-specified product rule: keep the pathway if at least 30% of its sampled leads are worth investigating

# What reviewers see: the record as its source describes it.
FACT_BASIS = {'published': 'Published record', 'stated': 'Stated in the source', 'derived': 'Calculated from published records'}
PUBLIC_RECORD = {'live_procurement': 'Tender notice', 'official_early_signal': 'Early market notice', 'pre_tender': 'Contract award record',
                 'verify_first': 'Contract award record', 'contract_defence': 'Contract award record'}
SHADOW_RECORD = {'works_awarded': 'Building works record', 'works_planned': 'Building works record', 'estate_expansion': 'Public body publication',
                 'regulator_compliance_finding': 'Regulator or fire authority record', 'fire_enforcement_outcome': 'Regulator or fire authority record',
                 'false_alarm_rise': 'Fire service statistics'}  # everything else indirect rests on procurement records
RECORD_TYPES = {*PUBLIC_RECORD.values(), *SHADOW_RECORD.values(), 'Public procurement record', 'Company announcement or news'}
_INTERNAL = re.compile(r'\bradar:', re.I)
_CAVEAT = re.compile(r"\s*\(reported, not necessarily today.s incumbent\)", re.I)
_RECORD_ID = re.compile(r'(Contracts Finder notice) [0-9a-f-]{20,}', re.I)  # a long internal id means nothing to a reader; the link stays
# A notice's dates in plain words, and honest about which were calculated rather than published.
TIMING = {'published award contract period': ('Contract period ends', 'published'), 'published contract end date': ('Contract end date', 'published'),
          'published deadline': ('Tender deadline', 'published'), 'published expected date': ('Expected tender date', 'published'),
          'term stated in the notice wording added to the start date': ('Contract end, from the start date plus the term stated in the notice', 'derived'),
          'published duration added to the start date': ('Contract end, from the start date plus the published duration', 'derived')}
_TIMING = re.compile(r'^(' + '|'.join(re.escape(k) for k in TIMING) + r'): (\d{4}-\d{2}-\d{2})', re.I)

PROTOCOL = {
    'version': VERSION,
    'arms': {'qualified': "SalesIntel's daily list (act now and this week): an evidenced requirement for a service the profile sells, or an existing relationship",
             'exploratory': "SalesIntel's exploratory list: a sourced organisation, site or commercial change; need not confirmed",
             'pr8': 'The daily list as PR #8 built it', 'renewal': f'Published contract ends within {RENEWAL_DAYS} days',
             'keyword': "Leads whose own source text names a fire or security system"},
    'reference_profile': {k: REFERENCE_PROFILE[k] for k in ('services', 'territory')},
    'sampling': f'A simple random sample of up to {PER_ARM} leads per arm from its own list, with a seed fixed in the sealed key. '
                'A lead sampled by two arms is judged once and counts in both. Excluded from every frame: leads in the withdrawn v1 set, and leads '
                "that v1's published documents or screenshots show with the method that found them.",
    'blinding': 'Reviewers see only the source records: no arm, rank, tier, reasons, summary, service list or inferences. Order and ids use a secret salt.',
    'completion': 'At least two independent complete reviews per item; every disagreement on relevance, reason or pursue adjudicated with a recorded '
                  'method (consensus or an independent third reviewer) and rationale; then the set is locked before the key is revealed.',
    'measures': {k: v[0] for k, v in MEASURES.items()},
    'primary_comparisons': [f'{a} vs {b}: {m}' for a, b, m in PRIMARY_COMPARISONS],
    'secondary_comparisons': [f'{a} vs {b}: {m}' for a, b, m in SECONDARY_COMPARISONS],
    'statistics': f'Wilson 95% intervals per arm; Newcombe intervals for differences at z = {Z_ADJ} (Bonferroni over each family of four). '
                  'Shared leads make arms positively correlated, so these intervals are conservative. A difference is claimed only if the adjusted '
                  'interval excludes zero.',
    'exploratory_rule': f'The exploratory pathway is supported as useful if at least {EXPLORATORY_RULE:.0%} of its sampled leads are judged worth investigating.',
    'withdrawn': [{'set_key': 'opportunities-2026-11-05', 'reason': 'Its key was published in a public repository before any judgement; it was never reviewed.'}],
}


# ------------------------------------------------------------------ profile and rules

PR8_FAMILY_SERVICE = {"fire_alarm": "fire_alarm", "cctv": "cctv", "access": "access_control", "access_control": "access_control", "intruder": "intruder",
                      "emergency_lighting": "emergency_lighting", "sprinkler": "sprinkler", "suppression": "sprinkler", "extinguisher": "fire_alarm",
                      "passive_fire": "fire_alarm", "door_entry": "access_control"}


@contextmanager
def pr8_rules():
    """PR #8's title-to-service mapping, so its arm reproduces PR #8 exactly."""
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


# ------------------------------------------------------------------ commitment

def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def digest(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def commit(review_set: dict, key: dict) -> dict:
    """The public commitment: the dataset's hash and the salted key's hash, plus the pre-specified protocol."""
    if not re.fullmatch(r'[0-9a-f]{64}', str(key.get('salt') or '')):
        raise ValueError('The key needs a 256-bit random salt, so its hash cannot be guessed.')
    if key.get('set_key') != review_set['set_key']:
        raise ValueError('The key belongs to another review set.')
    return {'set_key': review_set['set_key'], 'as_of': review_set['as_of'], 'items_served': len(review_set['items']),
            'dataset_sha256': digest(review_set), 'key_sha256': digest(key),
            'hash': 'SHA-256 of canonical JSON: keys sorted, no whitespace, UTF-8', 'protocol': PROTOCOL}


def verify_key(commitment: dict, key: dict) -> None:
    if key.get('set_key') != commitment.get('set_key') or digest(key) != commitment.get('key_sha256'):
        raise ValueError('This key does not match the commitment published before the review.')


# ------------------------------------------------------------------ what reviewers see

def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', _RECORD_ID.sub(r'\1', _CAVEAT.sub('', _INTERNAL.sub('', text or '')))).strip()[:300]


def _timing(text: str, basis: str) -> tuple[str, str]:
    m = _TIMING.match(text or '')
    if not m:
        return text, basis
    label, real = TIMING[m.group(1).lower()]
    return f"{label}: {date.fromisoformat(m.group(2)):%-d %B %Y}", real


def present(x: dict, as_of: date) -> tuple[dict, int]:
    """The item as its source records describe it, and how many later-dated facts were dropped."""
    facts, dropped, seen = [], 0, set()
    for k in (x.get('brief') or {}).get('known') or []:
        text, basis = _timing(k.get('text') or '', k.get('basis') or '')
        k = {**k, 'text': text}
        basis, url = basis, k.get('source_url') or ''
        if basis not in FACT_BASIS or (basis == 'stated' and not url):
            continue  # an inference, or a claim with no source, is not evidence
        day = (k.get('date') or '')[:10]
        if day and day > as_of.isoformat():
            dropped += 1  # never let later evidence into a judgement made as of this date
            continue
        text = _clean(k.get('text') or '')
        if not text or (text.lower(), url) in seen:
            continue
        seen.add((text.lower(), url))
        facts.append({'text': text, 'date': day, 'url': url, 'basis': FACT_BASIS[basis]})
    if x['type'] == 'public':
        title, record = _clean(x.get('title') or ''), PUBLIC_RECORD.get(x.get('category') or '', 'Public procurement record')
    else:
        first = next((f for f in facts if f['basis'] != FACT_BASIS['derived']), facts[0] if facts else None)
        title = first['text'] if first else ''
        if x['type'] == 'private':
            record = 'Company announcement or news'
        else:
            anchor = next((e for e in (x.get('shadow') or {}).get('timeline') or [] if e.get('role') == 'anchor'), {})
            record = SHADOW_RECORD.get(anchor.get('type') or '', 'Public procurement record')
    location = ', '.join(dict.fromkeys(p for p in (x.get('region'), x.get('nation')) if p)) or None
    return {'organisation': x['organisation'], 'site': (x.get('shadow') or {}).get('site') or None, 'location': location,
            'title': title[:240], 'record_type': record, 'facts': facts[:6]}, dropped


# ------------------------------------------------------------------ sampling and the frozen set

def sample_arms(pools: dict[str, list[str]], *, per_arm: int, seed: int, exclude: set[str]) -> dict[str, list[str]]:
    """A simple random sample from each arm's own list, in a fixed order, so the draw is reproducible from the seed."""
    rng = random.Random(seed)
    out = {}
    for arm in ARMS:
        frame = sorted(k for k in dict.fromkeys(pools.get(arm) or []) if k not in exclude)
        out[arm] = sorted(rng.sample(frame, min(per_arm, len(frame))))
    return out


def _objective(x: dict, item: dict, as_of: date) -> dict:
    days = [date.fromisoformat(f['date']) for f in item['facts'] if re.fullmatch(r'\d{4}-\d{2}-\d{2}', f['date'] or '')]
    shadow = x.get('shadow') or {}
    identity = ('official buyer name' if x['type'] == 'public' else 'inferred beneficiary' if any('purchasing consortium' in i for i in shadow.get('inferred', []))
                else 'organisation named in its own evidence' if x['type'] == 'shadow' else 'named in company research')
    routes = (x.get('contact_routes') or 0) if x['type'] == 'private' else 1 if x['type'] == 'public' else 0  # a public notice always gives an official route
    return {'evidence_age_days': (as_of - max(days)).days if days else None, 'sources': len({f['url'] for f in item['facts'] if f['url']}),
            'advertised': x['kind'] == 'published_procurement', 'identity_basis': identity, 'routes_on_record': routes,
            'people_named_in_research': x.get('people') or 0, 'kind': x['kind'], 'type': x['type'], 'record_type': item['record_type']}


def build(db, as_of: date, *, seed: int, salt: str, exclude: set[str], per_arm: int = PER_ARM) -> tuple[dict, dict]:
    """Return (review_set, key) for the data visible in this session. Deterministic given the data, seed and salt."""
    from app.services import best, si_core
    with reference_profile():
        items = [x for x in si_core.discover_items(db, limit=None) if x['status'] != 'dismissed']
        daily = best.opportunities(db, limit=1000, explore_limit=1000)
        with pr8_rules():
            legacy = best.opportunities(db, limit=1000, strict_service=False)
    by_key = {x['key']: x for x in items}
    shown = {k: present(x, as_of) for k, x in by_key.items()}
    judgeable = {k for k, (item, _) in shown.items() if item['facts'] and item['title']}
    source_text = {k: ' '.join([item['title'], *(f['text'] for f in item['facts'])]) for k, (item, _) in shown.items()}
    pools = {
        'qualified': [x['key'] for x in daily['items'] if x['tier'] in ('act_now', 'this_week')],
        'exploratory': [x['key'] for x in daily['exploratory']],
        'pr8': [x['key'] for x in legacy['items'] if x['tier'] != 'watch'],
        'renewal': [x['key'] for x in items if x['kind'] == 'contract_ending' and x.get('days') is not None and 0 <= x['days'] <= RENEWAL_DAYS],
        'keyword': [k for k in by_key if KEYWORDS.search(source_text[k])],  # the record's own words, never SalesIntel's
    }
    pools = {a: [k for k in dict.fromkeys(v) if k in by_key] for a, v in pools.items()}
    excluded = set(exclude) | (set(by_key) - judgeable)
    picked = sample_arms(pools, per_arm=per_arm, seed=seed, exclude=excluded)
    union = sorted(set().union(*picked.values()))
    random.Random(f'{salt}:order').shuffle(union)  # the order and the ids reveal nothing without the salt
    review_items, key_items, dropped_total = [], {}, 0
    rank = {x['key']: n for n, x in enumerate(daily['items'], 1)}
    for n, lead in enumerate(union, 1):
        item, dropped = shown[lead]
        dropped_total += dropped
        item_id = f'E-{n:02d}'
        review_items.append({'id': item_id, **item})
        key_items[item_id] = {'lead_key': lead, 'sampled_by': sorted(a for a in ARMS if lead in picked[a]),
                              'in_pools': sorted(a for a in ARMS if lead in pools[a]), 'qualified_rank': rank.get(lead),
                              'objective': _objective(by_key[lead], item, as_of)}
    sells = set(REFERENCE_PROFILE['services'])

    def pool_facts(keys: list[str]) -> dict:
        xs = [by_key[k] for k in keys]
        ages = sorted(a for a in (_objective(by_key[k], shown[k][0], as_of)['evidence_age_days'] for k in keys) if a is not None)
        return {'size': len(xs),
                'record_names_a_service_you_sell': round(sum(1 for x in xs if set(x.get('evidenced_services', x['services'])) & sells) / len(xs), 3) if xs else None,
                'advertised': round(sum(1 for x in xs if x['kind'] == 'published_procurement') / len(xs), 3) if xs else None,
                'median_evidence_age_days': ages[len(ages) // 2] if ages else None, 'by_source': dict(Counter(x['type'] for x in xs))}
    review_set = {'set_key': f'opportunities-{as_of.isoformat()}-v{VERSION}', 'as_of': as_of.isoformat(), 'rubric': RUBRIC, 'items': review_items,
                  'instructions': INSTRUCTIONS}
    key = {'set_key': review_set['set_key'], 'version': VERSION, 'as_of': as_of.isoformat(), 'seed': seed, 'salt': salt, 'per_arm': per_arm,
           'renewal_days': RENEWAL_DAYS, 'reference_profile': PROTOCOL['reference_profile'], 'items': key_items,
           'pools': {a: len(v) for a, v in pools.items()}, 'frames': {a: len([k for k in v if k not in excluded]) for a, v in pools.items()},
           'excluded_published': {a: len([k for k in v if k in set(exclude)]) for a, v in pools.items()},
           'unjudgeable': {a: len([k for k in v if k not in judgeable]) for a, v in pools.items()},
           'future_evidence_dropped': dropped_total, 'candidates': len(items), 'pool_metrics': {a: pool_facts(v) for a, v in pools.items()},
           'blinding_audit': blinding_audit(review_items, key_items)}
    return review_set, key


def blinding_audit(review_items: list[dict], key_items: dict) -> dict:
    """How well each presentational feature alone would let someone guess an item's arm family (SalesIntel or a baseline).
    Kept in the sealed key, because publishing it before the review would itself be a clue."""
    def family(i: str) -> str:
        arms = set(key_items[i]['sampled_by'])
        return 'salesintel' if arms <= {'qualified', 'exploratory', 'pr8'} else 'baseline' if arms <= {'renewal', 'keyword'} else 'both'
    features = {'record_type': lambda it: it['record_type'], 'has_site': lambda it: bool(it['site']), 'has_location': lambda it: bool(it['location']),
                'facts': lambda it: min(len(it['facts']), 4)}
    out = {}
    for name, f in features.items():
        table: dict[str, Counter] = {}
        for it in review_items:
            table.setdefault(str(f(it)), Counter())[family(it['id'])] += 1
        majority = sum(c.most_common(1)[0][1] for c in table.values())
        out[name] = {'by_value': {k: dict(v) for k, v in table.items()}, 'guess_accuracy': round(majority / len(review_items), 3) if review_items else None}
    base = Counter(family(it['id']) for it in review_items)
    out['chance'] = round(base.most_common(1)[0][1] / len(review_items), 3) if review_items else None
    return out


# ------------------------------------------------------------------ completion and adjudication

def complete_answers(answers: dict) -> bool:
    return all((answers or {}).get(q) in VALID[q] for q in VALID)


def validate(answers: dict) -> dict:
    unknown = set(answers) - set(VALID)
    if unknown:
        raise ValueError(f'Unknown question: {sorted(unknown)[0]}.')
    clean = {}
    for k, options in VALID.items():
        v = answers.get(k)
        if v is not None and v not in options:
            raise ValueError(f'Unknown answer for {k}.')
        if v is not None:
            clean[k] = v
    return clean


def _reviews(review_set: dict, decisions: list[dict]) -> dict[str, dict]:
    """Complete reviews per item, one per reviewer. An unfinished review does not count."""
    out: dict[str, dict] = {i['id']: {} for i in review_set['items']}
    for d in decisions:
        if d['item_id'] in out and complete_answers(d.get('answers') or {}):
            out[d['item_id']][d['reviewer']] = d
    return out


def _name(d: dict) -> str:
    return (d.get('reviewer_name') or '').strip() or f"Reviewer {d['reviewer']}"


def status(review_set: dict, decisions: list[dict], adjudications: list[dict]) -> dict:
    """Progress without unblinding anything: complete reviews, disagreements and what still needs adjudicating."""
    reviews = _reviews(review_set, decisions)
    ruled = {(a['item_id'], a['question']) for a in adjudications}
    disagreements, pending = [], []
    for item, revs in reviews.items():
        if len(revs) < 2:
            continue
        for q in PRIMARY:
            given = {_name(d): d['answers'][q] for d in revs.values()}
            if len(set(given.values())) > 1:
                row = {'item_id': item, 'question': q, 'answers': given, 'reviewers': sorted(given)}
                disagreements.append(row)
                if (item, q) not in ruled:
                    pending.append(row)
    two = [i for i, r in reviews.items() if len(r) >= 2]
    names = {_name(d) for r in reviews.values() for d in r.values()}
    return {'items': len(reviews), 'reviews': sum(len(r) for r in reviews.values()), 'reviewers': len(names),
            'items_with_two_reviews': len(two), 'missing': sorted(i for i, r in reviews.items() if len(r) < 2),
            'disagreements': disagreements, 'pending': pending,
            'adjudicated': len([d for d in disagreements if (d['item_id'], d['question']) in ruled]),
            'complete': bool(reviews) and len(two) == len(reviews) and not pending, 'agreement': agreement(reviews)}


def check_adjudication(state: dict, ruling: dict) -> None:
    q, item = ruling.get('question'), ruling.get('item_id')
    target = next((d for d in state['disagreements'] if d['item_id'] == item and d['question'] == q), None)
    if target is None:
        raise ValueError('Only a recorded disagreement between two reviewers is adjudicated.')
    if ruling.get('answer') not in VALID[q]:
        raise ValueError("The final answer must be one of the rubric's own answers.")
    if ruling.get('method') not in METHODS:
        raise ValueError('Say how it was resolved: consensus of the reviewers, or an independent third reviewer.')
    who = (ruling.get('adjudicator') or '').strip()
    if len(who) < 2:
        raise ValueError('Record who resolved it.')
    if len((ruling.get('rationale') or '').strip()) < 10:
        raise ValueError('Record why, in at least a sentence.')
    if ruling['method'] == 'third_reviewer' and who.lower() in {n.lower() for n in target['reviewers']}:
        raise ValueError('An independent third reviewer cannot be one of the reviewers who disagreed.')


def final_labels(review_set: dict, decisions: list[dict], adjudications: list[dict]) -> dict[str, dict]:
    reviews = _reviews(review_set, decisions)
    rulings = {(a['item_id'], a['question']): a for a in adjudications}
    out = {}
    for item, revs in reviews.items():
        if len(revs) < 2:
            raise ValueError(f'{item} needs two complete independent reviews.')
        labels = {}
        for q in PRIMARY:
            given = {d['answers'][q] for d in revs.values()}
            if len(given) == 1:
                labels[q] = given.pop()
            elif (item, q) in rulings:
                labels[q] = rulings[(item, q)]['answer']
            else:
                raise ValueError(f'The disagreement on {item} ({q}) has not been adjudicated.')
        out[item] = labels
    return out


def agreement(reviews: dict[str, dict]) -> dict:
    """Agreement between the two reviewers who judged most items, on their own answers before any adjudication."""
    counts = Counter(r for revs in reviews.values() for r in revs)
    pair = sorted(r for r, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:2])
    out = {}
    for q in PRIMARY:
        pairs = [(revs[pair[0]]['answers'][q], revs[pair[1]]['answers'][q]) for revs in reviews.values() if len(pair) == 2 and all(p in revs for p in pair)]
        out[q] = {'items': len(pairs), 'percent_agreement': round(sum(1 for a, b in pairs if a == b) / len(pairs), 3) if pairs else None, 'kappa': kappa(pairs)}
    return out


# ------------------------------------------------------------------ statistics

def _wilson(hits: int, n: int, z: float) -> tuple[float, float]:
    p = hits / n
    centre, spread = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - spread) / (1 + z * z / n)), min(1.0, (centre + spread) / (1 + z * z / n))


def wilson(hits: int, n: int, z: float = Z) -> list[float] | None:
    if not n:
        return None
    low, high = _wilson(hits, n, z)
    return [round(low, 3), round(high, 3)]


def newcombe(h1: int, n1: int, h2: int, n2: int, z: float = Z) -> list[float]:
    """Newcombe's hybrid score interval for a difference of two proportions (method 10)."""
    p1, p2 = h1 / n1, h2 / n2
    l1, u1 = _wilson(h1, n1, z)
    l2, u2 = _wilson(h2, n2, z)
    d = p1 - p2
    return [round(d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), 3), round(d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2), 3)]


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for two reviewers' categorical answers."""
    if len(pairs) < 2:
        return None
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(left[c] * right[c] for c in set(left) | set(right)) / (n * n)
    return round((observed - expected) / (1 - expected), 3) if expected < 1 else None


def results(review_set: dict, key: dict, decisions: list[dict], adjudications: list[dict]) -> dict:
    """The unblinded results. Refuses until every item has two complete reviews and every disagreement is adjudicated."""
    state = status(review_set, decisions, adjudications)
    if not state['complete']:
        raise ValueError(f"The review is not complete: {state['items_with_two_reviews']} of {state['items']} items have two reviews and "
                         f"{len(state['pending'])} disagreement(s) await adjudication.")
    final = final_labels(review_set, decisions, adjudications)
    reviews = _reviews(review_set, decisions)
    rulings = {(a['item_id'], a['question']): a for a in adjudications}
    arms = {}
    for arm in ARMS:
        ids = sorted(i for i, k in key['items'].items() if arm in k['sampled_by'])
        n = len(ids)
        row = {'label': ARM_LABEL[arm], 'n': n, 'pool': key['pools'].get(arm), 'frame': key['frames'].get(arm)}
        for m, (_, f) in MEASURES.items():
            hits = sum(1 for i in ids if f(final[i]))
            row[m] = {'hits': hits, 'n': n, 'rate': round(hits / n, 3) if n else None, 'interval': wilson(hits, n)}
        for name, (q, values) in SECONDARY.items():
            row[name] = round(sum(sum(1 for d in reviews[i].values() if d['answers'][q] in values) / len(reviews[i]) for i in ids) / n, 3) if n else None
        # The kind of record differs by method (by design) and stays visible as evidence, so results are also shown by it.
        by_record: dict[str, dict] = {}
        for i in ids:
            b = by_record.setdefault(key['items'][i]['objective'].get('record_type') or 'Not recorded', {'n': 0, 'relevant': 0, 'actionable': 0})
            b['n'] += 1
            b['relevant'] += int(MEASURES['relevant'][1](final[i]))
            b['actionable'] += int(MEASURES['actionable'][1](final[i]))
        row['by_record_type'] = by_record
        minutes = [sum(d.get('minutes') or 0 for d in reviews[i].values()) / len(reviews[i]) for i in ids]
        row['minutes_per_item'] = round(sum(minutes) / n, 1) if n else None
        obj = [key['items'][i]['objective'] for i in ids]
        ages = sorted(o['evidence_age_days'] for o in obj if o.get('evidence_age_days') is not None)
        row['objective'] = {'median_evidence_age_days': ages[len(ages) // 2] if ages else None,
                            'advertised_share': round(sum(1 for o in obj if o.get('advertised')) / n, 3) if n else None,
                            'with_route_on_record': round(sum(1 for o in obj if o.get('routes_on_record')) / n, 3) if n else None,
                            'by_source': dict(Counter(o.get('type') for o in obj))}
        arms[arm] = row
    overlap = {'|'.join(sorted(p)): sum(1 for k in key['items'].values() if set(p) <= set(k['sampled_by'])) for p in combinations(ARMS, 2)}
    comparisons, verdicts = [], []
    for family, pairs in (('primary', PRIMARY_COMPARISONS), ('secondary', SECONDARY_COMPARISONS)):
        for a, b, m in pairs:
            x, y = arms[a][m], arms[b][m]
            row = {'family': family, 'arms': [a, b], 'measure': m, 'overlap': overlap['|'.join(sorted((a, b)))], 'difference': None,
                   'interval': None, 'adjusted_interval': None, 'supported': False}
            if x['n'] and y['n']:
                adjusted = newcombe(x['hits'], x['n'], y['hits'], y['n'], Z_ADJ)
                row.update({'difference': round(x['rate'] - y['rate'], 3), 'interval': newcombe(x['hits'], x['n'], y['hits'], y['n']),
                            'adjusted_interval': adjusted, 'supported': adjusted[0] > 0 or adjusted[1] < 0})
            comparisons.append(row)
            label = f"{ARM_LABEL[a]} and {ARM_LABEL[b]} on {MEASURES[m][0].lower()} (n = {x['n']} and {y['n']})"
            if row['supported']:
                lo, hi = row['adjusted_interval']
                verdicts.append(f"{ARM_LABEL[a]} {'higher' if row['difference'] > 0 else 'lower'} than {ARM_LABEL[b]} on {MEASURES[m][0].lower()}: "
                                f"difference {row['difference']:+.0%}, adjusted interval {lo:+.0%} to {hi:+.0%} ({family}).")
            else:
                verdicts.append(f'No statistically supported difference between {label}.')
    relevant = {i for i, f in final.items() if f['relevance'] == 'yes'}
    explore = arms['exploratory']['worth_investigating']
    disagreements = []
    for item in sorted({d['item_id'] for d in state['disagreements']}):
        rows = [d for d in state['disagreements'] if d['item_id'] == item]
        disagreements.append({'item_id': item, 'questions': [{'question': d['question'], 'answers': d['answers'],
                                                             'final': rulings[(item, d['question'])]['answer'],
                                                             'method': rulings[(item, d['question'])]['method'],
                                                             'adjudicator': rulings[(item, d['question'])]['adjudicator'],
                                                             'rationale': rulings[(item, d['question'])]['rationale']} for d in rows]})
    return {'set_key': review_set['set_key'], 'items': len(review_set['items']), 'reviewers': state['reviewers'], 'reviews': state['reviews'],
            'arms': arms, 'overlap': overlap, 'comparisons': comparisons, 'verdicts': verdicts,
            'exploratory': {'rule': PROTOCOL['exploratory_rule'], 'worth_investigating': explore,
                            'met': bool(explore['n']) and explore['rate'] >= EXPLORATORY_RULE},
            'agreement': state['agreement'], 'disagreements': disagreements,
            'missed_by_qualified': sorted(i for i in relevant if 'qualified' not in key['items'][i]['in_pools']),
            'missed_by_salesintel': sorted(i for i in relevant if not {'qualified', 'exploratory'} & set(key['items'][i]['in_pools'])),
            'pools': key['pools'], 'frames': key['frames'], 'excluded_published': key.get('excluded_published'),
            'future_evidence_dropped': key.get('future_evidence_dropped'), 'statistics': PROTOCOL['statistics'],
            'note': ('Every measure comes from final labels: agreed answers, or adjudicated ones where two reviewers differed. '
                     'With samples this small the intervals are wide; no difference is claimed unless its adjusted interval excludes zero.')}
