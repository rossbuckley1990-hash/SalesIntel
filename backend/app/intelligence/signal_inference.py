"""Infer commercial conditions nobody has announced, without claiming them as fact.

A customer's satisfaction or a contractor's delivery cannot be seen directly, so
this reasons from what can: procurement behaviour, fire service attendance,
regulator findings and insolvency notices. The pipeline is observe, link,
hypothesise, challenge, corroborate, prioritise and act. Each hypothesis names
rival explanations and what would separate them. There are no probabilities: no
data here could calibrate one, so evidence states are descriptive. A contractor
is treated as responsible only when a source says so.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
import hashlib
import json
from math import exp, lgamma, log
import re

from app.intelligence.contract_terms import iso_day
from app.intelligence.renewal_radar import (ACT_NOW_TO_DAYS, FAMILIES, OWN_GROUP, WINDOW_FUTURE_DAYS, _buyer_key, _overlap, _title_tokens, classify, families)

RULE_VERSION = 'signal-inference-v1'
MAX_AGE_DAYS = 730
OVERLAP_TITLE = 0.3
SAME_RELET_GAP_DAYS = 120
OUT_OF_CYCLE_DAYS = 180
SHORT_TERM_DAYS = 270
RETENDER_WINDOW_DAYS = 730
FIRE_POLICY_START = date(2024, 11, 1)
FIRE_PUBLICATION_LAG_DAYS = 45
FIRE_RECENT_DAYS = 182
FIRE_BASELINE_DAYS = 365
FIRE_MIN_RECENT = 6
FIRE_MIN_RATIO = 2.0
FIRE_MAX_P = 0.01
FIRE_FAMILIES = ['fire_alarm']
COMPETITOR_WIN_DAYS = 365
COMPETITOR_MIN_WINS = 3
COMPETITOR_MIN_LOSSES = 2
PLAUSIBLE_PURSUIT_MIN = 2

# category: A performance, B dissatisfaction, C operational, D procurement, E contractor stress, F estate or demand, G competitor.
TAXONOMY = {
    'published_performance_finding': {'category': 'A', 'label': 'Published finding about contract performance'},
    'customer_concern_published': {'category': 'B', 'label': 'Customer concern in a public paper'},
    'regulator_compliance_finding': {'category': 'C', 'label': 'Regulator finding on fire safety compliance'},
    'fire_enforcement_outcome': {'category': 'C', 'label': 'Fire authority inspection outcome'},
    'false_alarm_rise': {'category': 'C', 'label': 'Rise in fire service alarm attendances'},
    'remedial_programme': {'category': 'C', 'label': 'Remedial or corrective work procured'},
    'emergency_procurement': {'category': 'D', 'label': 'Emergency or urgent procurement'},
    'tender_abandoned': {'category': 'D', 'label': 'Procurement cancelled or abandoned'},
    'contract_terminated': {'category': 'D', 'label': 'Contract published as terminated'},
    'contract_modified': {'category': 'D', 'label': 'Contract extended or varied'},
    'short_term_award': {'category': 'D', 'label': 'Unusually short service award'},
    'out_of_cycle_relet': {'category': 'D', 'label': 'Replacement before the published end'},
    'repeated_retender': {'category': 'D', 'label': 'Repeated tendering of the same service'},
    'supplier_replaced': {'category': 'D', 'label': 'Published supplier changed'},
    'supplier_insolvency': {'category': 'E', 'label': 'Insolvency notice'},
    'supplier_filing_overdue': {'category': 'E', 'label': 'Statutory filing overdue'},
    'control_change': {'category': 'G', 'label': 'Corporate control change'},
    'estate_expansion': {'category': 'F', 'label': 'New or enlarged estate'},
    'market_engagement': {'category': 'F', 'label': 'Official market engagement'},
    'competitor_acquisition': {'category': 'G', 'label': 'Published acquisition'},
    'issue_resolved': {'category': 'X', 'label': 'Published resolution'},
    'attribution_elsewhere': {'category': 'X', 'label': 'Published cause other than the contractor'},
}
# Rival explanations, what supports each, and the question that would separate them.
EXPLANATIONS = {
    'contractor_delivery': ('The current contractor may be under-delivering', 'Does the customer attribute the problem to this contractor under this contract?'),
    'ageing_assets': ('Ageing or obsolete systems', 'Do published asset or backlog records show end-of-life equipment?'),
    'capital_programme': ('A planned capital or replacement programme', 'Is the work in an approved capital plan?'),
    'estate_change': ('Building work or a changed estate', 'Were works, occupancy changes or new buildings under way at the time?'),
    'deferred_compliance': ('Compliance work deferred by the customer', 'Does a regulator or audit place the backlog with the customer rather than a contractor?'),
    'routine_procurement': ('Ordinary procurement or budget timing', 'Was this a planned extension, re-let or budget decision?'),
    'corporate_change': ('Corporate change at the supplier', 'Was the change a merger, rebrand or novation rather than a problem?'),
}
_RIVALS = {'false_alarm_rise': ['contractor_delivery', 'ageing_assets', 'estate_change'], 'remedial_programme': ['contractor_delivery', 'ageing_assets', 'capital_programme', 'deferred_compliance'],
           'regulator_compliance_finding': ['deferred_compliance', 'contractor_delivery', 'ageing_assets'], 'fire_enforcement_outcome': ['deferred_compliance', 'ageing_assets', 'contractor_delivery'],
           'emergency_procurement': ['contractor_delivery', 'routine_procurement', 'ageing_assets'], 'tender_abandoned': ['routine_procurement', 'contractor_delivery'], 'contract_terminated': ['contractor_delivery', 'routine_procurement', 'corporate_change'],
           'contract_modified': ['routine_procurement', 'capital_programme'], 'short_term_award': ['routine_procurement', 'contractor_delivery'], 'out_of_cycle_relet': ['routine_procurement', 'contractor_delivery', 'estate_change'],
           'repeated_retender': ['routine_procurement', 'contractor_delivery'], 'supplier_replaced': ['routine_procurement', 'contractor_delivery', 'corporate_change'], 'supplier_insolvency': ['corporate_change'], 'supplier_filing_overdue': ['routine_procurement', 'corporate_change'],
           'published_performance_finding': ['contractor_delivery'], 'customer_concern_published': ['contractor_delivery', 'ageing_assets', 'deferred_compliance']}
PROBLEM_SIGNALS = {x for x, v in TAXONOMY.items() if v['category'] in 'ABC'}
INSTABILITY_SIGNALS = {x for x, v in TAXONOMY.items() if v['category'] == 'D'}
_CONTRADICTIONS = {'issue_resolved', 'attribution_elsewhere'}
COMPLIANCE_SIGNALS = {'regulator_compliance_finding', 'fire_enforcement_outcome'}
FIRE_WORK = {'fire_alarm', 'emergency_lighting', 'extinguishers', 'sprinklers', 'smoke_control', 'passive_fire', 'fire_risk_assessment'}
REQUIREMENT_SIGNALS = {'regulator_compliance_finding', 'fire_enforcement_outcome', 'estate_expansion', 'customer_concern_published'}
# "Emergency lighting" and "emergency call-out" are ordinary scope, so the word alone proves nothing.
_EMERGENCY = re.compile(r'\b(?:emergency\s+(?:procurement|appointment|award|contract|replacement)|extreme\s+urgency|urgent(?:ly)?\s+(?:required|needed|procure\w*|appoint\w*))\b', re.I)
_MODIFIED = re.compile(r'\b(?:extension\s+(?:of|to)\s+(?:the\s+)?(?:contract|term|existing)|contract\s+extension|variation|modification|voluntary\s+ex[\s-]ante|veat)\b', re.I)
_REMEDIAL = re.compile(r'\b(?:remedial|rectif\w*|defects?|non[\s-]?compliance|corrective)\b', re.I)
_ESTATE = re.compile(r'\b(?:new[\s-]build|new\s+(?:primary\s+|secondary\s+)?school|new\s+hospital|new\s+(?:\w+\s+)?(?:centre|facility|campus|building|depot|library|station)|construction\s+of|hospital\s+expansion|extension\s+to\s+the\s+\w+\s+(?:hospital|school|building))\b', re.I)
_INTERIM = re.compile(r'\b(?:interim|temporary|short[\s-]term|bridging)\b', re.I)


def _day(value):
    return date.fromisoformat(value) if value else None


def _text(value, limit=2000) -> str:
    return ' '.join(value.split())[:limit] if isinstance(value, str) else ''


def fingerprint(*parts) -> str:
    return hashlib.sha256('\0'.join(str(x) for x in parts).encode()).hexdigest()


# Trading names of one corporate group in published notices. Grouping is not proof of a legal link.
COMPETITOR_GROUPS = {'PTSG': r'premier technical services|\bptsg\b', 'Trinity Fire & Security': r'\btrinity fire\b', 'Chubb Fire & Security': r'\bchubb\b', 'Churches Fire & Security': r'\bchurches fire\b',
                     'Ranger Fire and Security': r'\branger fire\b', 'Johnson Controls (ADT, Tyco)': r'\btyco fire\b|\badt fire\b|\bjohnson controls\b', 'Openview Security': r'\bopenview security\b',
                     'Reliance High-Tech': r'\breliance high[\s-]tech\b', 'Kings Secure Technologies': r'\bkings? se(?:cure|curity)\b', 'SPIE Scotshield': r'\bscotshield\b'}
_GROUPS = {name: re.compile(pattern, re.I) for name, pattern in COMPETITOR_GROUPS.items()}


def competitor_group(name: str) -> str:
    """A watched group, or the name with spelling differences removed."""
    return next((group for group, pattern in _GROUPS.items() if pattern.search(name)), _buyer_key(name).replace(' and ', ' '))


def observation(signal_type: str, *, statement: str, occurred: date, available: date | None = None, url: str, group: str, reliability: str, buyer: str | None = None, supplier: str | None = None,
                company_number: str | None = None, fams=(), scope: str = 'organisation', attribution: str = 'none', capture: str = 'automatic', revision_id: int | None = None, detail: dict | None = None) -> dict:
    return {'fingerprint': fingerprint(signal_type, url, occurred, buyer, supplier), 'signal_type': signal_type, 'scope': scope, 'buyer': buyer, 'buyer_key': _buyer_key(buyer) if buyer else None,
            'supplier': supplier, 'supplier_key': _buyer_key(supplier) if supplier else None, 'company_number': company_number, 'families': sorted(fams), 'statement': statement, 'occurred_on': occurred,
            'available_on': available or occurred, 'source_group': group, 'reliability': reliability, 'attribution': attribution, 'capture': capture, 'source_url': url, 'source_revision_id': revision_id, 'detail': detail or {}}


def _full(raw: dict) -> tuple[str, str]:
    tender = raw.get('tender') if isinstance(raw.get('tender'), dict) else {}
    return _text(tender.get('title')), _text(tender.get('description'))


def procurement_observations(rows: list) -> list[dict]:
    """What each stored notice shows by itself. Every one shares one source lineage."""
    found = []
    for row in rows:
        raw = row.raw if isinstance(row.raw, dict) else {}
        title, body = _full(raw)
        buyer = _text((raw.get('buyer') or {}).get('name'), 250)
        day = row.published_at.date() if row.published_at else None
        fams = families(f'{title} {body}')
        if not title or not buyer or not day or not fams:
            continue
        shared = {'occurred': day, 'url': row.source_url, 'group': 'procurement', 'reliability': 'official_notice', 'buyer': buyer, 'fams': fams, 'revision_id': row.id, 'scope': 'contract', 'detail': {'title': title[:200], 'ocid': row.ocid}}
        tender = raw.get('tender') or {}
        tags = {str(x).lower() for x in raw.get('tag') or []}
        awards = [x for x in raw.get('awards') or [] if isinstance(x, dict)]
        if tags & {'tendercancellation'} or str(tender.get('status')).lower() in {'cancelled', 'withdrawn'} or any(str(x.get('statusDetails')).lower() == 'discontinued' for x in awards):
            found.append(observation('tender_abandoned', statement=f'{buyer} published that the procurement "{title[:120]}" was cancelled or discontinued.', **shared))
        if any(str(x.get('status')).lower() in {'terminated', 'cancelled'} for x in raw.get('contracts') or [] if isinstance(x, dict)):
            found.append(observation('contract_terminated', statement=f'{buyer} published a contract under "{title[:120]}" as terminated or cancelled. No reason is implied.', **shared))
        if _EMERGENCY.search(f'{title} {body}') and families(title):
            found.append(observation('emergency_procurement', statement=f'{buyer} described "{title[:120]}" in emergency or urgent terms.', **shared))
        if tags & {'contractamendment'} or _MODIFIED.search(title):
            found.append(observation('contract_modified', statement=f'{buyer} published an extension or change to "{title[:120]}".', **shared))
        if _REMEDIAL.search(title) and families(title):
            found.append(observation('remedial_programme', statement=f'{buyer} procured remedial or corrective work: "{title[:120]}".', **shared))
        if _ESTATE.search(title):
            found.append(observation('estate_expansion', statement=f'{buyer} published building work: "{title[:120]}". New space usually needs fire and security systems maintained.', **{**shared, 'scope': 'organisation'}))
        if tags & {'planning', 'planningupdate'} and classify({'title': title, 'description': body, 'start': None})[0] != 'exclude':
            found.append(observation('market_engagement', statement=f'{buyer} published an early notice: "{title[:120]}".', **shared))
    return found


def _supplier_form(name: str) -> str:
    """Ignore spacing and the word and, so Net View and NetView are one supplier."""
    return _buyer_key(name).replace(' and ', ' ').replace(' ', '')


def _lifecycle_group(views: list[dict]) -> dict:
    grouped = defaultdict(list)
    for view in views:
        if view.get('end') and view.get('published') and view['fit'] in {'core', 'bundled', 'adjacent'}:
            grouped[_buyer_key(view['buyer'])].append(view)
    return grouped


def sequence_observations(views: list[dict], notices: list[dict]) -> list[dict]:
    """Changes only visible across notices: replacements, early re-lets, repeat tenders."""
    found = []
    for rows in _lifecycle_group(views).values():
        ordered = sorted(rows, key=lambda x: x['published'])
        for index, old in enumerate(ordered):
            tokens, fams = _title_tokens(old['title']), families(old['title'])
            for new in ordered[index + 1:]:
                if not fams & families(new['title']) or _overlap(tokens, _title_tokens(new['title'])) < OVERLAP_TITLE or _day(new['end']) <= _day(old['end']):
                    continue
                changed = old['suppliers'] and new['suppliers'] and not {_supplier_form(x) for x in old['suppliers']} & {_supplier_form(x) for x in new['suppliers']}
                early = (_day(old['end']) - _day(new['published'])).days
                shared = {'occurred': _day(new['published']), 'url': new['url'], 'group': 'procurement', 'reliability': 'official_notice', 'buyer': old['buyer'], 'fams': fams & families(new['title']), 'scope': 'contract',
                          'detail': {'old_title': old['title'][:160], 'new_title': new['title'][:160], 'old_end': old['end'], 'new_suppliers': new['suppliers'][:4], 'old_suppliers': old['suppliers'][:4]}}
                if changed:
                    found.append(observation('supplier_replaced', statement=f"Similar titles suggest {old['buyer']} moved from {old['incumbent'][:60]} to {new['incumbent'][:60]}. This does not establish why.", supplier=old['suppliers'][0], **shared))
                if early > OUT_OF_CYCLE_DAYS:
                    found.append(observation('out_of_cycle_relet', statement=f"{old['buyer']} published \"{new['title'][:100]}\" {early} days before the published end of \"{old['title'][:80]}\".", supplier=old['suppliers'][0] if old['suppliers'] else None, **shared))
                break
    tenders = defaultdict(list)
    for notice in notices:
        if notice.get('type') == 'Contract' and notice.get('status') in {'Open', 'Closed'} and notice.get('published') and families(notice['title']):
            tenders[_buyer_key(notice['buyer'])].append(notice)
    for rows in tenders.values():
        rows.sort(key=lambda x: x['published'])
        for first, second in zip(rows, rows[1:]):
            gap = (_day(second['published']) - _day(first['published'])).days
            if 30 < gap <= RETENDER_WINDOW_DAYS and families(first['title']) & families(second['title']) and _overlap(_title_tokens(first['title']), _title_tokens(second['title'])) >= OVERLAP_TITLE:
                found.append(observation('repeated_retender', statement=f"{second['buyer']} went to market for \"{second['title'][:100]}\" {gap} days after a similar notice, with no award visible for the first.", occurred=_day(second['published']), url=second['url'],
                                         group='procurement', reliability='official_notice', buyer=second['buyer'], fams=families(first['title']) & families(second['title']), scope='contract', detail={'first': first['url'], 'title': second['title'][:200]}))
    for notice in notices:
        term = (_day(notice['end']) - _day(notice['start'])).days if notice.get('start') and notice.get('end') and notice['end'] > notice['start'] else None
        if notice.get('type') == 'Contract' and notice.get('status') == 'Awarded' and term and term < SHORT_TERM_DAYS and notice.get('published') and families(notice['title']) and classify(notice)[1] == 'term too short for recurring maintenance' and _INTERIM.search(f"{notice['title']} {notice.get('description') or ''}"):
            found.append(observation('short_term_award', statement=f"{notice['buyer']} made an interim award of {term} days: \"{notice['title'][:110]}\".", occurred=_day(notice['published']), url=notice['url'], group='procurement', reliability='official_notice', buyer=notice['buyer'],
                                     supplier=(notice.get('suppliers') or [None])[0], fams=families(notice['title']), scope='contract', detail={'title': notice['title'][:200]}))
    return found


def _poisson_upper_tail(count: int, mean: float) -> float:
    """Chance of at least count events if the earlier rate had simply continued."""
    if mean <= 0:
        return 0.0
    return min(1.0, sum(exp(k * log(mean) - mean - lgamma(k + 1)) for k in range(count, count + 200)))


def fire_service_rises(incidents: list[tuple[str, date]], *, as_of: date) -> list[dict]:
    """Sites whose recent automatic alarm attendances rose beyond their own earlier rate.

    Only dates after the attendance policy change count, and an incident counts once
    published, so a backtest cannot see it early. A rise says nothing about its cause.
    """
    cutoff = as_of - timedelta(days=FIRE_PUBLICATION_LAG_DAYS)
    recent_start, base_start = cutoff - timedelta(days=FIRE_RECENT_DAYS), cutoff - timedelta(days=FIRE_RECENT_DAYS + FIRE_BASELINE_DAYS)
    if base_start < FIRE_POLICY_START:
        base_start = FIRE_POLICY_START
    base_days = (recent_start - base_start).days
    if base_days < 90:
        return []
    counts = defaultdict(lambda: [0, 0])
    for uprn, day in incidents:
        if recent_start <= day < cutoff:
            counts[uprn][1] += 1
        elif base_start <= day < recent_start:
            counts[uprn][0] += 1
    found = []
    for uprn, (before, recent) in counts.items():
        expected = max(before, 1) * FIRE_RECENT_DAYS / base_days
        probability = _poisson_upper_tail(recent, expected)
        if recent >= FIRE_MIN_RECENT and recent / expected >= FIRE_MIN_RATIO and probability < FIRE_MAX_P:
            found.append({'uprn': uprn, 'before': before, 'recent': recent, 'expected': round(expected, 1), 'as_of': cutoff, 'base_days': base_days, 'tail_probability': round(probability, 5)})
    return found


def council_key(name: str) -> str:
    """One key for a council's published name variants; other organisations keep their own."""
    lowered = re.sub(r'[^a-z ]', ' ', name.lower())
    if not re.search(r'\b(?:council|borough|lbc|cc|dc|mbc)\b', lowered):
        return _buyer_key(name)
    return ' '.join(re.sub(r'\b(?:london|royal|borough|council|of|the|city|county|district|metropolitan|lbc|mbc|dc|cc|bc|and)\b', ' ', lowered).split())


