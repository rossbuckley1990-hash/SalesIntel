"""Deterministic pre-tender leads from published contract end dates.

A lead is a reason to check a buyer's plans, not evidence of a live requirement.
Published end dates omit unrecorded extensions, and a buyer can re-let through a
framework or below a publication threshold without any notice appearing here.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from statistics import median
import re

RULE_VERSION = 'renewal-radar-v2'
MIN_TERM_DAYS = 270
MAX_SUPPLIERS = 4
RELET_GAP_DAYS = 90
MIN_TITLE_OVERLAP = 0.3
SAME_TITLE_OVERLAP = 0.6
SAME_CONTRACT_DAYS = 120
CLOSE_VALUE_SHARE = 0.05
STALE_SIGNAL_DAYS = 180
WINDOW_PAST_DAYS = 90
WINDOW_FUTURE_DAYS = 548
ACT_NOW_FROM_DAYS = 90
ACT_NOW_TO_DAYS = 365
LINK_ORDER = ('possible', 'strong', 'exact')
BUCKET_ORDER = ('act_now', 'plan', 'closing', 'overdue_check', 'relet_seen')
BUCKET_LABELS = {'act_now': 'Act now: ends in 3 to 12 months', 'plan': 'Plan: ends in 12 to 18 months',
                 'closing': 'Closing: ends within 3 months', 'overdue_check': 'Overdue check: end date has passed',
                 'relet_seen': 'Check first: a similar newer notice exists'}
FIT_LABELS = {'core': 'Core', 'bundled': 'Bundled', 'adjacent': 'Adjacent', 'framework': 'Framework'}

FAMILIES = {name: re.compile(pattern, re.I) for name, pattern in {
    'fire_alarm': r'\bfire\s+(?:alarms?|detection)\b|\bfire\s+and\s+(?:intruder|security)\b|\bfire\s*&\s*security\b|\bvoice\s+alarms?\b',
    'emergency_lighting': r'\bemergency\s+light',
    'extinguishers': r'\bextinguishers?\b|\bfire\s+(?:fighting\s+|safety\s+)?equipment\b',
    'sprinklers': r'\bsprinklers?\b|\b(?:dry|wet)\s+risers?\b|\bsuppression\b',
    'smoke_control': r'\bsmoke\s+(?:control|vent\w*|extract\w*)\b|\bfire\s+dampers?\b',
    'cctv': r'\bcctv\b|\bvideo\s+surveillance\b',
    'access_control': r'\baccess\s+control\b|\bdoor\s+entry\b',
    'intruder': r'\bintruder\s+alarms?\b|\bburglar\s+alarms?\b|\balarm\s+(?:monitoring|receiving)\b|\bsecurity\s+(?:systems?|alarms?)\b',
    'passive_fire': r'\bfire\s+doors?\b|\bcompartmentation\b|\bfire\s+stopping\b|\bpassive\s+fire\b',
    'fire_risk_assessment': r'\bfire\s+risk\s+assess\w*\b',
}.items()}
ADJACENT_FAMILIES = {'passive_fire', 'fire_risk_assessment'}
CORE_CPV = {'50413200', '50610000', '79711000'}
_SERVICE = re.compile(r'\b(?:maintenan\w*|servicing|inspect\w*|testing|preventative|ppm|reactive|call[\s-]?outs?|monitoring|repairs?|statutory|compliance)\b', re.I)
_SERVICES = re.compile(r'\bservices?\b', re.I)
_FRAMEWORK = re.compile(r'\bframework\b|\bdynamic\s+purchasing\s+system\b|\bdps\b', re.I)
_FRAMEWORK_STATED = re.compile(r'\bthe\s+above\s+framework\b|\bcurrent\s+framework\s+agreement\b', re.I)
_CANCELLED = re.compile(r'\bthis\s+notice\s+is\s+to\s+cancel\b', re.I)
_FRAMEWORK_BODY = re.compile(r'\bdynamic\s+purchasing\s+system\b|\b(?:establish\w*|create|set\s+up|appoint|procure)\b[^.;\n]{0,60}\bframework\b|\bfor\s+an?\s+[^.;\n]{0,80}\bframework\b', re.I)
_VIA_FRAMEWORK = re.compile(r'\b(?:via|under|through|using|from|off)\b[^.;\n]{0,80}\bframework\b|\bcall[\s-]?off\b|\bdirect\s+award\b|\bfurther\s+competition\b', re.I)
_CALL_OFF = re.compile(r'\bcall[\s-]?off\b|\bmini[\s-]?competition\b', re.I)
_SUPPLY_ONLY = re.compile(r'\bsupply\b[^.;\n]{0,30}\binstall\w*\b', re.I)
_MAINTAINED = re.compile(r'\b(?:maintenan\w*|servic(?:e|ing)\b|support)\b', re.I)
_BUYER_AGENT = re.compile(r'\bon\s+behalf\s+of\b|\bt/a\b|\(', re.I)
_WORKS = re.compile(r'\b(?:replac\w*|remedial|upgrad\w*|install\w*|refurbish\w*|fit[\s-]?out|new\s+build|construction|works?\s+at|supply\s+(?:and|&)\s+fit)\b', re.I)
_NOISE = re.compile(r'\b(?:occupational\s+health|ppe|uniforms?|fleet|vehicles?|drainage|culverts?|sewers?|overhaul|on[\s-]train|rolling\s+stock|guarding|parking|anpr|number\s+plate|bollards?|passenger\s+counting|wi-?fi|intelligent\s+transport|traffic\s+enforcement|enforcement\s+cameras?|mobile\s+cctv|catchment|perimeter\s+wall|certification\s+for|cctv\s+drain\w*|drain\w*\s+(?:cctv|survey\w*)|community\s+alarms?|telecare|key\s+safes?|catering|recruit\w*|insurance|legal|training|night\s+vision|lone\s+worker|payroll|fire\s+(?:engines?|stations?|fighters?|kit|hose|boats?)|breathing\s+apparatus)\b', re.I)
# Another trade's contract: fine when the title also names a fire or security system.
_OTHER_TRADE = re.compile(r'\b(?:lifts?|hvac|heating|boilers?|gas|air\s+conditioning|ventilation|windows?|decorat\w*|roofing|trailers?|drains?|data\s+cent(?:re|er)s?|general\s+building|gates?|barriers?|high\s+mast|street\s+lighting|building\s+services)\b', re.I)
_CARE_ALARM = re.compile(r'\b(?:telecare|careline|lifeline|community\s+alarms?)\b', re.I)
_NO_AWARD = re.compile(r'\b(?:procedure\s+discontinued|not\s+awarded|no\s+award|no\s+suitable|cancelled|unsuccessful)\b', re.I)
_EXTENSION = re.compile(r'\b(?:extensions?|extend(?:ed|able)?|\d\s*\+\s*\d)\b', re.I)
_SUFFIX = re.compile(r'\b(?:limited|ltd|plc|llp|the|nhs|trust|foundation)\b')
OWN_GROUP = re.compile(r'\b(?:mitie|marlowe)\b', re.I)
_TRAILING_ROLE = re.compile(r'\s+primary$', re.I)
_SCOTTISH_POSTCODE = re.compile(r'^(?:AB|DD|DG|EH|FK|G|HS|IV|KA|KW|KY|ML|PA|PH|TD|ZE)\d')
_WELSH_POSTCODE = re.compile(r'^(?:CF|LD|LL|NP|SA)\d')
_ENGLISH_REGION = re.compile(r'NORTH EAST|NORTH WEST|YORKSHIRE|EAST MIDLANDS|WEST MIDLANDS|EAST OF ENGLAND|LONDON|SOUTH EAST|SOUTH WEST')
_TITLE_STOP = {'provision', 'contract', 'service', 'award', 'lot', 'work', 'the', 'and', 'for', 'with', 'all', 'various', 'new', 'term', 'year'}


FRAMEWORK_REASON = 'framework agreement, not an individual contract'


def _day(value):
    return date.fromisoformat(value) if value else None


def nation_of(notice: dict) -> str:
    """The UK nation a notice's address or region names; many name none."""
    if notice.get('source') == 'public_contracts_scotland':
        return 'Scotland'
    region, postcode = (notice.get('region') or '').upper(), (notice.get('postcode') or '').upper()
    if region.startswith('UKM') or 'SCOTLAND' == region or _SCOTTISH_POSTCODE.match(postcode):
        return 'Scotland'
    if region.startswith('UKL') or 'WALES' == region or _WELSH_POSTCODE.match(postcode):
        return 'Wales'
    if region.startswith('UKN') or 'NORTHERN IRELAND' == region or postcode.startswith('BT'):
        return 'Northern Ireland'
    if region.startswith('UK') or postcode or _ENGLISH_REGION.search(region):
        return 'England'
    return 'Not stated'


