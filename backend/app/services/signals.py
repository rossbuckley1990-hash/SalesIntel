"""Public records that give a reason to ask, before any tender: a regulator's finding, a fire authority's notice, an early
procurement notice, a press report.

One reading of a stored signal, shared by the lead list, Today and the brief, so all three say the same thing. Rules only:
nothing is generated, the stored sentences are shown as they were collected (with dates written for people), and nothing here
is a requirement, a supplier, a value or a contract date.
"""
from __future__ import annotations

import re

from app.services import notice

CATEGORY = 'inferred_signal'
KIND_LABEL = 'Public record, before any tender'
OFFICIAL = {'statutory_record', 'official_notice'}
SOURCE_LABEL = {'regulator': 'Regulator', 'fire_service': 'Fire and rescue authority', 'procurement': 'Procurement notice', 'local_press': 'Press report',
                'gazette': 'The Gazette', 'planning': 'Planning record', 'companies_house': 'Companies House'}
SOURCE_PHRASE = {'regulator': 'Regulator’s finding', 'fire_service': 'Fire authority record', 'procurement': 'Early procurement notice', 'local_press': 'Press report',
                 'gazette': 'Gazette notice', 'planning': 'Planning record', 'companies_house': 'Companies House filing'}
_ABBREVIATION = re.compile(r'\b(?:St|Dr|Mr|Mrs|Ms|Ltd|Co|No|Rd|Ave|Inc|Prof)$')
_QUOTED = re.compile(r':\s*["\u201c](.+?)["\u201d]\s*\.?\s*$')
_SENTENCE_END = re.compile(r'(?<=[a-z0-9"”)])\.\s+(?=[A-Z"“])')


def lead_sentence(text: str) -> tuple[str, str]:
    """The first sentence of a stored statement, and the rest of it. A statement that does not split cleanly is kept whole
    (cut at a word and marked if it is long), with the full text as the rest so nothing is lost."""
    text = (text or '').strip()
    for m in _SENTENCE_END.finditer(text):
        first = text[:m.start()]
        if _ABBREVIATION.search(first) or len(first) < 30:
            continue
        if len(first) <= 220:
            return first, text[m.end():].strip()
        break
    whole = text.rstrip('. ')
    return (whole, '') if len(whole) <= 220 else (notice.clip(whole, 180), text)


def records(s: dict) -> list[dict]:
    """The supporting public records of a stored signal, newest first."""
    sig = s.get('signal') or {}
    found = [x for x in sig.get('supporting') or [] if isinstance(x, dict) and str(x.get('statement') or '').strip()]
    if not found and str(s.get('title') or '').strip():  # a signal stored before the records were kept one by one
        e = next((e for e in s.get('evidence') or [] if isinstance(e, dict)), {})
        found = [{'statement': s['title'], 'occurred_on': e.get('published_at') or '', 'label': e.get('source') or '', 'source_url': e.get('source_url') or '',
                  'source_group': e.get('source_key') or '', 'signal_type': e.get('record_key') or '', 'reliability': ''}]
    return sorted(found, key=lambda x: str(x.get('occurred_on') or '')[:10], reverse=True)


def summary(s: dict) -> dict | None:
    """What a salesperson needs from a signal at a glance: the newest record in one sentence, its date and source, and how much
    evidence stands behind it. None when the signal has no usable record."""
    found = records(s)
    if not found:
        return None
    lead = found[0]
    headline, rest = lead_sentence(notice.readable(lead['statement']))
    groups = sorted({x.get('source_group') for x in found if x.get('source_group')})
    independent = [g for g in (s.get('signal') or {}).get('independent_sources') or [] if g] or groups
    n, group = len(found), lead.get('source_group') or ''
    if n == 1:
        strength = 'One press report so far' if group == 'local_press' else 'One public record so far'
    elif len(independent) > 1:
        strength = f'{n} public records from {len(independent)} independent sources'
    else:
        strength = f'{n} public records, all from one source'
    day = str(lead.get('occurred_on') or '')[:10]
    return {'headline': headline, 'rest': rest, 'date': day, 'source': SOURCE_LABEL.get(group, 'Public record'), 'source_url': lead.get('source_url') or '',
            'official': lead.get('reliability') in OFFICIAL, 'records': n, 'sources': max(len(independent), 1), 'corroborated': len(independent) > 1, 'strength': strength,
            'types': sorted({x.get('signal_type') for x in found if x.get('signal_type')}),
            'why': f"{SOURCE_PHRASE.get(group, 'Public record')}{', ' + notice.readable(day) if day else ''}. {strength}. A reason to ask, not a published requirement."}


def engagement(s: dict) -> dict | None:
    """The buyer's own early notice among the records, if there is one, and what the buyer called the work. It is the one record
    that can be mentioned to the buyer, because the buyer published it."""
    for x in records(s):
        if x.get('signal_type') == 'market_engagement':
            named = _QUOTED.search(notice.readable(x['statement']))
            return {'title': named.group(1).strip() if named else '', 'date': str(x.get('occurred_on') or '')[:10], 'source_url': x.get('source_url') or ''}
    return None