def _fresh(item: dict, today: date) -> bool:
    return item['available_on'] <= today and (today - item['occurred_on']).days <= MAX_AGE_DAYS and not (item.get('retracted_on') and item['retracted_on'] <= today)


def apply_contradictions(items: list[dict], opposing: list[dict]) -> tuple[list[dict], list[dict]]:
    """(still standing, contradicting). Later evidence removes only what it actually answers.

    A good regulator grade answers a regulator finding, not a rise in alarm calls.
    An opposing item with no stated target answers everything earlier.
    """
    standing, used = [], {}
    for item in items:
        answers = [x for x in opposing if x['occurred_on'] >= item['occurred_on'] and (not x['detail'].get('answers') or item['signal_type'] in x['detail']['answers'])]
        if answers:
            used.update({x['fingerprint']: x for x in answers})
        else:
            standing.append(item)
    return standing, list(used.values())


def _matches_contract(item: dict, view: dict) -> str | None:
    """How an observation relates to a contract: the same service, the customer, or not at all."""
    fams = set(item['families'])
    wanted = families(view['title'])
    # Buyers run many contracts for one system, so the service alone does not identify one.
    named = item['detail'].get('old_title') or item['detail'].get('title')
    if fams and fams & wanted and (not named or _overlap(_title_tokens(named), _title_tokens(view['title'])) >= OVERLAP_TITLE):
        return 'same_service'
    # A signal about one named service stays with that service. Only customer-wide findings spread.
    return 'organisation' if not fams or item['signal_type'] in COMPLIANCE_SIGNALS else None


