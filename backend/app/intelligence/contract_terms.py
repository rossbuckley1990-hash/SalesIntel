"""One reading of a published contract term, shared by every renewal rule.

Sources publish the term in different places: Find a Tender in contracts[].period
or awards[].contractPeriod, Contracts Finder only in awards[].contractPeriod, and
Public Contracts Scotland's award notices not at all. Only a date the source gives
for this award is a published end. A tender's planned date, a duration added to a
start date and a term stated in wording are estimates and stay labelled as such.
No date here shows whether a contract is still being delivered.
"""
from __future__ import annotations
from calendar import monthrange
from datetime import date, datetime, timedelta
import re

PUBLISHED_BASES = {'contract_period', 'award_contract_period'}
BASIS_LABELS = {'contract_period': 'published contract end date', 'award_contract_period': 'published award contract period',
                'published_duration': 'published duration added to the start date', 'tender_planned_end': 'end date planned in the tender notice',
                'tender_duration': 'tender notice duration added to the start date', 'stated_term': 'term stated in the notice wording added to the start date',
                'none': 'no term published'}
MIN_STATED_MONTHS, MAX_STATED_MONTHS = 6, 180
_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'twelve': 12}
_NUMBER = r'(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|twelve)'
_UNIT = r'(years?|yrs?|months?)'
_TERM_BEFORE = re.compile(rf'\b(?:contract|term|period|duration)\b[^.;\n]{{0,60}}?\b{_NUMBER}(?:\s*\(\s*\d+\s*\))?[\s-]*{_UNIT}\b', re.I)
_TERM_AFTER = re.compile(rf'\b{_NUMBER}(?:\s*\(\s*\d+\s*\))?[\s-]*{_UNIT}\b[^.;\n]{{0,30}}?\b(?:contract|term|period)\b', re.I)
_PLUS = re.compile(r'\b(\d{1,2})\s*\+\s*(\d{1,2})(?:\s*\+\s*(\d{1,2}))?\s*(?:years?|yrs?)\b', re.I)
_EXTEND = re.compile(rf'\b(?:extend\w*|extension\w*)\b[^.;\n]{{0,60}}?\b{_NUMBER}(?:\s*\(\s*\d+\s*\))?[\s-]*(?:further\s+|additional\s+)?{_UNIT}\b', re.I)
_EXTENSION_SENTENCE = re.compile(r'[^.;\n]*\b(?:extensions?|extend(?:ed|able)?)\b[^.;\n]*', re.I)
_CALL_OFF = re.compile(r'\bcall[\s-]?off\b|\bmini[\s-]?competition\b|\b(?:via|under|through|using|from)\b[^.;\n]{0,60}\bframework\b', re.I)


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def iso_day(value) -> str:
    """YYYY-MM-DD for a valid date, otherwise an empty string."""
    if isinstance(value, date):
        return value.isoformat()[:10]
    if not isinstance(value, str) or not value.strip():
        return ''
    try:
        return datetime.fromisoformat(value.strip().replace('Z', '+00:00')).date().isoformat()
    except ValueError:
        return ''


def _add_months(day: date, months: int) -> date:
    total = day.month - 1 + months
    year, month = day.year + total // 12, total % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def _months(number: str, unit: str) -> int:
    count = _WORDS.get(number.lower()) or int(number)
    return count if unit.lower().startswith('month') else count * 12


def _bounded(months: int | None) -> int | None:
    return months if months and MIN_STATED_MONTHS <= months <= MAX_STATED_MONTHS else None


def stated_term_months(text: str) -> int | None:
    """The initial term a notice states in words, or None when it does not."""
    text = text or ''
    plus = _PLUS.search(text)
    if plus:
        return _bounded(int(plus.group(1)) * 12)
    match = _TERM_BEFORE.search(text) or _TERM_AFTER.search(text)
    return _bounded(_months(*match.groups())) if match else None


def extension_months(text: str) -> int | None:
    """Optional extra months a notice states in words, or None when it does not."""
    text = text or ''
    plus = _PLUS.search(text)
    if plus:
        return _bounded(sum(int(x) for x in plus.groups()[1:] if x) * 12)
    match = _EXTEND.search(text)
    return _bounded(_months(*match.groups())) if match else None


def framework_stage(release: dict) -> tuple[str | None, str | None]:
    """(stage, evidence path); a stage read from wording is a weaker signal than a flag."""
    tender = _dict(release.get('tender'))
    first = _dict(tender.get('techniques')).get('hasFrameworkAgreement') is True
    second = any('framework' in _list(_dict(x).get('relationship')) for x in _list(release.get('relatedProcesses')))
    if first and second:
        return 'conflicting_framework_flags', 'tender.techniques.hasFrameworkAgreement'
    if first:
        return 'framework_first_stage', 'tender.techniques.hasFrameworkAgreement'
    if second:
        return 'framework_second_stage', 'relatedProcesses.relationship'
    details = tender.get('procurementMethodDetails')
    if isinstance(details, str) and _CALL_OFF.search(details):
        return 'framework_second_stage', 'tender.procurementMethodDetails'
    description = tender.get('description')
    if isinstance(description, str) and _CALL_OFF.search(description):
        return 'framework_second_stage', 'tender.description'
    return None, None