def clean_supplier(name: str) -> str:
    """Drop the role word some Contracts Finder rows append to a supplier name."""
    return _TRAILING_ROLE.sub('', name).strip()


def families(text: str) -> set[str]:
    return {name for name, pattern in FAMILIES.items() if pattern.search(text)}


def _service_families(text: str) -> set[str]:
    """Families named in the same sentence as a service term."""
    found = set()
    for sentence in re.split(r'[.!?;\n]', text):
        if _SERVICE.search(sentence):
            found |= families(sentence)
    return found


def term_days(notice: dict) -> int | None:
    start, end = _day(notice.get('start')), _day(notice.get('end'))
    return (end - start).days if start and end and end > start else None


def classify(notice: dict) -> tuple[str, str]:
    """Return (fit, reason) from published wording, never from buyer intent."""
    title, body = notice['title'], notice.get('description') or ''
    suppliers = notice.get('suppliers') or []
    if _NOISE.search(title) or (_CARE_ALARM.search(body) and not families(title) - {'intruder'}):
        return 'exclude', 'subject is outside fire and security systems'
    if _OTHER_TRADE.search(title) and not families(title) - ADJACENT_FAMILIES:
        return 'exclude', "another trade's contract"
    if (suppliers and all(_NO_AWARD.search(x) for x in suppliers)) or _CANCELLED.search(body):
        return 'exclude', 'no supplier was appointed'
    if notice.get('framework') or (_FRAMEWORK.search(title) and not _CALL_OFF.search(title)) or _FRAMEWORK_STATED.search(body) or (_FRAMEWORK_BODY.search(body) and not _VIA_FRAMEWORK.search(body)):
        return 'exclude', FRAMEWORK_REASON
    if len(suppliers) > MAX_SUPPLIERS:
        return 'exclude', 'framework-style award to many suppliers'
    term = term_days(notice)
    if term is not None and term < MIN_TERM_DAYS:
        return 'exclude', 'term too short for recurring maintenance'
    in_title = families(title)
    title_service = bool(_SERVICE.search(title))
    if in_title and _WORKS.search(title) and not title_service:
        return 'exclude', 'one-off installation or replacement'
    opening = re.split(r'[.!?;\n]', body)[0]
    if in_title and not title_service and _SUPPLY_ONLY.search(opening) and not _MAINTAINED.search(body):
        return 'exclude', 'one-off installation or replacement'
    active_title = in_title - ADJACENT_FAMILIES
    in_body = _service_families(body)
    if active_title and (title_service or _SERVICES.search(title)):
        return 'core', 'title names both the system and the service'
    if active_title & in_body:
        return 'core', 'title names the system and the description covers its service'
    if title_service and in_body - ADJACENT_FAMILIES:
        return 'bundled', 'fire or security service sits inside wider maintenance'
    if set(notice.get('cpv') or []) & CORE_CPV and (title_service or in_title or in_body):
        return 'bundled', 'coded as fire or security maintenance'
    if _service_families(opening) - ADJACENT_FAMILIES:
        return 'bundled', 'the description opens with the system and its service'
    if (in_title | in_body) & ADJACENT_FAMILIES and (title_service or in_title & ADJACENT_FAMILIES):
        return 'adjacent', 'passive fire or fire risk assessment work'
    return 'exclude', 'no fire or security service evidence'


