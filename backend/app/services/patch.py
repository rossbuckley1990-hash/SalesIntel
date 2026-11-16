"""The patch brief: five leads for one rep's patch, from records already held.

It is the first thing a rep sees and the thing the owner sends them. No typing, no paid call, nothing predicted.

- A rep is a name, a patch (regions), disciplines, sectors and target accounts, kept with the workspace's preferences.
- The five are chosen by a fixed rule that is shown on the page, never by a score: named target accounts, then leads resting
  on two or more independent records, then the deadlines closing soonest, then the largest contracts reaching a published end.
  Inside each step the order is a published fact (a date or a value). The list in Discover keeps its own order.
- Each lead carries its evidence chain: dated records, oldest first, each labelled Published (a source states it, and the
  link opens it) or Inferred (SalesIntel's reading). Nothing is invented to fill a gap: a lead with one record shows one.
- A lead the rep has already judged leaves the five, so the brief moves on to the next ones.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm import Preference
from app.services import brief, notice, signals, verdicts
from app.services import si_core as core

SIZE = 5
REGIONS = ('North East', 'North West', 'Yorkshire and the Humber', 'East Midlands', 'West Midlands', 'East of England', 'London', 'South East', 'South West',
           'Scotland', 'Wales', 'Northern Ireland')
_REGION_WORDS = {'yorkshire': 'Yorkshire and the Humber', 'humber': 'Yorkshire and the Humber', 'east anglia': 'East of England'}
# A sector read from the organisation's own name or the sector a source states. It is a filter, never a claim about the organisation.
SECTORS = {'Housing': r'housing|homes\b|\bliving\b|landlord|almshouse', 'Health': r'\bnhs\b|hospital|health|care\b|clinic|ambulance',
           'Education': r'universit|college|school|academy|education', 'Local government': r'council|borough|\bcity of\b|combined authority',
           'Central government': r'ministry|department for|department of|\bhm\b|agency|home office|government', 'Emergency services': r'police|fire and rescue|fire service|constabulary',
           'Transport': r'transport|rail|airport|\bport\b|harbour|highways|\btfl\b', 'Retail and logistics': r'retail|logistic|parcel|warehouse|distribution|supermarket|shopping',
           'Commercial property': r'propert|estate|developer|construction|data centre|hotel|leisure'}
RULE = ['Target accounts you named, wherever they are.',
        'Then leads that rest on two or more independent sources: the most sources first, then the newest record.',
        'Then tenders and early notices with a published deadline still ahead, the soonest first.',
        'Then contracts reaching a published end within twelve months, the largest published value first.',
        'If that leaves fewer than five, the next leads in your patch fill the brief.',
        'Leads you have already judged, and leads outside your patch, disciplines or sectors, are left out.']
REASON = {'target': 'A target account you named', 'two_records': 'Two or more independent records', 'closing': 'A published deadline still ahead',
          'ending': 'A published contract end within twelve months', 'next': 'Next in the list for your patch'}


# ---------------------------------------------------------------- reps

def _pref(db: Session, key: str, default):
    row = db.scalar(select(Preference).where(Preference.key == key))
    return default if row is None or row.value is None else row.value


def _save(db: Session, key: str, value) -> None:
    row = db.scalar(select(Preference).where(Preference.key == key))
    if row is None:
        db.add(Preference(key=key, value=value))
    else:
        row.value = value
    db.flush()


def _clean(values, allowed=None, limit: int = 12) -> list[str]:
    out = []
    for v in values or []:
        v = re.sub(r'\s+', ' ', str(v)).strip()[:80]
        if v and v not in out and (allowed is None or v in allowed):
            out.append(v)
    return out[:limit]


def reps(db: Session) -> dict:
    found = [r for r in _pref(db, 'reps', []) if isinstance(r, dict) and r.get('name')]
    active = _pref(db, 'active_rep', '')
    return {'reps': found, 'active': active if any(r['name'] == active for r in found) else (found[0]['name'] if found else '')}


def save_rep(db: Session, profile: dict, *, active: bool = True) -> dict:
    name = re.sub(r'\s+', ' ', str(profile.get('name') or '')).strip()[:60]
    if not name:
        raise ValueError('Give the rep a name.')
    rep = {'name': name, 'regions': _clean(profile.get('regions'), REGIONS), 'services': _clean(profile.get('services')),
           'sectors': _clean(profile.get('sectors'), SECTORS), 'targets': _clean(profile.get('targets'), limit=25)}
    found = [r for r in reps(db)['reps'] if r['name'] != name]
    if len(found) >= 25:
        raise ValueError('Twenty-five reps are kept at most. Remove one first.')
    _save(db, 'reps', [*found, rep])
    if active:
        _save(db, 'active_rep', name)
    return rep


def remove_rep(db: Session, name: str) -> None:
    _save(db, 'reps', [r for r in reps(db)['reps'] if r['name'] != name])


def choose_rep(db: Session, name: str) -> None:
    if not any(r['name'] == name for r in reps(db)['reps']):
        raise LookupError('Rep not found')
    _save(db, 'active_rep', name)


def rep_named(db: Session, name: str | None) -> dict | None:
    state = reps(db)
    wanted = name or state['active']
    return next((r for r in state['reps'] if r['name'] == wanted), None)


# ---------------------------------------------------------------- where a lead is, and what it is

def region_of(item: dict) -> str:
    """The region or nation a lead is in, as its own notice or research states it. Empty when nothing states one."""
    place = ((item.get('facts') or {}).get('place') or '') if item['type'] == 'public' else (item.get('region') or '')
    text = f"{place} {item.get('region') or ''}".lower()
    for region in REGIONS:
        if region.lower() in text:
            return region
    for word, region in _REGION_WORDS.items():
        if word in text:
            return region
    nation = item.get('nation') or ''
    return nation if nation in ('Scotland', 'Wales', 'Northern Ireland') else ''


def regions_of(item: dict) -> set[str]:
    """Every region a lead touches: research on a company with several sites names several places."""
    text = f"{(item.get('facts') or {}).get('place') or ''} {item.get('region') or ''}".lower()
    found = {r for r in REGIONS if r.lower() in text} | {r for w, r in _REGION_WORDS.items() if w in text}
    return found or ({region_of(item)} - {''})


def sector_of(item: dict) -> str:
    text = f"{item.get('organisation') or ''} {item.get('sector') or ''}".lower()
    return next((name for name, words in SECTORS.items() if re.search(words, text)), '')


def _is_target(item: dict, rep: dict) -> bool:
    name = core.name_key(item.get('organisation') or '')
    return bool(name) and any((key := core.name_key(t)) and (key in name or name in key) for t in rep.get('targets') or [])


def two_records(item: dict) -> int:
    """How many independent sources a lead rests on, when it is more than one: the public record's own count for a signal;
    for research, the separate sites that state a dated fact. Otherwise 0."""
    if item.get('signal'):
        return item['signal']['sources'] if item['signal']['corroborated'] else 0
    dated = [s for s in item.get('sourced_signals') or [] if s.get('date') and s.get('source_url')]
    sites = {urlparse(s['source_url']).netloc.removeprefix('www.') for s in dated}
    return len(sites) if len(dated) >= 2 and len(sites) >= 2 else 0


def fits(item: dict, rep: dict) -> bool:
    """Inside the rep's patch, disciplines and sectors. A target account always fits. What is not stated is not held against a
    lead for disciplines (most notices name none in their title), but a patch or a sector the rep chose has to be stated."""
    if _is_target(item, rep):
        return True
    if rep.get('regions') and not (regions_of(item) & set(rep['regions'])):
        return False
    if rep.get('services') and item.get('services') and not (set(item['services']) & set(rep['services'])):
        return False
    return not rep.get('sectors') or sector_of(item) in rep['sectors']


# ---------------------------------------------------------------- the five

def choose(items: list[dict], rep: dict, judged: set[str], size: int = SIZE) -> tuple[list[tuple[str, dict]], dict]:
    """The leads for the brief, each with the step of the rule that chose it, and how many leads each step had to choose from."""
    pool = [x for x in items if x['status'] != 'dismissed' and x['key'] not in judged and fits(x, rep)]
    steps = {
        'target': [x for x in pool if _is_target(x, rep)],
        'two_records': sorted(sorted((x for x in pool if two_records(x)), key=_newest, reverse=True), key=lambda x: -two_records(x)),
        'closing': sorted((x for x in pool if x['type'] == 'public' and x['category'] in ('live_procurement', 'official_early_signal') and _deadline(x) is not None), key=_deadline),
        'ending': sorted((x for x in pool if x['type'] == 'public' and x['category'] in ('pre_tender', 'contract_defence') and x.get('days') is not None and 0 <= x['days'] <= 365
                          and (x.get('worth') or {}).get('kind') == 'published_total'), key=lambda x: -x['worth']['amount']),
        'next': pool,
    }
    limits = {'target': 2, 'two_records': 2, 'closing': 2, 'ending': size, 'next': size}
    chosen: list[tuple[str, dict]] = []
    taken: set[str] = set()
    for step, found in steps.items():
        n = 0
        for x in found:
            if len(chosen) >= size or n >= limits[step]:
                break
            if x['key'] not in taken:
                chosen.append((step, x)); taken.add(x['key']); n += 1
    held = sum(1 for x in items if x['status'] != 'dismissed' and fits(x, rep))  # with the ones already judged
    counts = {'in_patch': len(pool), 'held': held, **{step: len(found) for step, found in steps.items() if step != 'next'}}
    return chosen, counts


def _newest(x: dict) -> str:
    """The date of a lead's newest dated record, for "newest first" among leads with the same number of sources."""
    if x.get('signal'):
        return x['signal'].get('date') or ''
    return max((s.get('date') or '' for s in x.get('sourced_signals') or []), default='') or x.get('published') or ''