def evidence_state(items: list[dict], contradicted: list[dict]) -> tuple[str, list[str]]:
    groups = sorted({x['source_group'] for x in items})
    if contradicted:
        return 'contradicted', groups
    return ('independently_corroborated' if len(groups) > 1 else 'same_source_repeated' if len(items) > 1 else 'single_source'), groups


def challenge(items: list[dict], contradicted: list[dict], estate_notes: list[dict]) -> list[dict]:
    """Test each rival explanation against the evidence held, and say what stays unknown."""
    named = {name for item in items for name in _RIVALS.get(item['signal_type'], [])}
    attributed = [x for x in items if x['attribution'] == 'contractor']
    results = []
    for name in sorted(named, key=list(EXPLANATIONS).index):
        label, question = EXPLANATIONS[name]
        supporting = [x['fingerprint'] for x in items if name in _RIVALS.get(x['signal_type'], [])]
        against = [x['fingerprint'] for x in contradicted]
        status = 'possible'
        if name == 'contractor_delivery':
            status = 'supported_by_published_attribution' if attributed else 'not_established'
            if any(x['signal_type'] == 'attribution_elsewhere' for x in contradicted):
                status = 'contradicted'
        elif name == 'estate_change' and estate_notes:
            status, supporting = 'supported', supporting + [x['fingerprint'] for x in estate_notes]
        elif name == 'deferred_compliance' and any(x['signal_type'] == 'regulator_compliance_finding' for x in items):
            status = 'supported'
        results.append({'explanation': name, 'label': label, 'status': status, 'observations': supporting[:6], 'against': against[:6], 'test': question})
    return results


