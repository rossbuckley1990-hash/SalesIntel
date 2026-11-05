"""Test whether indirect signals beat renewal dates, using only what was public then.

For each settled contract the decision date falls before its end. Only observations
available before that date count. The outcome is a later official notice for the same
buyer and service, so the arms are scored against the same independent event. A rule
that only explains the past proves nothing, so nothing here is fitted to the outcome.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from math import comb, sqrt
from statistics import median

from app.intelligence.renewal_radar import _buyer_key, _overlap, _title_tokens, families
from app.intelligence.signal_inference import MAX_AGE_DAYS, OVERLAP_TITLE, TAXONOMY, council_key

DECISION_DAYS_BEFORE_END = 270
OUTCOME_DAYS_AFTER_END = 180
FIRST_END, LAST_END = date(2024, 4, 1), date(2026, 4, 30)
# A published replacement is the outcome being predicted, so it cannot also be a predictor.
INDIRECT = {x for x, v in TAXONOMY.items() if v['category'] in 'ABCD'} - {'supplier_replaced', 'out_of_cycle_relet'}
OFFICIAL = {'market_engagement'}


def _day(value):
    return date.fromisoformat(value) if value else None


def wilson(hits: int, total: int) -> list[float] | None:
    if not total:
        return None
    z, share = 1.96, hits / total
    centre = (share + z * z / (2 * total)) / (1 + z * z / total)
    spread = z * sqrt(share * (1 - share) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [round(max(0, centre - spread), 3), round(min(1, centre + spread), 3)]


def fisher_greater(a: int, b: int, c: int, d: int) -> float:
    """One-sided chance of at least a hits among flagged contracts if flags were random."""
    total, flagged, hits = a + b + c + d, a + b, a + c
    return round(sum(comb(hits, k) * comb(total - hits, flagged - k) for k in range(a, min(flagged, hits) + 1)) / comb(total, flagged), 4)


def _market_events(notices: list[dict]) -> dict:
    events = defaultdict(list)
    for notice in notices:
        if not notice.get('published') or not families(notice['title']):
            continue
        # An outcome is dated by when the notice became observable (its publication),
        # never by a planned approach date, which can precede or follow publication.
        day = _day(notice['published'])
        events[_buyer_key(notice['buyer'])].append({'day': day, 'approach': _day(notice.get('approach')), 'tokens': _title_tokens(notice['title']), 'fams': families(notice['title']), 'id': notice['id'], 'ocid': notice.get('ocid'), 'kind': notice.get('type')})
    return events


def _outcome(view: dict, events: list[dict], decision: date) -> date | None:
    tokens, fams, end = _title_tokens(view['title']), families(view['title']), _day(view['end'])
    days = [x['day'] for x in events if x['ocid'] != view.get('ocid') and x['fams'] & fams and _overlap(tokens, x['tokens']) >= OVERLAP_TITLE and decision < x['day'] <= end + timedelta(days=OUTCOME_DAYS_AFTER_END)]
    return min(days) if days else None


def _signals(view: dict, by_buyer: dict, decision: date, types: set, *, same_service: bool = True) -> list[dict]:
    fams = families(view['title'])
    published = _day(view['published']) if same_service else date.min
    found = []
    for key in {_buyer_key(view['buyer']), council_key(view['buyer'])}:
        for item in by_buyer.get(key, []):
            if item['signal_type'] in types and item['available_on'] < decision and (decision - item['occurred_on']).days <= MAX_AGE_DAYS and item['occurred_on'] >= published and (not same_service or set(item['families']) & fams) and item['source_url'] != view['url']:
                found.append(item)
    return list({x['fingerprint']: x for x in found}.values())


def _arm(rows: list[dict], flag: str) -> dict:
    a = sum(1 for x in rows if x[flag] and x['outcome'])
    b = sum(1 for x in rows if x[flag] and not x['outcome'])
    c = sum(1 for x in rows if not x[flag] and x['outcome'])
    d = sum(1 for x in rows if not x[flag] and not x['outcome'])
    flagged, base = a + b, (a + c) / len(rows) if rows else 0
    leads = [x['lead_' + flag] for x in rows if x[flag] and x['outcome'] and x.get('lead_' + flag) is not None]
    return {'flagged': flagged, 'precision': round(a / flagged, 3) if flagged else None, 'precision_95ci': wilson(a, flagged), 'false_positive_rate': round(b / (b + d), 3) if b + d else None, 'coverage_of_later_procurements': round(a / (a + c), 3) if a + c else None,
            'lift_over_all_contracts': round(a / flagged / base, 2) if flagged and base else None, 'one_sided_p': fisher_greater(a, b, c, d) if flagged else None, 'median_lead_days_before_market': median(leads) if leads else None, 'multi_source_share': round(sum(1 for x in rows if x[flag] and x['groups_' + flag] > 1) / flagged, 3) if flagged else None}


def run_backtest(views: list[dict], notices: list[dict], observations: list[dict]) -> dict:
    """Score the renewal baseline and each signal arm on the same settled contracts."""
    by_buyer, events = defaultdict(list), _market_events(notices)
    for item in observations:
        if item['buyer']:
            for key in {item['buyer_key'], council_key(item['buyer'])}:
                by_buyer[key].append(item)
    activity = defaultdict(list)
    for notice in notices:
        if notice.get('published'):
            activity[_buyer_key(notice['buyer'])].append(_day(notice['published']))
    rows = []
    for view in views:
        end = _day(view.get('end'))
        if view['fit'] not in {'core', 'bundled'} or not end or view['end_estimated'] or not FIRST_END <= end <= LAST_END:
            continue
        decision, published = end - timedelta(days=DECISION_DAYS_BEFORE_END), _day(view['published'])
        if not published or published >= decision:
            continue
        key = _buyer_key(view['buyer'])
        outcome = _outcome(view, events.get(key, []), decision)
        row = {'title': view['title'], 'buyer': view['buyer'], 'end': view['end'], 'decision': decision, 'outcome': outcome, 'activity': sum(1 for x in activity.get(key, []) if x < decision), 'renewal': True, 'groups_renewal': 1, 'lead_renewal': (outcome - (end - timedelta(days=548))).days if outcome else None}
        for flag, types, same in (('indirect', INDIRECT, True), ('official', OFFICIAL, True), ('combined', INDIRECT | OFFICIAL, True), ('customer', INDIRECT, False)):
            signals = _signals(view, by_buyer, decision, types, same_service=same)
            row[flag] = bool(signals)
            row['groups_' + flag] = len({x['source_group'] for x in signals})
            row['lead_' + flag] = (outcome - min(x['available_on'] for x in signals)).days if signals and outcome else None
            row['types_' + flag] = sorted({x['signal_type'] for x in signals})
        rows.append(row)
    cut = median([x['activity'] for x in rows]) if rows else 0
    busy, quiet = [x for x in rows if x['activity'] > cut], [x for x in rows if x['activity'] <= cut]
    by_type = {}
    for name in sorted(INDIRECT | OFFICIAL):
        hit = [x for x in rows if name in x['types_combined'] or name in x['types_customer']]
        by_type[name] = {'flagged': len(hit), 'later_procurement': sum(1 for x in hit if x['outcome'])}
    return {'population': len(rows), 'later_procurements': sum(1 for x in rows if x['outcome']), 'decision_rule': f'{DECISION_DAYS_BEFORE_END} days before the published end', 'arms': {'renewal_date_only': _arm(rows, 'renewal'), 'official_early_notices': _arm(rows, 'official'), 'indirect_signals': _arm(rows, 'indirect'), 'indirect_or_official': _arm(rows, 'combined'), 'sensitivity_any_signal_at_the_customer': _arm(rows, 'customer')},
            'confounding_check': {'active_buyers': {'contracts': len(busy), 'customer_wide': _arm(busy, 'customer')}, 'quiet_buyers': {'contracts': len(quiet), 'customer_wide': _arm(quiet, 'customer')}}, 'by_signal_type': by_type,
            'examples': [{k: str(x[k]) for k in ('buyer', 'title', 'end', 'decision', 'outcome', 'types_indirect')} for x in rows if x['customer']][:12]}


def prospective_scorecard(hypotheses: list[dict], notices: list[dict], today: date) -> dict:
    """Hypotheses dated when they were made, scored later against official notices.

    This is the test that cannot leak: the claim is on record before the outcome exists.
    """
    events = _market_events(notices)
    made, followed, waiting = 0, [], 0
    for item in hypotheses:
        if item['decision'] not in {'pursue', 'verify'} or not item['buyer']:
            continue
        made += 1
        # Only notices first published after the claim and no later than today count.
        later = [x for x in events.get(_buyer_key(item['buyer']), []) if item['first_seen'] < x['day'] <= today]
        if later:
            followed.append({'buyer': item['buyer'], 'kind': item['kind'], 'made_on': str(item['first_seen']), 'first_notice_published': str(min(x['day'] for x in later))})
        elif (today - item['first_seen']).days < 365:
            waiting += 1
    return {'hypotheses_on_record': made, 'followed_by_a_notice': len(followed), 'still_within_12_months': waiting, 'examples': followed[:8]}


def incremental_discoveries(views: list[dict], notices: list[dict], observations: list[dict], *, first: date = date(2024, 4, 1), last: date = date(2026, 10, 31), notice_days: int = 60) -> dict:
    """Of tenders the renewal list could not foresee, how many had an earlier indirect signal?"""
    by_buyer = defaultdict(list)
    for item in observations:
        if item['buyer'] and item['signal_type'] in INDIRECT:
            for key in {item['buyer_key'], council_key(item['buyer'])}:
                by_buyer[key].append(item)
    contracts = defaultdict(list)
    for view in views:
        if view.get('end') and view['fit'] in {'core', 'bundled'}:
            contracts[_buyer_key(view['buyer'])].append(view)
    total = foreseen = unseen = signalled = 0
    for notice in notices:
        if notice.get('type') != 'Contract' or notice.get('status') not in {'Open', 'Closed'} or not notice.get('published') or not families(notice['title']):
            continue
        day = _day(notice['published'])
        if not first <= day <= last:
            continue
        total += 1
        key, tokens, fams = _buyer_key(notice['buyer']), _title_tokens(notice['title']), families(notice['title'])
        known = any(_day(x['published']) < day and abs((_day(x['end']) - day).days) <= 548 and families(x['title']) & fams and _overlap(_title_tokens(x['title']), tokens) >= OVERLAP_TITLE for x in contracts.get(key, []) if x.get('published'))
        if known:
            foreseen += 1
            continue
        unseen += 1
        signalled += any(x['available_on'] <= day - timedelta(days=notice_days) and (day - x['occurred_on']).days <= MAX_AGE_DAYS and set(x['families']) & fams for k in {key, council_key(notice['buyer'])} for x in by_buyer.get(k, []))
    return {'tenders': total, 'foreseeable_from_a_held_contract': foreseen, 'not_foreseeable_from_a_held_contract': unseen, 'of_those_with_an_earlier_indirect_signal': signalled}