def _deadline(x: dict) -> int | None:
    due = (x.get('facts') or {}).get('deadline')
    if due and due.get('days') is not None and due['days'] >= 0:
        return due['days']
    return x['days'] if x['category'] == 'live_procurement' and x.get('days') is not None and x['days'] >= 0 else None


# ---------------------------------------------------------------- the evidence chain

def _say(kind: str, e: dict) -> str:
    title, detail = e['title'], e['detail']
    if detail and kind == 'public_signal':
        return signals.lead_sentence(detail)[0]  # the record's own sentence, not the label of the kind of record
    if detail and title.endswith('published'):
        return f'{title}: {detail}'
    return title or detail


def chain(b: dict, why_now: str = '') -> list[dict]:
    """The dated records behind a lead, oldest first, and then SalesIntel's reading of them. Each record is Published (a source
    states it; the link opens that source) or Inferred. A record with no link of its own, such as a deadline read from a notice,
    opens the notice it was read from."""
    events = sorted((e for e in b['evidence'] if e['date_kind'] != 'first_seen' and e['effect'] != 'weakens' and e['date'] and (e['title'] or e['detail'])),
                    key=lambda e: e['date'])
    notice_url = next(((e['source'] or {}).get('url') for e in b['evidence'] if e['source'] and e['basis'] == 'published'), '') or ''
    if len(events) > 3:  # where it began, the latest thing that has happened, and the next dated thing ahead
        today = core.uk_today().isoformat()
        past, ahead = [e for e in events if e['date'] <= today], [e for e in events if e['date'] > today]
        events = ([past[0], past[-1]] if len(past) > 1 else past) + ahead[:1] if ahead else [events[0], *events[-2:]]
    links = []
    for e in events:
        url = (e['source'] or {}).get('url') or (notice_url if e['basis'] == 'published' else '')
        links.append({'date': e['date'], 'text': notice.clip(_say(b['kind'], e), 150), 'url': url, 'label': 'Published' if url and e['basis'] in ('published', 'stated') else 'Inferred'})
    if b['kind'] != 'public_tender':  # a tender needs no reading: the requirement and the deadline are published
        why = b['reveal']['why']
        # the sentence that says why it is a reason to act; the timing is already said once, in "Why now"
        reading = next((s for s in re.split(r'(?<=\.)\s+', why) if 'reason to' in s), '') or signals.lead_sentence(why)[0]
        if reading:
            links.append({'date': '', 'text': notice.clip(reading.rstrip('.'), 190), 'url': '', 'label': 'Inferred'})
    return links


