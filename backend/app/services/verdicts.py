"""A rep's one-tap verdict on a lead: "Didn't know, worth a call", "Knew already" or "Wrong".

The measure of whether SalesIntel is worth paying for is how many judged leads are marked "Didn't know, worth a call". Each
verdict is stored with the evidence that was on screen when it was given, so the measure can be checked later against what
the rep actually saw.

- A verdict never changes the order of any list. "Wrong" dismisses the lead, and taking it back restores it. That is all.
- Verdicts are appended, never edited: the latest one for a lead and a rep counts, and the history stays.
- Counts are reported as "3 of 7", never as a rate on its own: a handful of taps is not a statistic.
- They live in the existing judgement table (si_lead_feedback), so there is no schema change.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shadow import LeadFeedback, ShadowHypothesis
from app.services import brief
from app.services import si_core as core

VERDICTS = {'worth_a_call': "Didn't know, worth a call", 'knew_already': 'Knew already', 'wrong': 'Wrong'}
CLEARED = 'cleared'  # a verdict taken back: the lead is unjudged again, and the earlier tap stays on record
LEAD = re.compile(r'^(mo|pr|sh):\d+$')


def lead_of(b: dict) -> str | None:
    """The lead a brief was built from. A verdict follows the lead, whether it is given from the list or from its account."""
    key = b.get('source_key') or b.get('key') or ''
    return key if LEAD.match(key) else None


def _shown(b: dict, rep: str) -> dict:
    """What was on screen when the verdict was given: the claim, why it was said to matter, the next move and each dated record."""
    r = b['reveal']
    return {'rep': rep, 'kind': b['kind'], 'kind_label': b['kind_label'], 'organisation': b['organisation'].get('name') or '', 'headline': r['headline'],
            'detail': (r.get('happened') or {}).get('detail') or '', 'why': r['why'], 'next': b['next']['label'],
            'evidence': [{'date': e['date'], 'title': e['title'], 'basis': e['basis'], 'effect': e['effect'], 'url': (e.get('source') or {}).get('url') or ''}
                         for e in b['evidence'][:12]]}


def _note(row: LeadFeedback) -> dict:
    try:
        found = json.loads(row.note or '{}')
    except ValueError:
        return {}
    return found if isinstance(found, dict) else {}


def _latest(db: Session) -> dict[tuple[str, str], LeadFeedback]:
    """The verdict that counts for each lead and rep: the last one given."""
    out: dict[tuple[str, str], LeadFeedback] = {}
    for row in db.scalars(select(LeadFeedback).where(LeadFeedback.decision.in_([*VERDICTS, CLEARED])).order_by(LeadFeedback.id)):
        out[(row.lead_key, str(_note(row).get('rep') or ''))] = row
    return out


def _view(row: LeadFeedback | None) -> dict | None:
    if row is None or row.decision == CLEARED:
        return None
    at = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
    return {'value': row.decision, 'label': VERDICTS[row.decision], 'at': at.isoformat(), 'rep': str(_note(row).get('rep') or '')}


def current(db: Session, lead: str | None, rep: str = '') -> dict | None:
    return _view(_latest(db).get((lead, rep))) if lead else None


def judged(db: Session, rep: str = '') -> dict[str, str]:
    """Every lead this rep has a standing verdict on, and what it is."""
    return {lead: row.decision for (lead, who), row in _latest(db).items() if who == rep and row.decision != CLEARED}


def record(db: Session, key: str, verdict: str, *, rep: str = '', user_id: int | None = None, now: datetime | None = None) -> dict | None:
    if verdict not in VERDICTS and verdict != CLEARED:
        raise ValueError('Choose one of the three verdicts.')
    b = brief.build(db, key)
    lead = lead_of(b)
    if lead is None:
        raise ValueError('Only a lead can be judged: this record did not come from one.')
    rep = rep.strip()[:60]
    before = current(db, lead, rep)
    sensor = b['kind']
    if lead.startswith('sh:') and (row := db.get(ShadowHypothesis, int(lead[3:]))):
        sensor = row.sensor  # Shadow Radar's own scorecard groups judgements by the sensor that raised the lead
    db.add(LeadFeedback(lead_key=lead, sensor=sensor[:40], decision=verdict, reason='', note=json.dumps(_shown(b, rep), ensure_ascii=False),
                        created_by=user_id, created_at=now or datetime.now(UTC)))
    db.flush()
    if verdict == 'wrong':
        core.set_status(db, lead, 'dismissed')  # a lead that is wrong should not be shown again
    elif before and before['value'] == 'wrong':
        core.set_status(db, lead, 'new')  # taking "Wrong" back brings the lead back
    return current(db, lead, rep)


def _tally(rows: list[LeadFeedback]) -> dict:
    counts = {v: sum(1 for r in rows if r.decision == v) for v in VERDICTS}
    return {'judged': len(rows), **counts}


def summary(db: Session, rep: str | None = None) -> dict:
    """How many judged leads were marked each way, in total, by kind of lead and by rep. `rep` narrows it to one rep."""
    standing = [(who, row) for (_lead, who), row in _latest(db).items() if row.decision != CLEARED and (rep is None or who == rep)]
    rows = [row for _who, row in standing]
    total = _tally(rows)
    kinds: dict[str, dict] = {}
    for row in rows:
        shown = _note(row)
        kind = str(shown.get('kind') or row.sensor or 'lead')
        kinds.setdefault(kind, {'kind': kind, 'label': str(shown.get('kind_label') or kind.replace('_', ' ').capitalize()), 'rows': []})['rows'].append(row)
    reps: dict[str, list[LeadFeedback]] = {}
    for who, row in standing:
        reps.setdefault(who, []).append(row)
    recent = sorted(rows, key=lambda r: r.id, reverse=True)[:10]
    return {**total,
            'headline': f"{total['worth_a_call']} of {total['judged']} judged lead{'' if total['judged'] == 1 else 's'}: didn’t know, worth a call" if rows else '',
            'by_kind': sorted(({'kind': k['kind'], 'label': k['label'], **_tally(k['rows'])} for k in kinds.values()), key=lambda x: (-x['judged'], x['label'])),
            'by_rep': sorted(({'rep': who, **_tally(found)} for who, found in reps.items()), key=lambda x: (-x['judged'], x['rep'])),
            'recent': [{'key': r.lead_key, 'organisation': _note(r).get('organisation') or '', 'headline': _note(r).get('headline') or '', **(_view(r) or {})} for r in recent]}