def lot_for_award(release: dict, award: dict) -> dict:
    """The tender lot an award names, or the only lot when there is just one."""
    lots = [_dict(x) for x in _list(_dict(release.get('tender')).get('lots'))]
    related = [str(x) for x in _list(award.get('relatedLots'))]
    named = [x for x in lots if str(x.get('id')) in related]
    if named:
        return named[0]
    return lots[0] if len(lots) == 1 else {}


def _wording(release: dict, lot: dict) -> str:
    tender = _dict(release.get('tender'))
    return ' '.join(x for x in (tender.get('description'), lot.get('description')) if isinstance(x, str))


def _extension(release: dict, lot: dict) -> tuple[str, bool]:
    renewal, options = _dict(lot.get('renewal')), _dict(lot.get('options'))
    note = next((x for x in (renewal.get('description'), options.get('description')) if isinstance(x, str) and x.strip()), '')
    if not note:
        sentence = _EXTENSION_SENTENCE.search(_wording(release, lot))
        note = sentence.group(0) if sentence else ''
    flagged = lot.get('hasRenewal') is True or bool(note)
    return ' '.join(note.split())[:300], flagged


def award_term(release: dict, award: dict, contract: dict | None = None) -> dict:
    """The term of one award; 'end' holds a published date and nothing else."""
    tender, contract, lot = _dict(release.get('tender')), _dict(contract), lot_for_award(release, award)
    contract_period, award_period = _dict(contract.get('period')), _dict(award.get('contractPeriod'))
    lot_period, tender_period = _dict(lot.get('contractPeriod')), _dict(tender.get('contractPeriod'))
    term = {'start': '', 'start_basis': '', 'end': '', 'estimated_end': '', 'end_basis': 'none', 'end_estimated': False,
            'latest_end': '', 'latest_end_basis': '', 'duration_days': None, 'extension_note': '', 'has_extension': False, 'conflict': False}
    published_start = next((x for x in map(iso_day, (contract_period.get('startDate'), award_period.get('startDate'))) if x), '')
    planned_start = next((x for x in map(iso_day, (lot_period.get('startDate'), tender_period.get('startDate'))) if x), '')
    signed, awarded = iso_day(contract.get('dateSigned')), iso_day(award.get('date'))
    term['start'] = published_start or planned_start or signed or awarded
    term['start_basis'] = 'published_start' if published_start else 'planned_start' if planned_start else 'signature_date' if signed else 'award_date' if awarded else ''
    start = date.fromisoformat(term['start']) if term['start'] else None
    first, second = iso_day(contract_period.get('endDate')), iso_day(award_period.get('endDate'))
    term['conflict'] = bool(first and second and first != second)
    term['end'], term['end_basis'] = (first, 'contract_period') if first else (second, 'award_contract_period') if second else ('', 'none')
    if term['end'] and start and date.fromisoformat(term['end']) <= start:
        term.update(end='', end_basis='none', conflict=True)
    if not term['end']:
        published_days = next((x for x in (contract_period.get('durationInDays'), award_period.get('durationInDays')) if isinstance(x, int) and x > 0), None)
        planned_end = next((x for x in map(iso_day, (lot_period.get('endDate'), tender_period.get('endDate'))) if x), '')
        planned_days = next((x for x in (lot_period.get('durationInDays'), tender_period.get('durationInDays')) if isinstance(x, int) and x > 0), None)
        stated = stated_term_months(_wording(release, lot))
        if published_days and start:
            term.update(estimated_end=(start + timedelta(days=published_days)).isoformat(), end_basis='published_duration', duration_days=published_days)
        elif planned_end and (not start or date.fromisoformat(planned_end) > start):
            term.update(estimated_end=planned_end, end_basis='tender_planned_end')
        elif planned_days and start:
            term.update(estimated_end=(start + timedelta(days=planned_days)).isoformat(), end_basis='tender_duration', duration_days=planned_days)
        elif stated and start:
            term.update(estimated_end=_add_months(start, stated).isoformat(), end_basis='stated_term', duration_days=stated * 30)
        term['end_estimated'] = bool(term['estimated_end'])
    term['extension_note'], term['has_extension'] = _extension(release, lot)
    latest = next((x for x in map(iso_day, (contract_period.get('maxExtentDate'), award_period.get('maxExtentDate'), lot_period.get('maxExtentDate'))) if x), '')
    term['latest_end'], term['latest_end_basis'] = (latest, 'published_max_extent') if latest else ('', '')
    months = extension_months(' '.join((term['extension_note'], _wording(release, lot))))
    known_end = term['end'] or term['estimated_end']
    if not latest and months and known_end:
        term['latest_end'] = _add_months(date.fromisoformat(known_end), months).isoformat()
        term['latest_end_basis'], term['has_extension'] = 'extension_wording', True
    return term