def _timing(view: dict, today: date) -> str:
    days = (_day(view['end']) - today).days
    return 'passed' if days < 0 else 'renewal_window' if days <= WINDOW_FUTURE_DAYS else 'beyond_window'


def arbitrate(kind: str, *, fit: str | None, timing: str | None, state: str, attribution_found: bool, has_value: bool, stale: bool, replaced: bool, own_group: bool) -> tuple[str, list[str]]:
    """PURSUE, VERIFY, MONITOR or DISMISS, with the reason for each gate."""
    reasons = []
    if state == 'contradicted':
        return 'dismiss', ['New evidence contradicts a key assumption.']
    if replaced:
        return 'dismiss', ['The contract appears to have been replaced already, so the opening has passed.']
    if stale:
        return 'dismiss', ['The evidence is too old to act on.']
    if fit == 'framework':
        return 'monitor', ['A framework agreement, so action depends on call-offs rather than one contract.']
    if timing == 'beyond_window':
        return 'monitor', ['The contract ends beyond the 18-month window, so watch it.']
    if timing == 'passed':
        return 'verify', ['The published term has passed, so the current arrangement must be confirmed first.']
    corroborated = state == 'independently_corroborated'
    reasons.append('Independent sources agree something is happening.' if corroborated else 'Only one line of evidence so far.')
    if kind in {'competitor_strength', 'competitor_pursuit'}:
        return 'monitor', ['Market awareness rather than a lead.']
    if kind in {'hidden_requirement', 'incumbent_vulnerability', 'contract_instability', 'supplier_stress', 'retention_risk'}:
        if corroborated and fit in {'core', 'bundled', None} and (has_value or own_group or kind == 'hidden_requirement'):
            return 'pursue', reasons + ['Relevant, timely and supported by more than one source. This justifies investigation, not an assumption of a contract.']
        return 'verify', reasons + ['An important assumption needs testing first.']
    return 'monitor', reasons