def _buyer_key(name: str) -> str:
    return ' '.join(_SUFFIX.sub(' ', re.sub(r'[^a-z0-9 ]', ' ', _BUYER_AGENT.split(name)[0].lower())).split())


def _title_tokens(title: str) -> set[str]:
    words = (w[:-1] if w.endswith('s') and len(w) > 3 else w for w in re.findall(r'[a-z]{3,}', title.lower()))
    return {w for w in words if w not in _TITLE_STOP}


def _overlap(first: set[str], second: set[str]) -> float:
    return len(first & second) / len(first | second) if first | second else 0.0


def _index(notices: list[dict]) -> dict:
    grouped = defaultdict(list)
    for notice in notices:
        fit, reason = classify(notice)
        # A buyer can re-let through its own framework, so one can show a replacement.
        if (fit != 'exclude' or reason == FRAMEWORK_REASON) and notice.get('published'):
            grouped[_buyer_key(notice['buyer'])].append((notice, families(notice['title']), _title_tokens(notice['title'])))
    return grouped


def successor(notice: dict, index: dict) -> dict | None:
    """The earliest later notice that appears to replace this contract.

    Buyers run many contracts for one system across different sites, so a false
    match would hide a real lead. Titles must overlap and the newer term must
    outlast this one; a missed re-let only leaves a lead to check.
    """
    wanted, tokens = families(notice['title']), _title_tokens(notice['title'])
    earliest = _day(notice['published']) + timedelta(days=RELET_GAP_DAYS)
    end = _day(notice.get('end'))
    later = []
    for other, covered, other_tokens in index.get(_buyer_key(notice['buyer']), []):
        if other['id'] == notice['id'] or not covered & wanted or _day(other['published']) < earliest:
            continue
        other_end = _day(other.get('end'))
        if end and other_end and other_end < end + timedelta(days=RELET_GAP_DAYS):
            continue
        if _overlap(tokens, other_tokens) >= MIN_TITLE_OVERLAP:
            later.append(other)
    return min(later, key=lambda x: x['published']) if later else None


