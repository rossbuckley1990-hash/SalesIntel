"""The Living Opportunity: one coherent, source-backed briefing for a lead or an account.

It answers, from records that already exist, and never from generated prose:
- what happened (the strongest sourced fact, with its date and source);
- why it could matter (an interpretation built from that record, labelled as such, with any rule of thumb flagged);
- what could be sold (services a source names, kept apart from services that are only possible);
- what could make it irrelevant (contrary evidence first, then the standard reasons for this kind of opportunity);
- the one unanswered question whose answer would most change the decision, and the next move.

The evidence river keeps publication, event, first-seen and research dates apart, and every item says what its source
establishes and what it does not. The next move is decided here, once, so every screen recommends the same action.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.renewal_radar import families
from app.models.crm import Account, AccountLink, Activity, Contact, DealRecord, Draft, Task
from app.models.gaps import GapRequest
from app.models.shadow import Dossier
from app.services import si_core as core
from app.services.atlas import FAMILY_LABEL, normalise

KIND_LABEL = {'private_signal': 'Private-sector signal', 'public_tender': 'Published tender', 'contract_ending': 'Published contract nearing its end',
              'shadow_hypothesis': 'Indirect signal', 'competitor_contract': 'Competitor-held contract', 'customer_expansion': 'Existing customer expansion',
              'unverified_candidate': 'Unverified research candidate'}
VALUE_LABEL = {'decisive': 'Could make or break the opportunity', 'timing': 'Decides when and how to engage', 'access': 'Decides who to speak to'}
VALUE_ORDER = {'decisive': 0, 'timing': 1, 'access': 2}
STALE_DAYS = 548  # evidence older than 18 months is flagged as possibly out of date
RESOLVED_STALE_DAYS = 120  # a resolved question is worth checking again after four months
GAP_COST_CENTS = 120
ESTATE_SIGNALS = {'new_site', 'expansion', 'relocation', 'planning_application', 'refurbishment', 'acquisition', 'construction'}
ESTATE_WORDS = re.compile(r'\b(depots?|sites?|warehouses?|hubs?|programme|facilit(?:y|ies)|buildings?|estate|stores?|campus)\b', re.I)
NOT_ESTABLISHED = {
    'estate': 'It does not say who will install or maintain the fire and security systems, or whether those packages are already let.',
    'leadership': 'It does not say the new leader will review suppliers.',
    'risk': 'It does not say a fire or security contract will change.',
    'default': 'It does not establish a fire or security requirement.'}


def _day(value: Any) -> str:
    return str(value or '')[:10]


def _as_date(value: Any) -> date | None:
    """A full date, or the first day of a published month or year."""
    text = _day(value)
    try:
        if len(text) == 10:
            return date.fromisoformat(text)
        if len(text) == 7:
            return date(int(text[:4]), int(text[5:7]), 1)
        if len(text) == 4:
            return date(int(text), 1, 1)
    except ValueError:
        return None
    return None


def _event(date_: Any, date_kind: str, title: str, *, detail: str = '', url: str = '', source: str = '', basis: str = 'reported',
           establishes: str = '', not_established: str = '', effect: str = 'context', recorded: datetime | None = None) -> dict:
    return {'date': _day(date_), 'date_kind': date_kind, 'title': title[:300], 'detail': detail[:600], 'source': {'url': url, 'label': source} if url else None,
            'basis': basis, 'establishes': establishes[:400], 'not_established': not_established[:400], 'effect': effect,
            'recorded': recorded.isoformat() if recorded else None}


def _long(value: Any) -> str:
    """A date for people: 27 November 2026 (or November 2026, or 2026), never an ISO string."""
    text = _day(value)
    d = _as_date(text)
    if not d:
        return text
    return f'{d.day} {d:%B %Y}' if len(text) >= 10 else f'{d:%B %Y}' if len(text) == 7 else str(d.year)


def _neg(text: str) -> str:
    """Sort key for 'most recent first' on ISO-like date text."""
    return ''.join(chr(255 - ord(ch)) for ch in text)


def _services(named: set[str], possible: set[str]) -> list[dict]:
    out = [{'family': f, 'label': FAMILY_LABEL.get(f, f), 'status': 'named', 'basis': 'Named in a source'} for f in sorted(named)]
    out += [{'family': f, 'label': FAMILY_LABEL.get(f, f), 'status': 'possible', 'basis': 'Possible: not stated by any source'} for f in sorted(possible - named)]
    return out


CONTRACTOR_ROLE = re.compile(r'^(?P<name>[A-Z][\w&.,\' -]{2,80}?) (?:has been |was |is )?(?:appointed|named|selected) (?:as )?(?:the )?(?P<role>main contractor|principal contractor|'
                             r'design and build contractor|contractor|installer|maintenance contractor)(?: (?P<scope>(?:for|on) the [\w\s-]{3,60}))?$', re.I)
PROFILE_TO_FAMILY = {'fire_alarm': 'fire_alarm', 'cctv': 'cctv', 'access_control': 'access_control', 'intruder': 'intruder',
                     'emergency_lighting': 'emergency_lighting', 'sprinkler': 'sprinklers', 'monitoring': 'intruder', 'general': None}


# ------------------------------------------------------------------ the source record, per kind

def _prospect(db: Session, entity_id: int) -> dict | None:
    from app.models.prospect import Prospect
    from app.services.prospect_research import SIGNALS, view
    row = db.get(Prospect, entity_id)
    if row is None:
        return None
    p = view(row)
    signals = [s for s in p.get('signals') or [] if isinstance(s, dict)]
    stated = [s for s in signals if s.get('basis') == 'stated' and s.get('source_url')]
    supporting = [s for s in stated if s.get('direction') != 'against']
    events = []
    for s in signals:
        group = 'estate' if s.get('type') in ESTATE_SIGNALS else 'leadership' if s.get('type') in ('leadership_change', 'new_leader') else \
            'risk' if s.get('type') in ('incident', 'enforcement', 'insurer_requirement') else 'default'
        against = s.get('direction') == 'against'
        events.append(_event(s.get('date'), 'reported', s.get('title') or '', detail=s.get('detail') or '', url=s.get('source_url') or '',
                             source=SIGNALS.get(s.get('type'), (s.get('type') or 'Source', ''))[0], basis='stated' if s.get('basis') == 'stated' else 'inferred',
                             establishes=(s.get('title') or '') if s.get('basis') == 'stated' else 'Nothing on its own: an inference from other evidence.',
                             not_established=NOT_ESTABLISHED[group],
                             effect='weakens' if against else 'supports' if s.get('direction') == 'supports' else 'context'))
    for c in p.get('timing_clues') or []:
        events.append(_event(c.get('date'), 'event', f"{(c.get('kind') or 'timing').replace('_', ' ').capitalize()}: {c.get('detail') or ''}", url=c.get('source_url') or '',
                             source='Timing clue', basis='stated' if c.get('basis') == 'stated' else 'inferred',
                             establishes=c.get('detail') or '' if c.get('basis') == 'stated' else 'An estimate, not a published date.',
                             not_established='It does not say when the fire and security packages are let.'))
    events.append(_event(p.get('created_at'), 'first_seen', 'Found by SalesIntel research', basis='research',
                         establishes='When SalesIntel first recorded this organisation.', recorded=row.created_at))
    weight = {'expansion': 0, 'new_site': 1, 'acquisition': 1, 'relocation': 2, 'planning_application': 2, 'construction': 2, 'refurbishment': 3}

    def rank(s: dict) -> tuple:  # a programme across many sites says more than one site's opening
        estate_investment = s.get('type') == 'investment' and ESTATE_WORDS.search(f"{s.get('title') or ''} {s.get('detail') or ''}")
        return (0 if estate_investment else weight.get(s.get('type'), 9), _neg(_day(s.get('date'))))
    happened = (min(supporting, key=rank) if supporting else None) or (signals[0] if signals else None)
    sites = [s.get('title') for s in stated if s.get('type') in ESTATE_SIGNALS]
    estate = any(s.get('type') in ESTATE_SIGNALS for s in supporting)
    named = set()
    for s in stated:
        named |= families(f"{s.get('title') or ''} {s.get('detail') or ''}")
    possible = {PROFILE_TO_FAMILY.get(x) for x in p.get('services') or []} - {None}
    clues = [c for c in p.get('timing_clues') or [] if c.get('kind') == 'site_opening' and c.get('date')]
    interpretation = (f"{row.name} is adding or changing sites, and new buildings need fire and security systems installed, then maintained." if estate else
                      f'A sourced change at {row.name} may lead to a review of how its fire and security is provided. A need is not confirmed.')
    today_text = date.today().isoformat()
    planned = sorted((c for c in clues if _day(c['date']) >= today_text[:len(_day(c['date']))]), key=lambda c: _day(c['date']))
    if planned:
        interpretation += (' Still ahead, as reported: ' + '; '.join(f"{(c.get('detail') or 'a site').rstrip('.')} ({_long(c['date'])})" for c in planned[:4]) +
                           '. The soonest may already be committed; later sites are more likely to be open.')
    heuristic = next((r for r in (p.get('timing') or {}).get('reasons') or [] if 'usually' in r.lower() or 'typically' in r.lower()), None)
    disprove = [f"Contrary evidence: {s.get('title')}" for s in signals if s.get('direction') == 'against']
    if estate:
        disprove += ['The fire and security installation packages may already be awarded', 'A national supplier may already cover the estate under an existing agreement',
                     'A principal contractor may control specialist procurement', 'Maintenance may already be committed to the installer or an incumbent']
    incumbent = p.get('incumbent') or {}
    if incumbent.get('name'):
        disprove.append(f"Reported incumbent: {incumbent['name']}" + ('' if incumbent.get('basis') == 'stated' else ' (not confirmed)'))
    site_text = 'the planned sites' if len(sites) != 1 else 'the new site'
    questions = [('package_status', 'Fire and security packages', f"Have the fire and security packages for {site_text} already been awarded, and who controls their procurement?",
                  'decisive', 'If they are awarded, there is no installation opportunity; if a main contractor controls them, that is who to approach.')] if estate else []
    questions += [('site_status', 'Project stage', 'Which of the planned sites are still in development, and when does each open?', 'timing',
                   'Sites still in design or early construction are the ones a supplier can still influence.')] if estate else []
    questions += [('incumbent', 'Current fire and security supplier', "Which company currently maintains this organisation's fire or security systems?", 'timing',
                   'It shows whether the new sites would fall under an existing maintenance agreement, and who you compete with.')]
    if not estate:
        questions.insert(0, ('need', 'Requirement', f'Does {row.name} have a fire or security requirement linked to this change, and who owns it?', 'decisive',
                             'Without a need this is background, not an opportunity.'))
    rels = []
    if incumbent.get('name'):
        rels.append({'kind': 'incumbent', 'label': 'Reported incumbent', 'name': incumbent['name'], 'basis': incumbent.get('basis') or 'unknown',
                     'source': incumbent.get('source_url') or ''})
    for c in p.get('competitors') or []:
        if isinstance(c, dict) and c.get('name'):
            rels.append({'kind': 'competitor', 'label': 'Competitor named by research', 'name': c['name'], 'basis': c.get('basis') or 'inferred', 'source': c.get('source_url') or ''})
    for s in signals:  # a contractor a source names, with the role the source gives it (never inferred from a name)
        found = CONTRACTOR_ROLE.match(s.get('title') or '')
        if found and s.get('basis') == 'stated':
            rels.append({'kind': 'main_contractor', 'label': f"{found.group('role').capitalize()}{(' ' + found.group('scope')) if found.group('scope') else ''}",
                         'name': found.group('name').strip(), 'basis': 'stated', 'source': s.get('source_url') or ''})
    for person in (p.get('people') or [])[:4]:
        if isinstance(person, dict) and person.get('name') and person.get('source_url'):
            rels.append({'kind': 'person', 'label': person.get('role') or 'Named by a source', 'name': person['name'], 'basis': 'stated', 'source': person['source_url']})
    kind = 'private_signal' if supporting else 'unverified_candidate'
    return {'kind': kind, 'organisation': {'name': row.name, 'sector': p.get('sector'), 'location': p.get('location'), 'website': p.get('website'),
                                             'company_number': p.get('company_number')},
            'events': events, 'happened': happened and {'text': happened.get('title') or '', 'detail': happened.get('detail') or '', 'date': _day(happened.get('date')),
                                                        'source': happened.get('source_url') or '', 'basis': happened.get('basis')},
            'interpretation': interpretation, 'heuristic': heuristic, 'services': _services(named, possible), 'disprove': disprove, 'questions': questions,
            'relationships': rels, 'unknowns': list(p.get('unknowns') or []), 'first_seen': row.created_at, 'updated': row.updated_at,
            'people': p.get('people') or [], 'routes': p.get('contact_routes') or []}


def _market(db: Session, entity_id: int) -> dict | None:
    found = core._mo(db, entity_id)
    if not found:
        return None
    _item, s = found
    tender = s.get('category') in ('live_procurement', 'official_early_signal')
    customer, title, supplier, timing = s.get('customer') or '', s.get('title') or '', s.get('supplier') or '', _day(s.get('timing'))
    events = [_event(e.get('published_at'), 'published', f"{e.get('source') or 'Notice'} published", detail=title, url=e.get('source_url') or '',
                     source=e.get('source') or 'Notice', basis='published', establishes=f'{customer} published this record: {title}',
                     not_established=('It does not say whether you meet the mandatory requirements.' if tender else
                                      'It does not say whether the buyer will extend, re-tender or call off.'))
              for e in s.get('evidence') or []]
    if timing:
        events.append(_event(timing, 'event', ('Tender deadline' if tender else 'End of published term') + f': {_long(timing)}',
                             basis='published' if 'published' in (s.get('timing_basis') or 'published').lower() else 'inferred',
                             establishes=f"{s.get('timing_basis') or 'Published date'}.", not_established='An extension may change it.' if not tender else '',
                             effect='supports'))
    for c in s.get('counter_evidence') or []:
        text = c if isinstance(c, str) else (c.get('text') or '')
        if text:
            events.append(_event('', 'reported', text, basis='published', effect='weakens', establishes=text))
    named = families(title)
    when = _long(timing)
    if tender:
        happened = title or f'{customer} published a tender'
        said = f"{customer} published this tender" + (f"; responses are due {when}." if when else '.')
        interpretation = 'A live published requirement: respond through the buyer\'s procurement route, by its rules and deadline.'
        disprove = ['A mandatory requirement you may not meet (accreditation, insurance or turnover)', 'A competition limited to a framework you are not on',
                    'Scope you cannot deliver or price competitively']
        questions = [('eligibility', 'Mandatory requirements', 'What are the mandatory requirements in the tender documents (accreditations, insurance, turnover), and do we meet them?',
                      'decisive', 'If you do not meet a mandatory requirement, bidding is wasted effort.'),
                     ('evaluation_criteria', 'Evaluation criteria', 'What are the published evaluation criteria and weightings?', 'timing',
                      'They decide how to shape the bid and whether you can compete on quality or price.'),
                     ('incumbent', 'Current supplier', 'Which company currently provides this service?', 'access', 'It shows who you compete against.')]
    else:
        happened = f"Contract{f' with {supplier}' if supplier else ''} " + (f'ends {when}' if when else 'has a published end date')
        said = f"{customer}'s published contract: {title}." if title else ''
        interpretation = 'The buyer will extend, re-tender or call off before the term ends. That decision is a legitimate moment to offer an alternative.'
        disprove = ['An extension may already be agreed', 'A framework call-off without open competition', 'The service moving into a wider facilities contract']
        questions = [('route', 'Route to market', 'Will the buyer extend, re-tender or call off from a framework, and when will it decide?', 'decisive',
                      'It decides whether there is a competition to enter at all, and when.'),
                     ('contract_end', 'Extension options', 'What extension options does the current contract allow?', 'timing', 'An extension moves the window.'),
                     ('find_role', 'Procurement or category manager', 'Who is the procurement or category manager, and how can they be reached?', 'access',
                      'They run the decision.')]
    disprove = [f'Contrary evidence: {e["title"]}' for e in events if e['effect'] == 'weakens'] + disprove
    rels = [{'kind': 'incumbent', 'label': 'Supplier on the published record', 'name': supplier, 'basis': 'published',
             'source': (s.get('evidence') or [{}])[0].get('source_url', '')}] if supplier else []
    return {'kind': 'public_tender' if tender else 'contract_ending', 'organisation': {'name': customer, 'sector': 'Public sector', 'location': s.get('nation'), 'website': None,
                                                                                         'company_number': None},
            'events': events, 'happened': {'text': happened, 'detail': ' '.join(x for x in (said, (s.get('brief') or {}).get('why_it_matters') or '') if x),
                                           'date': (events[0]['date'] if events else ''),
                                           'source': (s.get('evidence') or [{}])[0].get('source_url', ''), 'basis': 'published'},
            'interpretation': interpretation, 'heuristic': None if tender else 'Buyers usually prepare this decision 6 to 12 months before the term ends.',
            'services': _services(named, set()), 'disprove': disprove, 'questions': questions, 'relationships': rels,
            'unknowns': list((s.get('brief') or {}).get('missing_information') or []), 'first_seen': _item.first_seen, 'updated': _item.last_evaluated,
            'people': [], 'routes': []}


def _shadow(db: Session, entity_id: int) -> dict | None:
    from app.services import shadow
    found = shadow.current(db, entity_id)
    if not found:
        return None
    row, a = found
    events = [_event(e.get('published'), 'published', e.get('label') or '', url=e.get('source_url') or '', source=(e.get('type') or 'Record').replace('_', ' '),
                     basis=e.get('basis') or 'published', establishes=e.get('label') or '',
                     not_established='An indirect record: it does not say anyone needs fire or security work.',
                     effect='weakens' if e.get('role') == 'contradicts' else 'supports' if e.get('role') in ('anchor', 'supports') else 'context')
              for e in a.get('timeline') or []]
    anchor = next((e for e in a.get('timeline') or [] if e.get('role') == 'anchor'), None)
    alternatives = [x for x in a.get('alternatives') or [] if isinstance(x, dict)]
    questions = [('hypothesis_test', 'The decisive test', alternatives[0].get('test') or 'Confirm the change from a direct source', 'decisive',
                  f"It rules out the strongest other explanation: {alternatives[0].get('explanation')}")] if alternatives else []
    questions += [('site_status', 'Project stage', 'Has the work started, and when will the site be handed over?', 'timing', 'It decides whether packages are still open.'),
                  ('site_operator', 'Who will run the site', 'Who will operate and maintain the site after handover?', 'access', 'They are who to approach.')]
    rels = [{'kind': 'main_contractor', 'label': 'Main contractor on the record', 'name': a['main_contractor'], 'basis': 'published', 'source': ''}] if a.get('main_contractor') else []
    return {'kind': 'shadow_hypothesis', 'organisation': {'name': a.get('entity_name') or row.entity_name, 'sector': None, 'location': a.get('postcode') or a.get('site'), 'website': None,
                                                          'company_number': a.get('company_number')},
            'events': events, 'happened': anchor and {'text': anchor.get('label') or '', 'detail': a.get('site') or '', 'date': _day(anchor.get('published')),
                                                      'source': anchor.get('source_url') or '', 'basis': anchor.get('basis') or 'published'},
            'interpretation': f"Hypothesis, not a finding: {a.get('hypothesis') or ''}", 'heuristic': None,
            'services': _services(set(), {s for s in a.get('services') or []}), 'disprove': [x.get('explanation') for x in alternatives if x.get('explanation')] + list(a.get('disconfirming') or []),
            'questions': questions, 'relationships': rels, 'unknowns': list(a.get('unknown') or []), 'first_seen': row.first_seen_at, 'updated': row.last_evaluated,
            'people': [], 'routes': []}


def _contract(db: Session, entity_id: int) -> dict | None:
    from app.models.atlas import AtlasContractParty, AtlasContractor
    from app.models.market_contract import MarketContract
    from app.services import atlas
    contract = db.get(MarketContract, entity_id)
    party = db.scalar(select(AtlasContractParty).where(AtlasContractParty.contract_id == entity_id)) if contract else None
    if not contract or not party:
        return None
    supplier = db.get(AtlasContractor, party.contractor_id)
    v = atlas.contract_view(contract, party, supplier.display_name if supplier else (contract.supplier or ''), date.today())
    reason = (v['reasons'] or [{}])[0]
    events = [_event(t['date'], 'published' if t['basis'] == 'publication date' else 'first_seen' if t['basis'] == 'retrieval' else 'event', t['event'], basis=t['basis'],
                     establishes=t['event']) for t in v['timeline']]
    return {'kind': 'competitor_contract', 'organisation': {'name': contract.buyer, 'sector': 'Public sector', 'location': v['region'] or v['nation'], 'website': None, 'company_number': None},
            'events': events, 'happened': {'text': f"{contract.buyer} named {v['supplier']} as supplier: {contract.title}. {v['status']['label']}.", 'detail': '',
                                           'date': (v['dates'] or {}).get('published') or '', 'source': (v['sources'] or [{}])[0].get('url', ''), 'basis': 'published'},
            'interpretation': reason.get('mechanism') or 'A competitor holds this published contract; its term decides when an alternative can be offered.',
            'heuristic': None, 'services': _services({s['family'] for s in v['services']}, set()),
            'disprove': list(reason.get('alternatives') or []) + list(reason.get('disconfirming') or []),
            'questions': [('relationship_status', 'Current status', f"Is {v['supplier']}'s contract still running, and has it been extended or re-let?", 'decisive',
                           'If it has been re-let recently, the next window is years away.'),
                          ('route', 'Route to market', 'How will the buyer procure the service next time, and when will it decide?', 'timing', 'It decides when to engage.')],
            'relationships': [{'kind': 'incumbent', 'label': 'Supplier on the published record', 'name': v['supplier'], 'basis': 'published',
                               'source': (v['sources'] or [{}])[0].get('url', '')}],
            'unknowns': list(reason.get('missing') or []), 'first_seen': contract.first_seen, 'updated': contract.last_evaluated, 'people': [], 'routes': []}


ADAPTERS = {'pr': ('prospect', _prospect), 'mo': ('market_opportunity', _market), 'sh': ('shadow_hypothesis', _shadow), 'mc': ('market_contract', _contract)}


def source(db: Session, key: str) -> dict | None:
    kind, _, raw = key.partition(':')
    if kind not in ADAPTERS or not raw.isdigit():
        raise LookupError('Unknown record')
    return ADAPTERS[kind][1](db, int(raw))


# ------------------------------------------------------------------ gaps, ranked by how much the answer changes the decision

def _gap_status(r: GapRequest | None, now: datetime) -> str:
    if r is None:
        return 'open'
    if r.status in ('queued', 'running'):
        return 'researching'
    if r.status == 'resolved':
        when = r.resolved_at or r.created_at
        return 'stale' if when and (now - (when if when.tzinfo else when.replace(tzinfo=UTC))).days > RESOLVED_STALE_DAYS else 'resolved'
    # A search that did not run (no provider, a failure, cancelled) is not an answer: the question stays open.
    return {'not_found': 'not_found', 'conflicting': 'conflicting', 'needs_human': 'conflicting', 'partial': 'partial'}.get(r.status, 'not_run')


def rank_gaps(questions: list[tuple], requests: list[GapRequest], now: datetime) -> list[dict]:
    latest: dict[tuple, GapRequest] = {}
    for r in sorted(requests, key=lambda r: r.id, reverse=True):
        latest.setdefault((r.gap, r.subject), r)
    out = []
    for gap, subject, question, value, why in questions:
        r = latest.get((gap, subject))
        status = _gap_status(r, now)
        out.append({'gap': gap, 'subject': subject, 'question': question, 'value': value, 'value_label': VALUE_LABEL[value], 'why': why, 'status': status,
                    'request_id': r.id if r else None, 'job_id': r.job_id if r else None, 'answer': (r.summary if r else '') or '', 'findings': (r.findings if r else []) or [],
                    'researched': r.created_at.date().isoformat() if r else None,
                    'action': 'ask_customer' if status in ('not_found', 'conflicting') else 'research' if status in ('open', 'stale', 'partial', 'not_run') else None,
                    'cost_cents': GAP_COST_CENTS})
    # Open first, by decision value; a question public sources could not answer is next (ask the customer); answered last.
    rank = {'open': 0, 'stale': 0, 'partial': 0, 'not_run': 0, 'researching': 1, 'not_found': 2, 'conflicting': 2, 'resolved': 3}
    out.sort(key=lambda g: (rank[g['status']], VALUE_ORDER[g['value']]))
    return out


# ------------------------------------------------------------------ the next move, decided once

def _action(key: str, label: str, why: str, produces: str, *, available: bool = True, reason: str = '', params: dict | None = None, cost_cents: int = 0) -> dict:
    return {'action': key, 'label': label, 'why': why, 'produces': produces, 'available': available, 'unavailable_reason': reason, 'params': params or {},
            'cost_cents': cost_cents}


def next_move(state: dict) -> tuple[dict, list[dict]]:
    """The one recommended action and its alternatives, from what is recorded. Used by every screen."""
    top = state['top_gap']
    research_ok, research_reason = state['research_available'], state['research_reason']
    candidates = []
    if state['requirement'] and not state['deal']:
        candidates.append(_action('qualify', 'Qualify into a deal', 'The customer has stated a requirement.',
                                  'A deal that keeps the discovery, the research and what the customer said.'))
    if state['kind'] == 'public_tender' and not state['deal'] and top and top['gap'] != 'eligibility' and state['has_account']:
        candidates.append(_action('qualify', 'Decide bid or no bid', 'The requirement is published and the decisive question has been looked at.',
                                  'A deal with the bid decision recorded, ready for the requirements and the response.'))
    task = state.get('next_task')
    if task:  # a follow-up the team set itself comes before anything SalesIntel suggests
        candidates.append(_action('complete_follow_up', f"{task['title']} (due {task['due']:%-d %b})", 'You set this follow-up. Log what happened to close it.',
                                  'The conversation on record, this follow-up closed, and the next one set.', params={'task_id': task['id'], 'due_on': task['due'].isoformat()}))
    if top and top['action'] == 'research':
        candidates.append(_action('research_gap', f"Research: {top['question']}", f"{top['why']} Public sources are checked first; nothing is guessed.",
                                  'A sourced answer, or a clear "not published", saved to this opportunity.'
                                  + ('' if state['has_account'] else ' It saves this as an account first, so the answer is kept.'), available=research_ok, reason=research_reason,
                                  params={'gap': top['gap'], 'subject': top['subject'], 'question': top['question']}, cost_cents=GAP_COST_CENTS))
    saves = '' if state['has_account'] else ' It saves this as an account first.'
    if not state['people_covered']:
        candidates.append(_action('find_people', 'Find the right people',
                                  ('Public sources do not answer the key question, so the customer has to: ' + top['question']) if top and top['action'] == 'ask_customer'
                                  else 'Nobody who decides is named or reachable yet.',
                                  'Named people where a source names them, and legitimate business routes.' + saves))
    if not state['drafts']:
        candidates.append(_action('prepare_introduction', 'Prepare introduction', 'A grounded first approach, built from the evidence.',
                                  'A draft introduction to review. Nothing is sent automatically.' + saves))
    if not state['outbound']:
        candidates.append(_action('log_contact', 'Log the first contact', 'Record the call, email or visit, and what was said.',
                                  'The conversation on record, and the next step it sets.' + saves))
    elif not state['open_task']:
        candidates.append(_action('set_follow_up', 'Set the next follow-up', 'There is no next step on record.', 'A dated follow-up on Today.'))
    if not state['has_account']:
        candidates.append(_action('open_account', 'Save as an account', 'Keep every finding, contact and conversation together without acting yet.',
                                  'An account linked to this record and its evidence.'))
    candidates.append(_action('log_contact', 'Record what the customer said', 'Keep the story current.', 'An interaction on record.' + saves))
    if not state['dossier'] and state['kind'] in ('private_signal', 'shadow_hypothesis', 'unverified_candidate', 'customer_expansion'):
        candidates.append(_action('investigate', 'Run a deep investigation', 'Tests the whole hypothesis against public evidence, including evidence against it.',
                                  'A dossier with a verdict: strengthened, weakened or unresolved.' + saves, available=research_ok, reason=research_reason, cost_cents=400))
    seen, ordered = set(), []
    for c in candidates:
        if c['action'] not in seen:
            seen.add(c['action'])
            ordered.append(c)
    primary = next((c for c in ordered if c['available']), ordered[0])
    blocked = [c for c in ordered[:ordered.index(primary)] if not c['available']]
    primary = {**primary, 'blocked': [{'label': b['label'], 'reason': b['unavailable_reason']} for b in blocked]}
    return primary, [c for c in ordered if c['action'] != primary['action'] and c not in blocked][:3]


def _journey(kind: str, state: dict) -> list[dict]:
    decisive_done = bool(state['top_gap'] is None or state['top_gap']['status'] in ('resolved', 'not_found', 'conflicting')) or state['dossier']
    steps = {
        'private_signal': [('Investigate the evidence', decisive_done), ('Establish the need and the buyer', state['requirement']),
                           ('Prepare the approach', state['drafts']), ('Engage', state['outbound']), ('Qualify', state['deal'])],
        'public_tender': [('Review the notice and documents', state['has_account']), ('Check the mandatory requirements', decisive_done), ('Decide bid or no bid', state['deal']),
                          ('Assess requirements and price', state['deal'] and state['requirement']), ('Submit and track', False)],
        'contract_ending': [('Review the published contract', state['has_account']), ('Establish the route to market', decisive_done), ('Find who decides', state['people_covered']),
                            ('Engage', state['outbound']), ('Qualify', state['deal'])],
        'competitor_contract': [('Verify the relationship', state['has_account']), ('Investigate its status and change signals', decisive_done),
                                ('Identify the route to market', state['people_covered']), ('Qualify', state['deal'])],
        'shadow_hypothesis': [('Test the hypothesis', decisive_done), ('Establish the need and the buyer', state['requirement']), ('Prepare the approach', state['drafts']),
                              ('Engage', state['outbound']), ('Qualify', state['deal'])],
        'customer_expansion': [('Understand the estate change', decisive_done), ('Review the existing contract', state['has_account']), ('Identify the account stakeholder', state['people_covered']),
                               ('Confirm the scope', state['requirement']), ('Develop the proposal', state['deal'])],
    }.get(kind) or [('Confirm the evidence', decisive_done), ('Establish the need', state['requirement']), ('Engage', state['outbound']), ('Qualify', state['deal'])]
    out, current = [], False
    for label, done in steps:
        s = 'done' if done else ('current' if not current else 'later')
        current = current or not done
        out.append({'label': label, 'state': s})
    return out


# ------------------------------------------------------------------ the brief

def _research_available(db: Session) -> tuple[bool, str]:
    from app.config import get_settings
    from app.services import spend
    from app.services.ai_costs import research_provider
    settings = get_settings()
    if research_provider(settings) is None:
        return False, ('Web research is switched off in demo mode, so no API credit is used.' if settings.app_env == 'demo' else 'Web research is not configured here.')
    if spend.live_provider() and not spend.programme(db)['approved']:
        return False, spend.refusal(spend.ApprovalRequired('not_approved'))['detail']
    return True, ''


def _account_for(db: Session, key: str) -> Account | None:
    kind, _, raw = key.partition(':')
    if kind == 'acct':
        return db.get(Account, int(raw)) if raw.isdigit() else None
    entity_type = {'pr': 'prospect', 'mo': 'market_opportunity', 'sh': 'shadow_hypothesis', 'mc': 'market_contract'}.get(kind)
    link = db.scalar(select(AccountLink).where(AccountLink.entity_type == entity_type, AccountLink.entity_id == int(raw))) if entity_type and raw.isdigit() else None
    return db.get(Account, link.account_id) if link else None


def _primary_key(db: Session, account: Account) -> str | None:
    rev = {'prospect': 'pr', 'market_opportunity': 'mo', 'shadow_hypothesis': 'sh', 'market_contract': 'mc'}
    link = db.scalar(select(AccountLink).where(AccountLink.account_id == account.id).order_by(AccountLink.id))
    return f"{rev[link.entity_type]}:{link.entity_id}" if link and link.entity_type in rev else None


def build(db: Session, key: str, *, last_review: datetime | None = None, now: datetime | None = None) -> dict:
    """The Living Opportunity for a lead key (pr:, mo:, sh:, mc:) or an account (acct:<id>). A lead that already has an
    account opens as that account, so research and conversations are never split."""
    now = now or datetime.now(UTC)
    account = _account_for(db, key)
    if key.startswith('acct:') and account is None:
        raise LookupError('Account not found')
    source_key = _primary_key(db, account) if account else key
    record = source(db, source_key) if source_key else None
    if record is None and account is None:
        raise LookupError('Record not found')
    record = record or {'kind': 'unverified_candidate', 'organisation': {'name': account.name}, 'events': [], 'happened': None, 'interpretation': '',
                        'heuristic': None, 'services': [], 'disprove': [], 'questions': [('need', 'Requirement', f'Does {account.name} have a fire or security requirement, and who owns it?',
                                                                                          'decisive', 'Without a need this is background, not an opportunity.')],
                        'relationships': [], 'unknowns': [], 'first_seen': account.created_at, 'updated': account.updated_at, 'people': [], 'routes': []}
    events, story = list(record['events']), []
    requests, contacts, acts, drafts, tasks, deals, dossier = [], [], [], [], [], [], None
    if account:
        requests = db.scalars(select(GapRequest).where(GapRequest.account_id == account.id)).all()
        contacts = db.scalars(select(Contact).where(Contact.account_id == account.id)).all()
        acts = db.scalars(select(Activity).where(Activity.account_id == account.id).order_by(Activity.occurred_at)).all()
        drafts = db.scalars(select(Draft).where(Draft.account_id == account.id).order_by(Draft.id)).all()
        tasks = db.scalars(select(Task).where(Task.account_id == account.id)).all()
        deals = db.scalars(select(DealRecord).where(DealRecord.account_id == account.id).order_by(DealRecord.id)).all()
        dossier = db.scalar(select(Dossier).where(Dossier.account_id == account.id).order_by(Dossier.version.desc()))
        story.append({'date': account.created_at.isoformat(), 'kind': 'discovered', 'text': f'Account opened from: {KIND_LABEL.get(record["kind"], "a record")}',
                      'detail': (record.get('happened') or {}).get('text') or ''})
        for r in requests:
            when = r.resolved_at or r.created_at
            if r.status in ('queued', 'running'):
                continue
            events.append(_event(when.isoformat(), 'researched', f'Research: {r.question}', detail=r.summary or '', basis='research',
                                 url=next((f.get('source_url') for f in r.findings or [] if f.get('source_url')), '') or '', source='Gap research',
                                 establishes=r.summary or ('Not published in the sources checked.' if r.status == 'not_found' else ''),
                                 not_established='What the sources do not say stays unknown.' if r.status != 'resolved' else '',
                                 effect='context', recorded=when))
            story.append({'date': when.isoformat(), 'kind': 'research', 'text': f'Researched: {r.subject}', 'detail': r.summary or r.status.replace('_', ' ')})
        if dossier is not None:
            when = getattr(dossier, 'created_at', None) or account.updated_at
            events.append(_event(when.isoformat(), 'researched', f'Deep investigation: {dossier.verdict}', basis='research', source='Investigation',
                                 establishes={'strengthened': 'The research supports the hypothesis.', 'weakened': 'Evidence was found against it: read before acting.',
                                              'unresolved': 'Not settled: open questions remain.'}.get(dossier.verdict, ''),
                                 effect='weakens' if dossier.verdict == 'weakened' else 'supports' if dossier.verdict == 'strengthened' else 'context', recorded=when))
            story.append({'date': when.isoformat(), 'kind': 'research', 'text': f'Deep investigation: {dossier.verdict}', 'detail': ''})
        for c in contacts:
            story.append({'date': c.created_at.isoformat(), 'kind': 'contact', 'text': f"Contact on record: {c.name or c.label or c.role or 'a route'}",
                          'detail': f"{c.role or ''} · {c.status}".strip(' ·')})
        for d in drafts:
            story.append({'date': d.created_at.isoformat(), 'kind': 'draft', 'text': f'Introduction {d.status}', 'detail': d.subject or ''})
        for a in acts:
            events.append(_event(a.occurred_at.isoformat(), 'recorded', f"{a.kind.replace('_', ' ').capitalize()} ({a.direction})", detail=a.summary, basis='recorded',
                                 establishes=(f'The customer stated: {a.requirements}' if (a.requirements or '').strip() else 'What happened, as recorded by your team.'),
                                 effect='supports' if a.outcome == 'requirement_captured' or (a.requirements or '').strip() else 'context', recorded=a.created_at))
            story.append({'date': a.occurred_at.isoformat(), 'kind': 'interaction', 'text': f"{a.kind.replace('_', ' ').capitalize()}: {a.summary[:140]}",
                          'detail': ' · '.join(x for x in (a.outcome.replace('_', ' '), f'Requirement: {a.requirements}' if a.requirements else '') if x)})
        for d in deals:
            story.append({'date': d.created_at.isoformat(), 'kind': 'deal', 'text': f'Deal: {d.title}', 'detail': f'Stage: {d.stage}'})
    events.sort(key=lambda e: e['date'] or '0000', reverse=True)
    story.sort(key=lambda s: s['date'])
    for e in events:
        e['new'] = bool(last_review and e['recorded'] and datetime.fromisoformat(e['recorded']).replace(tzinfo=UTC) > (last_review if last_review.tzinfo else last_review.replace(tzinfo=UTC)))
    gaps = rank_gaps(record['questions'], requests, now)
    research_ok, research_reason = _research_available(db)
    # Someone who decides is named: a usable contact on the account, or (before the account exists) a person a source names.
    people_covered = any(c.status != 'do_not_contact' and c.name for c in contacts) or \
        (account is None and any(isinstance(p, dict) and p.get('name') and p.get('source_url') for p in record.get('people') or []))
    state = {'kind': record['kind'], 'has_account': account is not None, 'top_gap': gaps[0] if gaps else None, 'research_available': research_ok,
             'research_reason': research_reason, 'requirement': any(a.outcome == 'requirement_captured' or (a.requirements or '').strip() for a in acts),
             'deal': bool(deals), 'people_covered': people_covered, 'drafts': bool(drafts), 'outbound': any(a.direction == 'outbound' for a in acts),
             'open_task': any(t.status == 'open' for t in tasks), 'dossier': dossier is not None,
             'next_task': next(({'id': t.id, 'title': t.title, 'due': t.due_on} for t in sorted((t for t in tasks if t.status == 'open'), key=lambda t: (t.due_on, t.id))), None)}
    primary, alternatives = next_move(state)
    suppressed = {c.name.strip().lower() for c in contacts if c.status == 'do_not_contact' and c.name}
    relationships = [{**r, 'label': f"{r['label']} · asked not to be contacted"} if r.get('kind') == 'person' and r['name'].strip().lower() in suppressed else r
                     for r in record['relationships']]
    dated = [e for e in record['events'] if e['basis'] in ('stated', 'published') and e['date'] and e['date_kind'] != 'event' and e['date'] <= now.date().isoformat()]
    latest = max((e['date'] for e in dated), default='')
    latest_day = _as_date(latest)
    # Old evidence is flagged unless a sourced date still lies ahead (a published contract end, a reported opening).
    ahead = any(e['date_kind'] == 'event' and e['basis'] in ('stated', 'published') and e['date'] and e['date'] > now.date().isoformat()[:len(e['date'])]
                for e in record['events'])
    stale = bool(latest_day and (now.date() - latest_day).days > STALE_DAYS and not ahead)
    happened = record.get('happened') or {}
    return {
        'key': key, 'account_id': account.id if account else None, 'source_key': source_key, 'kind': record['kind'], 'kind_label': KIND_LABEL.get(record['kind'], 'Opportunity'),
        'organisation': record['organisation'],
        'reveal': {'headline': happened.get('text') or record['organisation'].get('name') or '', 'happened': happened or None,
                   'why': record['interpretation'], 'heuristic': record['heuristic'], 'services': record['services'],
                   'disprove': ((['Your deep investigation found evidence against this opportunity: read it before acting'] if dossier is not None and dossier.verdict == 'weakened' else [])
                                + record['disprove'])[:7],
                   'key_question': gaps[0] if gaps else None,
                   'freshness': {'latest_evidence': latest, 'first_seen': record['first_seen'].date().isoformat() if record.get('first_seen') else None,
                                 'last_researched': max((r.created_at.date().isoformat() for r in requests), default=None),
                                 'stale': stale, 'note': 'The newest sourced evidence is over 18 months old: check it is still current.' if stale else ''}},
        'next': primary, 'alternatives': alternatives, 'research': {'available': research_ok, 'reason': research_reason}, 'gaps': gaps, 'evidence': events[:60], 'relationships': relationships,
        'journey': _journey(record['kind'], state), 'story': story,
        'stakeholders': [{'name': c.name, 'role': c.role, 'status': c.status, 'source': c.source_url, 'route': c.route_kind} for c in contacts if c.status != 'do_not_contact']
                        or [{'name': p.get('name'), 'role': p.get('role'), 'status': 'named by a source', 'source': p.get('source_url'), 'route': ''}
                            for p in record.get('people') or [] if isinstance(p, dict) and p.get('name') and p['name'].strip().lower() not in suppressed][:6],
        'unknowns': record['unknowns'][:8],
        'recorded_requirement': next((a.requirements.strip() for a in reversed(acts) if (a.requirements or '').strip()), ''),
        'sources': [{'key': source_key, 'title': (happened.get('text') or record['organisation'].get('name') or '')[:120]}] if source_key else [],
        'since_last_review': {'since': last_review.isoformat() if last_review else None, 'new_events': sum(1 for e in events if e['new'])},
    }


def next_label(db: Session, account_id: int) -> str | None:
    """The next move's label for an account, for screens that show only one line (Accounts, Engage)."""
    try:
        return build(db, f'acct:{account_id}')['next']['label']
    except Exception:  # never break a list view because one brief could not be built
        return None