_ACTIONS = {'incumbent_vulnerability': ['Confirm whether the published concern falls under this contract and whether it has been resolved.', 'Check whether an extension option has been exercised.', "Review the customer's published procurement plan.",
                                        'Identify the appropriate estates or procurement decision-making role through public sources.', 'Prepare a capability-led introduction that makes no claim about the current contractor.'],
            'contract_instability': ['Investigate the current contractual relationship.', 'Check the latest notices for the reason behind the change.', 'Monitor the renewal date and any market engagement.'],
            'supplier_stress': ['Confirm from the notice that this is the same legal company as the contractor.', 'Check who is delivering the contract now.', 'Investigate whether a compliant market-engagement opportunity exists.'],
            'retention_risk': ['Escalate to the account lead for retention planning.', 'Confirm internally whether the published concern relates to this contract.'],
            'hidden_requirement': ['Confirm the finding in the source and whether the customer has a remediation plan.', "Review the customer's published procurement plan.", 'Investigate whether a compliant market-engagement opportunity exists.', 'Prepare a capability-led introduction.'],
            'competitor_vulnerability': ['Confirm the legal entity and which contracts are affected.', 'Monitor affected contract dates. Make no claims about the competitor to customers.'],
            'competitor_strength': ['Note the change in market position for bid planning.'], 'competitor_pursuit': ['Allow for this competitor in bid planning. Its participation is not confirmed.']}