def card(db: Session, step: str, item: dict, rep_name: str) -> dict:
    b = brief.build(db, item['key'])
    facts = item.get('facts') or {}
    return {'key': item['key'], 'organisation': item['organisation'], 'kind': b['kind'], 'kind_label': b['kind_label'], 'chosen': step, 'chosen_because': REASON[step],
            'headline': b['reveal']['headline'], 'why_now': item['why_now'], 'chain': chain(b, item['why_now']),
            'against': sum(1 for e in b['evidence'] if e['effect'] == 'weakens'),
            'next': {'action': b['next']['action'], 'label': notice.clip(b['next']['label'], 90), 'url': str((b['next'].get('params') or {}).get('url') or '')},
            'region': region_of(item), 'place': facts.get('place') or item.get('region') or '', 'worth': (item.get('worth') or {}).get('label') or '',
            'deadline': facts.get('deadline'), 'sources': two_records(item), 'account_id': item.get('account_id'), 'verdict': verdicts.current(db, item['key'], rep_name)}


def view(db: Session, rep_name: str | None = None) -> dict:
    """The brief for one rep (the active one unless named). With no rep yet, the brief covers the whole record, so there is
    something to read before anything is set up."""
    state = reps(db)
    rep = rep_named(db, rep_name) or {'name': '', 'regions': [], 'services': [], 'sectors': [], 'targets': []}
    items = core.discover_items(db, limit=None)
    said = verdicts.judged(db, rep['name'])
    chosen, counts = choose(items, rep, set(said))
    held = [x for x in items if x['status'] != 'dismissed']
    # What the rep said was worth a call stays in reach until it has been acted on: a verdict is the start of the work, not the end.
    calls = [{'key': x['key'], 'organisation': x['organisation'], 'why_now': x['why_now'], 'account_id': x.get('account_id')}
             for x in held if said.get(x['key']) == 'worth_a_call'][:8]
    by_region = {r: sum(1 for x in held if r in regions_of(x)) for r in REGIONS}
    v = {'rep': rep, 'reps': state['reps'], 'active': state['active'], 'leads': [card(db, step, x, rep['name']) for step, x in chosen], 'counts': counts, 'calls': calls,
         'rule': RULE, 'said': verdicts.summary(db, rep['name']), 'as_of': core.uk_today().isoformat(),
         'options': {'regions': [{'name': r, 'leads': by_region[r]} for r in REGIONS], 'sectors': list(SECTORS)}}
    return {**v, 'text': text_of(v)}