def bucket(end: date, today: date) -> str | None:
    days = (end - today).days
    if days < -WINDOW_PAST_DAYS or days > WINDOW_FUTURE_DAYS:
        return None
    if days < 0:
        return 'overdue_check'
    if days < ACT_NOW_FROM_DAYS:
        return 'closing'
    return 'act_now' if days <= ACT_NOW_TO_DAYS else 'plan'


def _view(group: list[dict], next_notice: dict | None, today: date) -> dict:
    """One contract as its published records describe it, however they are dated."""
    primary = group[0]
    notice, fit, reason = primary['notice'], primary['fit'], primary['reason']
    end = _day(notice.get('end'))
    timing = bucket(end, today) if end else None
    term = term_days(notice)
    suppliers = notice.get('suppliers') or []
    value = notice.get('value')
    note, latest = notice.get('extension_note') or '', notice.get('latest_end') or ''
    ends = sorted({x['notice']['end'] for x in group if x['notice'].get('end')})
    contradictions = []
    if len(ends) > 1 and (_day(ends[-1]) - _day(ends[0])).days > SAME_CONTRACT_DAYS // 4:
        contradictions.append(f'Linked records give different end dates: {ends[0]} and {ends[-1]}.')
    if notice.get('term_conflict'):
        contradictions.append('The source gives conflicting contract dates.')
    framework = any(x['reason'] == FRAMEWORK_REASON for x in group)
    return {**{k: notice.get(k) for k in ('id', 'url', 'title', 'buyer', 'end', 'value', 'region', 'postcode', 'published', 'ocid', 'start', 'award_date', 'reference',
                                          'route', 'buyer_id', 'description')}, 'lot': notice.get('lot') or '',
            'rule_version': RULE_VERSION, 'bucket': ('relet_seen' if next_notice else timing) if timing else None, 'timing': timing, 'fit': 'framework' if framework else fit,
            'fit_reason': FRAMEWORK_REASON if framework else reason, 'source': notice.get('source') or 'contracts_finder', 'end_estimated': bool(notice.get('end_estimated')),
            'end_basis': notice.get('end_basis') or ('award_contract_period' if notice.get('end') else 'none'), 'incumbent': ', '.join(suppliers), 'suppliers': suppliers,
            'own_group': any(OWN_GROUP.search(x) for x in suppliers), 'company_numbers': notice.get('company_numbers') or [], 'term_days': term,
            'annual_value': round(value / (term / 365.25), 2) if value and term else None, 'framework_stage': notice.get('framework_stage') or '',
            'extension_mentioned': bool(note or latest or notice.get('has_extension') or _EXTENSION.search(notice.get('description') or '')),
            'extension_note': note, 'latest_end': latest, 'latest_end_basis': notice.get('latest_end_basis') or '', 'contradictions': contradictions,
            'members': [{'id': x['notice']['id'], 'ocid': x['notice'].get('ocid') or '', 'lot': x['notice'].get('lot') or '', 'source': x['notice'].get('source') or 'contracts_finder',
                         'url': x['notice'].get('url'), 'method': x.get('method') or 'primary record', 'confidence': x.get('confidence') or 'exact'} for x in group],
            'link_confidence': min((x.get('confidence') or 'exact' for x in group), key=LINK_ORDER.index),
            'successor_title': next_notice['title'] if next_notice else None, 'successor_published': next_notice['published'] if next_notice else None,
            'successor_url': next_notice['url'] if next_notice else None, 'successor_ocid': next_notice.get('ocid') if next_notice else None}