def assess(kind: str, items: list[dict], *, today: date, contradicted: list[dict] | None = None, estate: list[dict] | None = None, view: dict | None = None, replaced: bool = False, buyer: str | None = None, supplier: str | None = None, link: str = '') -> dict:
    contradicted = contradicted or []
    state, groups = evidence_state(items, contradicted)
    explanations = challenge(items, contradicted, estate or [])
    timing = _timing(view, today) if view else None
    stale = bool(items) and min((today - x['occurred_on']).days for x in items) > MAX_AGE_DAYS
    own_group = bool(view and view.get('own_group'))
    decision, reasons = arbitrate(kind, fit=view['fit'] if view else None, timing=timing, state=state, attribution_found=any(x['attribution'] == 'contractor' for x in items), has_value=bool(view and view.get('value')), stale=stale, replaced=replaced, own_group=own_group)
    label = {'incumbent_vulnerability': 'Potential incumbent vulnerability: investigation recommended', 'contract_instability': 'Procurement instability: investigation recommended', 'supplier_stress': 'Possible contractor stress: verification needed',
             'retention_risk': 'Possible retention risk on a Mitie group contract', 'hidden_requirement': 'Possible requirement before any tender', 'competitor_strength': 'Competitive strength', 'competitor_vulnerability': 'Potential competitive vulnerability',
             'competitor_pursuit': 'Potential competitive pursuit'}[kind]
    unknown = ['Whether the named contractor is responsible.'] if kind in {'incumbent_vulnerability', 'contract_instability'} else []
    if view and view.get('extension_mentioned'):
        unknown.append('Whether an extension has been used.')
    unknown.append('Whether the condition continues today.')
    return {'rule_version': RULE_VERSION, 'kind': kind, 'label': label, 'buyer': buyer, 'supplier': supplier, 'decision': decision, 'decision_reasons': reasons, 'evidence_state': state, 'independent_sources': groups, 'link': link,
            'timing': timing, 'contract_end': view.get('end') if view else None, 'supporting': [_public(x) for x in items[:10]], 'contradicting': [_public(x) for x in contradicted[:6]], 'explanations': explanations, 'unknowns': unknown,
            'first_signal': min((x['occurred_on'] for x in items), default=today).isoformat(), 'last_signal': max((x['occurred_on'] for x in items), default=today).isoformat(), 'actions': _ACTIONS[kind],
            'caution': 'An inference from public records, not a finding about any company. Do not repeat it to a customer as fact.'}


def _public(item: dict) -> dict:
    return {'fingerprint': item['fingerprint'], 'signal_type': item['signal_type'], 'label': TAXONOMY[item['signal_type']]['label'], 'statement': item['statement'], 'occurred_on': item['occurred_on'].isoformat(), 'source_group': item['source_group'],
            'reliability': item['reliability'], 'attribution': item['attribution'], 'capture': item['capture'], 'source_url': item['source_url'], 'scope': item['scope']}