# ---------------------------------------------------------------- the brief as text, for the owner to send

def text(db: Session, rep_name: str | None = None) -> str:
    return view(db, rep_name)['text']


def text_of(v: dict) -> str:
    """The same five as plain text, to paste into an email. SalesIntel sends nothing: the owner does."""
    who = v['rep']['name']
    lines = [f"SalesIntel patch brief{' for ' + who if who else ''}, {notice.readable(v['as_of'])}",
             f"{len(v['leads'])} lead{'' if len(v['leads']) == 1 else 's'} from public records{' in ' + ', '.join(v['rep']['regions']) if v['rep']['regions'] else ''}."
             ' Each line of evidence is marked Published (the link opens the source) or Inferred (our reading).', '']
    for n, c in enumerate(v['leads'], 1):
        lines += [f"{n}. {c['organisation']}  [{c['kind_label']}]", f"   Why now: {c['why_now']}"]
        for link in c['chain']:
            when = notice.readable(link['date']) if link['date'] else 'So'
            lines.append(f"   - {when}: {link['text']} [{link['label']}]{' ' + link['url'] if link['url'] else ''}")
        lines += [f"   Next: {c['next']['label']}", '']
    if v['leads']:
        lines += ['Tell me what you think of each one. Reply with the number and a letter:',
                  'A = Didn’t know, worth a call   B = Knew already   C = Wrong', 'For example: 1A 2B 3A 4C 5A']
    else:
        lines.append('Nothing new for this patch today.')
    return '\n'.join(lines)