def _supplier_keys(notice: dict) -> set[str]:
    return {_buyer_key(x) for x in notice.get('suppliers') or [] if _buyer_key(x)}


def link_strength(first: dict, second: dict) -> tuple[str, str] | None:
    """How two records from different sources relate; a similar title alone never links them.

    Different named suppliers rule a link out, however close the titles are.
    """
    if first.get('reference') and first.get('reference') == second.get('reference'):
        return 'exact', 'same published procurement reference'
    numbers = set(first.get('company_numbers') or []) & set(second.get('company_numbers') or [])
    same_supplier = bool(numbers or _supplier_keys(first) & _supplier_keys(second))
    if _supplier_keys(first) and _supplier_keys(second) and not same_supplier:
        return None
    end, other_end = _day(first.get('end')), _day(second.get('end'))
    close_end = bool(end and other_end and abs((end - other_end).days) <= SAME_CONTRACT_DAYS)
    overlap = _overlap(_title_tokens(first['title']), _title_tokens(second['title']))
    value, other_value = first.get('value') or 0, second.get('value') or 0
    close_value = bool(value and other_value and abs(value - other_value) <= CLOSE_VALUE_SHARE * max(value, other_value))
    if same_supplier and overlap >= MIN_TITLE_OVERLAP and (close_end or close_value):
        return 'strong', 'same buyer and supplier, with a matching end date or value'
    if close_end and overlap >= SAME_TITLE_OVERLAP:
        return 'possible', 'same buyer, similar title and end date'
    return None


def group_contracts(records: list[dict]) -> list[list[dict]]:
    """Records of one contract together, its best-evidenced record first.

    Repeat rows with an identical title, end date and supplier are one contract.
    Across sources a link needs link_strength, and the group keeps the weakest
    link so a doubtful merge stays visible.
    """
    groups, by_buyer = [], defaultdict(list)
    for record in sorted(records, key=lambda x: (bool(x['notice'].get('end_estimated')), -(x['notice'].get('value') or 0), x['notice']['id'])):
        notice = record['notice']
        match = None
        for group in by_buyer[_buyer_key(notice['buyer'])]:
            lead = group[0]['notice']
            if (lead.get('source') or 'contracts_finder') != (notice.get('source') or 'contracts_finder'):
                strength = link_strength(lead, notice)
                if strength:
                    match = group, *strength
                    break
            # A buyer can award identical lots to different suppliers; those stay separate.
            elif (lead['title'].lower(), lead.get('end')) == (notice['title'].lower(), notice.get('end')) and (
                    _supplier_keys(lead) & _supplier_keys(notice) or not _supplier_keys(lead) or not _supplier_keys(notice)):
                match = group, 'exact', 'identical repeated record'
                break
        if match:
            match[0].append({**record, 'confidence': match[1], 'method': match[2]})
        else:
            group = [record]
            groups.append(group)
            by_buyer[_buyer_key(notice['buyer'])].append(group)
    return groups