def contract_hypotheses(views: list[dict], observations: list[dict], today: date) -> dict:
    """Join observations to live contracts. A signal is applied to one contract only by a stated link."""
    by_buyer, by_supplier, by_number = defaultdict(list), defaultdict(list), defaultdict(list)
    for item in observations:
        if not _fresh(item, today) or item['signal_type'] not in TAXONOMY:
            continue
        if item['company_number']:
            by_number[item['company_number']].append(item)
        for key in {item['buyer_key'], council_key(item['buyer'])} if item['buyer'] else ():
            by_buyer[key].append(item)
        if item['supplier_key']:
            by_supplier[item['supplier_key']].append(item)
    found = {}
    for view in views:
        if view['fit'] == 'framework' or not view.get('end') or view['fit'] == 'adjacent' or (today - _day(view['end'])).days > 365:
            continue
        keys = {_buyer_key(view['buyer']), council_key(view['buyer'])}
        linked, opposing, estate = {}, {}, {}
        for key in keys:
            for item in by_buyer.get(key, []):
                relation = _matches_contract(item, view)
                if item['signal_type'] in _CONTRADICTIONS:
                    opposing[item['fingerprint']] = item
                elif item['signal_type'] == 'estate_expansion':
                    estate[item['fingerprint']] = item
                elif relation and item['signal_type'] in PROBLEM_SIGNALS | INSTABILITY_SIGNALS and item['occurred_on'] >= _day(view['published']) and item['source_url'] != view['url']:
                    # A replacement describes one earlier contract, not its neighbours at this customer.
                    if item['detail'].get('old_title') and item['detail']['old_title'] != view['title'][:160]:
                        continue
                    linked[item['fingerprint']] = {**item, 'relation': relation}
        # A published company number is the strong link; a name is only a lead to confirm.
        named = [x for name in {_buyer_key(s) for s in view['suppliers']} for x in by_supplier.get(name, [])] + [x for number in view.get('company_numbers') or [] for x in by_number.get(number, [])]
        stress = list({x['fingerprint']: x for x in named if x['signal_type'] == 'supplier_insolvency'}.values())
        filings = list({x['fingerprint']: x for x in named if x['signal_type'] == 'supplier_filing_overdue'}.values())
        items, against = apply_contradictions(sorted(linked.values(), key=lambda x: x['occurred_on']), list(opposing.values()))
        if linked and not items:
            items, withdrawn = sorted(linked.values(), key=lambda x: x['occurred_on']), against
        else:
            withdrawn = []
        key = f"{view['ocid']}:{view['lot']}"
        replaced = bool(view.get('successor_url'))
        # A finding about the customer says nothing about one supplier. Only a signal
        # naming the same service can raise a question about the incumbent.
        problems = [x for x in items if x['signal_type'] in PROBLEM_SIGNALS and x['relation'] == 'same_service']
        items = [x for x in items if x['relation'] == 'same_service' or x['signal_type'] in INSTABILITY_SIGNALS]
        if view['own_group'] and items:
            found[f'retention:{key}'] = (assess('retention_risk', items, today=today, contradicted=withdrawn, estate=list(estate.values()), view=view, replaced=replaced, buyer=view['buyer'], supplier=view['incumbent'], link=_link(items)), key)
        elif problems:
            found[f'vulnerability:{key}'] = (assess('incumbent_vulnerability', items, today=today, contradicted=withdrawn, estate=list(estate.values()), view=view, replaced=replaced, buyer=view['buyer'], supplier=view['incumbent'], link=_link(items)), key)
        elif items:
            found[f'instability:{key}'] = (assess('contract_instability', items, today=today, contradicted=withdrawn, view=view, replaced=replaced, buyer=view['buyer'], supplier=view['incumbent'], link=_link(items)), key)
        identity = 'Matched on a published company number.' if any(x['company_number'] in (view.get('company_numbers') or []) for x in stress + filings) else 'Same published company name; confirm the company number.'
        if stress:
            found[f'stress:{key}'] = (assess('supplier_stress', stress + filings, today=today, view=view, replaced=replaced, buyer=view['buyer'], supplier=view['incumbent'], link=identity), key)
        elif filings:
            # One late filing says little, so it is watched rather than acted on.
            assessment = assess('supplier_stress', filings, today=today, view=view, replaced=replaced, buyer=view['buyer'], supplier=view['incumbent'], link=identity)
            found[f'stress:{key}'] = ({**assessment, 'decision': 'monitor', 'decision_reasons': ['A single overdue filing is not evidence of difficulty, so this is only watched.']}, key)
    return found


def _link(items: list[dict]) -> str:
    same = sum(1 for x in items if x.get('relation') == 'same_service')
    return f'{same} of {len(items)} signals name the same service as this contract; the rest concern the customer generally.'


def buyer_hypotheses(views: list[dict], observations: list[dict], notices: list[dict], today: date) -> dict:
    """Requirements implied by compliance pressure or new estate, with no live tender."""
    found, grouped = {}, defaultdict(list)
    live = {_buyer_key(x['buyer']) for x in notices if x.get('type') == 'Contract' and x.get('status') == 'Open' and x.get('published')}
    for item in observations:
        if _fresh(item, today) and item['buyer'] and item['signal_type'] in REQUIREMENT_SIGNALS | _CONTRADICTIONS | {'remedial_programme', 'market_engagement', 'false_alarm_rise'}:
            grouped[council_key(item['buyer'])].append(item)
    held = defaultdict(list)
    for view in views:
        held[council_key(view['buyer'])].append(view)
    for key, items in grouped.items():
        # Needs a pressure that creates demand; supporting activity alone is not a requirement.
        if not any(x['signal_type'] in REQUIREMENT_SIGNALS for x in items) or _buyer_key(items[0]['buyer']) in live:
            continue
        opposing = [x for x in items if x['signal_type'] in _CONTRADICTIONS]
        standing, against = apply_contradictions(sorted((x for x in items if x['signal_type'] not in _CONTRADICTIONS), key=lambda x: x['occurred_on']), opposing)
        pressure = any(x['signal_type'] in REQUIREMENT_SIGNALS for x in standing)
        if pressure and any(x['signal_type'] in COMPLIANCE_SIGNALS for x in standing):
            # A fire safety finding is corroborated by fire work, not by a CCTV notice.
            standing = [x for x in standing if x['signal_type'] in REQUIREMENT_SIGNALS or set(x['families']) & FIRE_WORK]
        recent = [x for x in held.get(key, []) if x.get('published') and x['fit'] in {'core', 'bundled', 'adjacent'}]
        # Holding contracts shows the customer buys this work. It is context, not corroboration.
        link = f"Customer level, not tied to one contract. SalesIntel holds {len(recent)} relevant published contracts for this customer."
        name = next((x['buyer'] for x in items if x['signal_type'] in REQUIREMENT_SIGNALS), items[0]['buyer'])
        found[f'requirement:{key}'] = (assess('hidden_requirement', standing if pressure else sorted(items, key=lambda x: x['occurred_on']), today=today, contradicted=[] if pressure else against, estate=[], buyer=name, link=link), None)
    return found


def competitor_hypotheses(views: list[dict], observations: list[dict], today: date) -> dict:
    """Movement by a supplier, from published wins, losses, insolvency and acquisitions."""
    found, wins, ends, losses, notes = {}, defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    names = {}
    for view in views:
        if view['fit'] not in {'core', 'bundled'}:
            continue
        for supplier in view['suppliers'][:4]:
            key = competitor_group(supplier)
            names.setdefault(key, key if key in COMPETITOR_GROUPS else supplier)
            if view.get('published') and (today - _day(view['published'])).days <= COMPETITOR_WIN_DAYS:
                wins[key].append(view)
            if view.get('end') and 0 <= (_day(view['end']) - today).days <= ACT_NOW_TO_DAYS:
                ends[key].append(view)
    for item in observations:
        if not _fresh(item, today) or not item['supplier']:
            continue
        key = competitor_group(item['supplier'])
        if item['signal_type'] == 'supplier_replaced' and (today - item['occurred_on']).days <= COMPETITOR_WIN_DAYS:
            losses[key].append(item)
        elif item['signal_type'] in {'competitor_acquisition', 'control_change', 'supplier_insolvency'}:
            notes[key].append(item)
    for key in sorted(set(wins) | set(losses) | set(notes)):
        name = names.get(key) or next((x['supplier'] for x in notes.get(key, [])), key)
        if OWN_GROUP.search(name):
            continue
        gained = [observation('supplier_replaced', statement=f"{name} is the published supplier on \"{x['title'][:100]}\" for {x['buyer']}.", occurred=_day(x['published']), url=x['url'], group='procurement', reliability='official_notice', buyer=x['buyer'], supplier=name) for x in wins.get(key, [])]
        acquired = [x for x in notes.get(key, []) if x['signal_type'] in {'competitor_acquisition', 'control_change'}]
        insolvent = [x for x in notes.get(key, []) if x['signal_type'] == 'supplier_insolvency']
        if len(gained) >= COMPETITOR_MIN_WINS or acquired:
            found[f'strength:{key}'] = (assess('competitor_strength', sorted(acquired + gained, key=lambda x: x['occurred_on'], reverse=True), today=today, supplier=name, link=f'{len(gained)} published awards in the last year.'), None)
        if insolvent or len(losses.get(key, [])) >= COMPETITOR_MIN_LOSSES:
            found[f'competitive-risk:{key}'] = (assess('competitor_vulnerability', insolvent + losses.get(key, []), today=today, supplier=name, link=f"{len(ends.get(key, []))} of its published contracts end within a year."), None)
    return found


def plausible_competitors(view_title: str, buyer: str, views: list[dict]) -> list[str]:
    """Suppliers with repeated published work of this kind. Plausible, never confirmed."""
    wanted, counts = families(view_title), defaultdict(int)
    for view in views:
        if view['fit'] in {'core', 'bundled'} and families(view['title']) & wanted and len(view['suppliers']) == 1 and not OWN_GROUP.search(view['suppliers'][0]):
            counts[view['suppliers'][0]] += 1
    return [name for name, total in sorted(counts.items(), key=lambda x: -x[1])[:3] if total >= PLAUSIBLE_PURSUIT_MIN]


def assessment_fingerprint(assessment: dict) -> str:
    return hashlib.sha256(json.dumps(assessment, sort_keys=True, default=str).encode()).hexdigest()