def contract_views(notices: list[dict], today: date) -> list[dict]:
    """Every relevant award once, including those no longer in a renewal window."""
    index = _index(notices)
    records = []
    for notice in notices:
        if notice.get('type') != 'Contract' or notice.get('status') != 'Awarded' or not notice.get('published'):
            continue
        fit, reason = classify(notice)
        if fit != 'exclude' or (reason == FRAMEWORK_REASON and families(notice['title'])):
            records.append({'notice': notice, 'fit': fit, 'reason': reason})
    views = []
    for group in group_contracts(records):
        notice = group[0]['notice']
        views.append(_view(group, successor(notice, index) if notice.get('end') else None, today))
    return views


def renewal_leads(notices: list[dict], today: date) -> list[dict]:
    """One lead per contract, most actionable first, largest annual value next."""
    leads = [x for x in contract_views(notices, today) if x['bucket'] and x['fit'] != 'framework']
    return sorted(leads, key=lambda x: (BUCKET_ORDER.index(x['bucket']), -(x['annual_value'] or 0), x['end']))


def early_signals(notices: list[dict], today: date, *, max_age_days: int = 548) -> list[dict]:
    """Official pipeline and planning notices that have not reached a tender."""
    advanced = {x['ocid'] for x in notices if x.get('ocid') and x.get('type') == 'Contract'}
    leads = {}
    for notice in notices:
        published = _day(notice.get('published'))
        if notice.get('type') not in {'Pipeline', 'PreProcurement'} or not published or published < today - timedelta(days=max_age_days):
            continue
        end, expected = _day(notice.get('end')), _day(notice.get('approach'))
        fit, reason = classify({**notice, 'start': None})
        if reason == FRAMEWORK_REASON and families(notice['title']):
            fit = 'framework'
        if fit == 'exclude' or notice.get('status') == 'Withdrawn' or notice.get('ocid') in advanced or (end and end < today):
            continue
        # A missing date is not a deadline, so an undated notice must be recent.
        if expected and expected < today - timedelta(days=STALE_SIGNAL_DAYS) or (not expected and published < today - timedelta(days=STALE_SIGNAL_DAYS)):
            continue
        key = (_buyer_key(notice['buyer']), notice['title'].lower())
        leads[key] = {**{k: notice.get(k) for k in ('id', 'url', 'title', 'buyer', 'type', 'published', 'end', 'region', 'ocid', 'value', 'description')},
                      'source': notice.get('source') or 'contracts_finder', 'expected_tender': notice.get('approach') or '',
                      'rule_version': RULE_VERSION, 'fit': fit, 'fit_reason': reason}
    return sorted(leads.values(), key=lambda x: x['published'], reverse=True)


def backtest(notices: list[dict], today: date, *, lookback_days: int = 730, settled_days: int = 180) -> dict:
    """How often a past end date was followed by a visible new notice.

    A lower bound: re-lets through frameworks, below threshold or under another
    buyer name stay invisible, and only contracts ended long enough ago count.
    Lead time uses only the date a replacement went to market, because an award
    notice is published after the tender it follows.
    """
    index = _index(notices)
    seen, matched, lead_days = set(), 0, []
    for notice in notices:
        end = _day(notice.get('end'))
        if notice.get('type') != 'Contract' or notice.get('status') != 'Awarded' or not end or not notice.get('published'):
            continue
        if not today - timedelta(days=lookback_days) <= end <= today - timedelta(days=settled_days) or classify(notice)[0] != 'core':
            continue
        key = (_buyer_key(notice['buyer']), notice['title'].lower(), notice['end'])
        if key in seen:
            continue
        seen.add(key)
        next_notice = successor(notice, index)
        if next_notice is None or _day(next_notice['published']) > end + timedelta(days=settled_days):
            continue
        matched += 1
        if next_notice.get('approach'):
            lead_days.append((end - _day(next_notice['approach'])).days)
    return {'contracts': len(seen), 'with_visible_successor': matched,
            'share': round(matched / len(seen), 3) if seen else None,
            'median_days_before_end': median(lead_days) if lead_days else None, 'timed_replacements': len(lead_days),
            'sample_is_lower_bound': True}
