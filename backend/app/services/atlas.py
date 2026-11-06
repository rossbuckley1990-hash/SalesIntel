"""Contract Atlas: who holds fire and security work, for whom, until when, and why an account may be worth investigating.

Built over the Market Network, never beside it:
- contractor identities come from the suppliers named on canonical contracts (market_contracts), with a Companies House
  number only where a source publishes one for that exact supplier;
- each link to a contract points at the canonical contract, which keeps every source, date and value with its basis;
- relationships reported by case studies and announcements are researched per workspace (see atlas_research).

Identity is conservative. One company number is one contractor. A name without a number joins a numbered contractor only
when it is the identical legal name (ignoring case, punctuation, "&"/"and" and "Limited"/"Ltd") and that name has only
one published number. Similar names stay apart, a subsidiary is never merged into its parent, and a name published with
two numbers is left for a person to resolve.

Nothing here estimates a probability. Reasons to investigate are built from published dates, with the mechanism, the
other explanations, what would disprove it and what is missing.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.intelligence.contract_lifecycle import _INSTALL, _MAINTENANCE
from app.intelligence.renewal_radar import _CALL_OFF, _VIA_FRAMEWORK, OWN_GROUP, clean_supplier, families
from app.models.atlas import AtlasAlias, AtlasContractParty, AtlasContractor, AtlasIdentityConflict, AtlasRelationship
from app.models.market_contract import MarketContract
from app.models.market_graph import MarketRelationship
from app.models.market_network import MarketAward, MarketEntity, MarketSourceState, SourceRevision

BUILD = 'atlas-1'
STATE_KEY = 'contract_atlas'
RELEVANT_FIT = ('core', 'adjacent', 'bundled', 'framework')
HORIZON_DAYS = 548  # 18 months
LOOKBACK_DAYS = 730  # a published end up to two years ago may still be running under an unpublished extension

FAMILY_LABEL = {'fire_alarm': 'Fire alarms and detection', 'emergency_lighting': 'Emergency lighting', 'extinguishers': 'Extinguishers',
                'sprinklers': 'Sprinklers and suppression', 'smoke_control': 'Smoke control and dampers', 'cctv': 'CCTV',
                'access_control': 'Access control and door entry', 'intruder': 'Intruder alarms and monitoring', 'passive_fire': 'Passive fire protection',
                'fire_risk_assessment': 'Fire risk assessment'}
# The workspace profile's service words, to the families the records are classified by.
PROFILE_FAMILIES = {'fire_alarm': {'fire_alarm'}, 'cctv': {'cctv'}, 'access_control': {'access_control'}, 'intruder': {'intruder'},
                    'emergency_lighting': {'emergency_lighting'}, 'sprinkler': {'sprinklers'}, 'monitoring': {'intruder', 'fire_alarm'}}
SCOPE_LABEL = {'maintenance': 'Maintenance and servicing', 'installation': 'Installation or replacement works',
               'maintenance_and_installation': 'Maintenance and installation', 'not_stated': 'Scope not stated'}
ROUTE_LABEL = {'framework_appointment': 'Framework appointment, not a call-off contract', 'call_off': 'Call-off under a framework',
               'direct_award': 'Contract awarded by the buyer'}
MATCH_LABEL = {'company_number': 'Companies House number on the record', 'identical_legal_name': 'Identical legal name to a numbered record',
               'name_only': 'Name only: no company number published'}

# Postcode area to region. Areas that straddle a boundary are approximate, and say so.
REGIONS = {
    'North East': 'NE SR DH DL TS', 'North West': 'M L WN WA BL BB PR FY LA CA CH CW OL SK',
    'Yorkshire and the Humber': 'LS BD HD HX HG YO HU DN S WF', 'East Midlands': 'NG DE LE NN LN',
    'West Midlands': 'B CV DY WV WS ST TF WR HR', 'East of England': 'CB CO IP NR PE CM SS SG AL LU',
    'London': 'E EC N NW SE SW W WC BR CR EN HA IG RM SM UB', 'South East': 'BN CT GU ME MK OX PO RG RH SL SO TN HP DA KT TW WD',
    'South West': 'BA BH BS DT EX GL PL SN SP TA TQ TR', 'Scotland': 'AB DD DG EH FK G HS IV KA KW KY ML PA PH TD ZE',
    'Wales': 'CF LD LL NP SA SY', 'Northern Ireland': 'BT'}
AREA_REGION = {area: region for region, areas in REGIONS.items() for area in areas.split()}
APPROXIMATE_AREAS = {'CH', 'SK', 'DA', 'KT', 'TW', 'WD', 'SY', 'TD', 'DN'}


def normalise(name: str) -> str:
    """The legal name with formatting removed: case, punctuation, '&' for 'and', 'Limited' for 'Ltd', a leading 'The'."""
    s = (name or '').casefold().replace('&', ' and ')
    s = re.sub(r'[^0-9a-z ]+', ' ', s)
    s = re.sub(r'\blimited\b', 'ltd', s)
    s = re.sub(r'\bpublic ltd company\b', 'plc', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'^the ', '', s)


def company_number(value) -> str | None:
    """A Companies House number in its canonical form, or None for a blank or malformed one (such as "0")."""
    raw = re.sub(r'\s+', '', str(value or '')).upper()
    if raw.isdigit() and 0 < len(raw) <= 8 and int(raw) > 0:
        return raw.zfill(8)
    return raw if re.fullmatch(r'(?:SC|NI|OC|SO|NC|R|IP|SP|RS|LP|SL|SE|FC|GE|GS|ES|NL|NF|NO|NP|NR|NZ|AC|ZC|SA|SF|SR|SZ|RC|IC|SI|NA|R0|CE|CS|GN|GF)\d{5,6}', raw) else None


def stem(name: str) -> str:
    """The name without branch or trading notes in brackets and without legal suffixes: to find look-alikes, never to merge."""
    s = re.sub(r'\([^)]*\)', ' ', name or '')
    s = normalise(re.sub(r'\s[-\u2013]\s*lot\s*\d+.*$', ' ', s, flags=re.I))
    return ' '.join(w for w in s.split() if w not in {'ltd', 'plc', 'llp', 'uk', 'group', 'and', 'lot'})


def region_of(postcode: str | None) -> str:
    m = re.match(r'^([A-Z]{1,2})\d', (postcode or '').strip().upper())
    return AREA_REGION.get(m.group(1), '') if m else ''


def scope_of(text: str) -> str:
    maintained, installed = bool(_MAINTENANCE.search(text)), bool(_INSTALL.search(text))
    return {(True, True): 'maintenance_and_installation', (True, False): 'maintenance', (False, True): 'installation'}.get((maintained, installed), 'not_stated')


def route_of(contract: MarketContract) -> str:
    if contract.fit == 'framework':
        return 'framework_appointment'
    facts = contract.facts or {}
    text = f"{contract.title} {facts.get('description') or ''}"
    return 'call_off' if facts.get('framework_stage') == 'call_off' or _CALL_OFF.search(text) or _VIA_FRAMEWORK.search(text) else 'direct_award'


def disciplines_of(contract: MarketContract) -> list[str]:
    facts = contract.facts or {}
    return sorted(families(contract.title) | families(facts.get('description') or ''))


def _release(raw: dict) -> dict:
    if isinstance(raw.get('releases'), list) and raw['releases']:
        return raw['releases'][0] if isinstance(raw['releases'][0], dict) else {}
    return raw


REGION_WORDS = {'north east': 'North East', 'north west': 'North West', 'yorkshire': 'Yorkshire and the Humber', 'east midlands': 'East Midlands',
                'west midlands': 'West Midlands', 'east of england': 'East of England', 'london': 'London', 'south east': 'South East',
                'south west': 'South West', 'scotland': 'Scotland', 'wales': 'Wales', 'northern ireland': 'Northern Ireland'}


def buyer_postcode(raw: dict) -> str:
    return buyer_location(raw)[0]


def buyer_location(raw: dict) -> tuple[str, str]:
    """(buyer postcode, region as the source publishes it) from a notice's buyer party."""
    rel = _release(raw or {})
    for party in rel.get('parties') or []:
        if isinstance(party, dict) and 'buyer' in (party.get('roles') or []):
            address = party.get('address') or {}
            return str(address.get('postalCode') or ''), str(address.get('region') or '')
    return '', ''


def region_from_text(text: str) -> str:
    """A published region field naming exactly one region; a field naming several says nothing about where."""
    found = {label for part in re.split(r'[,;/]', (text or '').lower()) for word, label in REGION_WORDS.items() if word in part.strip()}
    found -= {'East of England'} if {'East Midlands', 'East of England'} <= found and 'east of england' not in (text or '').lower() else set()
    return found.pop() if len(found) == 1 else ''


# ------------------------------------------------------------------ build

def fingerprint(db: Session) -> str:
    count, latest = db.execute(select(func.count(MarketContract.id), func.max(MarketContract.last_evaluated))
                               .where(MarketContract.fit.in_(RELEVANT_FIT))).one()
    awards = db.scalar(select(func.count(MarketAward.id))) or 0
    return hashlib.sha256(f'{BUILD}|{count}|{latest}|{awards}'.encode()).hexdigest()[:32]


def ensure_built(db: Session, now: datetime | None = None) -> dict:
    """Rebuild the shared contractor index when the Market Network's contracts have changed since the last build."""
    state = db.scalar(select(MarketSourceState).where(MarketSourceState.source_key == STATE_KEY))
    current = fingerprint(db)
    if state and state.cursor == current:
        return {'rebuilt': False}
    stats = rebuild(db, now)
    moment = now or datetime.now(UTC)
    if state is None:
        state = MarketSourceState(source_key=STATE_KEY, failure_count=0)
        db.add(state)
    state.cursor, state.last_checked_at, state.last_success_at = current, moment, moment
    db.flush()
    return {'rebuilt': True, **stats}


def _numbers_from_awards(db: Session, revision_ids: set[int]) -> dict[tuple[int, str], set[str]]:
    """(source revision, normalised supplier name) -> Companies House numbers its award rows publish."""
    out: dict[tuple[int, str], set[str]] = defaultdict(set)
    ids = sorted(revision_ids)
    for start in range(0, len(ids), 500):
        rows = db.execute(select(MarketAward.source_revision_id, MarketAward.supplier, MarketEntity.identifier_value)
                          .join(MarketEntity, MarketEntity.id == MarketAward.supplier_id)
                          .where(MarketAward.source_revision_id.in_(ids[start:start + 500]), MarketEntity.identifier_scheme == 'GB-COH')).all()
        for revision, supplier, number in rows:
            if supplier and company_number(number):
                out[(revision, normalise(clean_supplier(supplier)))].add(company_number(number))
    return out


def _locations(db: Session, revision_ids: set[int]) -> dict[int, tuple[str, str]]:
    out, ids = {}, sorted(revision_ids)
    for start in range(0, len(ids), 200):
        for rid, raw in db.execute(select(SourceRevision.id, SourceRevision.raw).where(SourceRevision.id.in_(ids[start:start + 200]))).all():
            out[rid] = buyer_location(raw if isinstance(raw, dict) else {})
    return out


def rebuild(db: Session, now: datetime | None = None) -> dict:
    moment = now or datetime.now(UTC)
    contracts = db.scalars(select(MarketContract).where(MarketContract.fit.in_(RELEVANT_FIT), MarketContract.lifecycle_status != 'no_longer_supported')
                           .order_by(MarketContract.id)).all()
    evidence = {c.id: [e.get('source_revision_id') for e in (c.facts or {}).get('evidence') or [] if isinstance(e.get('source_revision_id'), int)]
                for c in contracts}
    all_ids = {i for ids in evidence.values() for i in ids}
    award_numbers = _numbers_from_awards(db, all_ids)
    locations = _locations(db, all_ids)
    region_by_contract = {}
    for c in contracts:
        places = [locations.get(i, ('', '')) for i in evidence[c.id]]
        found = next((region_of(p) for p, _ in places if region_of(p)), '') or next((region_from_text(t) for _, t in places if region_from_text(t)), '')
        region_by_contract[c.id] = found or (c.nation if c.nation in ('Scotland', 'Wales', 'Northern Ireland') else '')

    # One record per (contract, supplier name), with any number the sources publish for exactly that name.
    records = []
    for c in contracts:
        facts = c.facts or {}
        suppliers = [clean_supplier(s) for s in facts.get('suppliers') or ([c.supplier] if c.supplier else []) if s and clean_supplier(s)]
        published = [n for n in (company_number(x) for x in facts.get('company_numbers') or []) if n]
        for name in dict.fromkeys(suppliers):
            norm = normalise(name)
            if not norm:
                continue
            numbers = set().union(*[award_numbers.get((rid, norm), set()) for rid in evidence[c.id]]) if evidence[c.id] else set()
            if not numbers and len(suppliers) == 1 and len(published) == 1:
                numbers = {published[0]}
            records.append({'contract': c, 'name': name, 'norm': norm, 'number': next(iter(numbers)) if len(numbers) == 1 else None,
                            'revision': evidence[c.id][0] if evidence[c.id] else None})
    numbers_by_name: dict[str, set[str]] = defaultdict(set)
    for r in records:
        if r['number']:
            numbers_by_name[r['norm']].add(r['number'])
    for r in records:
        if r['number']:
            r['key'], r['basis'] = f"coh:{r['number']}", 'company_number'
        elif len(numbers_by_name.get(r['norm'], ())) == 1:
            r['key'], r['basis'] = f"coh:{next(iter(numbers_by_name[r['norm']]))}", 'identical_legal_name'
        else:
            r['key'], r['basis'] = f"name:{r['norm']}", 'name_only'

    # Contractors keep their id (and first-seen date) across rebuilds; links and aliases are rebuilt from the records.
    existing = {c.key: c for c in db.scalars(select(AtlasContractor))}
    by_key: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_key[r['key']].append(r)
    registry = {company_number(e.identifier_value): e for e in db.scalars(select(MarketEntity).where(MarketEntity.identifier_scheme == 'GB-COH'))}
    parents = _groups(db)
    db.execute(delete(AtlasContractParty))
    db.execute(delete(AtlasAlias))
    db.execute(delete(AtlasIdentityConflict))
    for key in set(existing) - set(by_key):
        db.delete(existing[key])
    db.flush()
    contractors: dict[str, AtlasContractor] = {}
    for key, rows in by_key.items():
        number = key[4:] if key.startswith('coh:') else None
        names = Counter(r['name'] for r in rows)
        display = registry[number].name if number and number in registry else names.most_common(1)[0][0]
        row = existing.get(key) or AtlasContractor(key=key, first_seen=moment, display_name=display, identity_basis='', group={}, disciplines={}, nations={})
        row.display_name, row.company_number, row.built_at = display[:255], number, moment
        row.identity_basis = 'published_company_number' if number else 'name_only'
        row.group = parents.get(number, {}) if number else {}
        db.add(row)
        contractors[key] = row
    db.flush()
    seen_aliases, linked = set(), set()
    for key, rows in by_key.items():
        contractor = contractors[key]
        disciplines, nations = Counter(), Counter()
        for r in rows:
            c = r['contract']
            if (contractor.id, r['norm']) not in seen_aliases:
                seen_aliases.add((contractor.id, r['norm']))
                db.add(AtlasAlias(contractor_id=contractor.id, alias=r['name'][:255], normalised=r['norm'][:255], source='contract_supplier',
                                  source_revision_id=r['revision']))
            if (contractor.id, c.id) in linked:
                continue
            linked.add((contractor.id, c.id))
            families_ = disciplines_of(c)
            disciplines.update(families_)
            nations[c.nation or 'Not stated'] += 1
            text = f"{c.title} {(c.facts or {}).get('description') or ''}"
            db.add(AtlasContractParty(contractor_id=contractor.id, contract_id=c.id, supplier_name_seen=r['name'][:255], match_basis=r['basis'],
                                      customer_key=normalise(c.buyer)[:255], region=region_by_contract[c.id],
                                      disciplines=families_, scope=scope_of(text), route=route_of(c)))
        contractor.disciplines, contractor.nations = dict(disciplines), dict(nations)
        contractor.contract_count = len({c for (cid, c) in linked if cid == contractor.id})
    conflicts = 0
    for norm, numbers in numbers_by_name.items():
        if len(numbers) > 1:
            ids = sorted({contractors[f'coh:{n}'].id for n in numbers} | ({contractors[f'name:{norm}'].id} if f'name:{norm}' in contractors else set()))
            db.add(AtlasIdentityConflict(normalised=norm[:255], kind='two_numbers', names=sorted({r['name'] for r in records if r['norm'] == norm}),
                                         company_numbers=sorted(numbers), contractor_ids=ids, status='unresolved'))
            conflicts += 1
    stems: dict[str, set[str]] = defaultdict(set)
    for key in contractors:
        for r in by_key[key]:
            if stem(r['name']):
                stems[stem(r['name'])].add(key)
    similar = 0
    already = [{f'coh:{n}' for n in numbers} | {f'name:{norm}'} for norm, numbers in numbers_by_name.items() if len(numbers) > 1]
    for s_, keys in stems.items():
        if len(keys) > 1 and not any(keys <= group for group in already):
            rows = [contractors[k] for k in sorted(keys)]
            db.add(AtlasIdentityConflict(normalised=f'stem:{s_}'[:255], kind='similar_names', names=sorted({c.display_name for c in rows}),
                                         company_numbers=sorted({c.company_number for c in rows if c.company_number}), contractor_ids=sorted(c.id for c in rows),
                                         status='unresolved'))
            similar += 1
    db.flush()
    return {'contracts': len(contracts), 'contractors': len(contractors), 'links': len(linked), 'conflicts': conflicts, 'similar_names': similar,
            'with_company_number': sum(1 for k in contractors if k.startswith('coh:'))}


def _groups(db: Session) -> dict[str, dict]:
    """Company number -> its controlling company, only from a reviewed registry filing in the Market Network."""
    out = {}
    rows = db.execute(select(MarketRelationship, MarketEntity).join(MarketEntity, MarketEntity.id == MarketRelationship.subject_entity_id)
                      .where(MarketRelationship.relation_type == 'SIGNIFICANT_CONTROL_BY')).all()
    for rel, subject in rows:
        parent = db.get(MarketEntity, rel.object_entity_id)
        if subject.identifier_scheme == 'GB-COH' and parent is not None:
            out[str(subject.identifier_value).upper()] = {
                'parent_name': parent.name, 'parent_number': parent.identifier_value if parent.identifier_scheme == 'GB-COH' else None,
                'basis': 'Person with significant control, from a reviewed Companies House filing', 'source_revision_id': rel.source_revision_id,
                'note': "The parent's other companies are separate contractors: a group relationship does not share contracts or services."}
    return out


# ------------------------------------------------------------------ what a contract shows

def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _months(days: int) -> int:
    return max(1, round(days / 30.4))


def status_of(contract: MarketContract, route: str, today: date) -> dict:
    """What the published dates show today. None of these says a contract is, or is not, being delivered."""
    facts = contract.facts or {}
    if route == 'framework_appointment':
        return {'code': 'framework', 'label': 'Framework appointment', 'detail': 'An appointment to a framework is not a contract for work: call-offs are separate.'}
    end, estimated = _day(facts.get('published_end_date')), False
    if end is None and _day(facts.get('estimated_end_date')):
        end, estimated = _day(facts.get('estimated_end_date')), True
    latest = _day(facts.get('latest_end'))
    basis = ' (estimated from the published duration)' if estimated else ''
    if end is None:
        return {'code': 'term_not_published', 'label': 'Term not published', 'detail': 'The records do not give an end date.'}
    if end >= today:
        days = (end - today).days
        if latest and latest > end:
            return {'code': 'extension_possible', 'label': f'In term to {end}; extension possible to {latest}',
                    'detail': f"{facts.get('latest_end_basis') or 'A published extension option'}{basis}.", 'end': str(end), 'latest_end': str(latest)}
        if days <= HORIZON_DAYS:
            return {'code': 'end_approaching', 'label': f'Published end in {_months(days)} months ({end})', 'detail': f'End date{basis}.', 'end': str(end)}
        return {'code': 'in_term', 'label': f'In published term to {end}', 'detail': f'End date{basis}.', 'end': str(end)}
    if facts.get('replacement'):
        return {'code': 'replacement_identified', 'label': f'Published end passed ({end}); a newer similar notice exists',
                'detail': 'A title match, not a confirmed replacement.', 'end': str(end)}
    if latest and latest >= today:
        return {'code': 'extension_window', 'label': f'Initial term ended {end}; an extension could run to {latest}', 'detail': 'Whether it was extended is not published.',
                'end': str(end), 'latest_end': str(latest)}
    if (today - end).days <= LOOKBACK_DAYS:
        return {'code': 'end_passed_unknown', 'label': f'Published end passed ({end}): current status not established',
                'detail': 'It may have been extended, re-let below the advertising threshold, or stopped.', 'end': str(end)}
    return {'code': 'historical', 'label': f'Historical: published end {end}', 'detail': 'A past relationship, not evidence of a current one.', 'end': str(end)}


def value_of(facts: dict) -> dict | None:
    v = facts.get('value') or {}
    if v.get('framework_ceiling'):
        return {'amount': v['framework_ceiling'], 'kind': 'framework_ceiling', 'label': 'Framework ceiling', 'basis': 'The most all suppliers together may be paid: not this supplier\'s revenue.'}
    if v.get('published_total'):
        out = {'amount': v['published_total'], 'kind': 'published_total', 'label': 'Published award value', 'basis': v.get('basis') or 'As published.'}
        if v.get('estimated_annualised'):
            out['annual_estimate'] = v['estimated_annualised']
        return out
    if v.get('published_annual'):
        return {'amount': v['published_annual'], 'kind': 'published_annual', 'label': 'Published annual value', 'basis': v.get('basis') or 'As published.'}
    return None


def _sources(facts: dict) -> list[dict]:
    seen, out = set(), []
    for e in facts.get('evidence') or []:
        url = e.get('source_url')
        if url and url not in seen:
            seen.add(url)
            out.append({'label': f"{e.get('source') or 'Notice'} {e.get('record_key') or ''}".strip(), 'url': url, 'published': (e.get('published_at') or '')[:10]})
    return out


def timeline(contract: MarketContract, today: date) -> list[dict]:
    """Publication, contract and retrieval dates kept apart."""
    facts, events = contract.facts or {}, []
    for e in facts.get('evidence') or []:
        if e.get('published_at'):
            events.append({'date': e['published_at'][:10], 'event': f"{e.get('source') or 'Notice'} published", 'basis': 'publication date'})
    if facts.get('award_date'):
        events.append({'date': str(facts['award_date'])[:10], 'event': 'Award', 'basis': 'contract event'})
    if facts.get('start_date'):
        events.append({'date': str(facts['start_date'])[:10], 'event': 'Contract start', 'basis': 'contract event'})
    end = facts.get('published_end_date') or facts.get('estimated_end_date')
    if end:
        events.append({'date': str(end)[:10], 'event': 'End of published term' if facts.get('published_end_date') else 'Estimated end of term',
                       'basis': 'contract event' if facts.get('published_end_date') else 'calculated from the published duration'})
    if facts.get('latest_end'):
        events.append({'date': str(facts['latest_end'])[:10], 'event': 'Latest end with extensions', 'basis': facts.get('latest_end_basis') or 'published extension'})
    replacement = facts.get('replacement') or {}
    if isinstance(replacement, dict) and replacement.get('published'):
        events.append({'date': str(replacement['published'])[:10], 'event': f"Similar newer notice: {replacement.get('title') or ''}".strip(), 'basis': 'title match, not a confirmed replacement'})
    events.append({'date': contract.first_seen.date().isoformat(), 'event': 'First seen by SalesIntel', 'basis': 'retrieval'})
    return sorted(events, key=lambda e: e['date'])


def reasons(contract: MarketContract, supplier: str, status: dict) -> list[dict]:
    """Why this relationship may be worth investigating: facts, mechanism, other explanations, what would disprove it, what
    is missing, the commercial action and the next verification step. Never a probability."""
    facts = contract.facts or {}
    code = status['code']
    if code not in {'end_approaching', 'extension_possible', 'extension_window', 'end_passed_unknown', 'replacement_identified'}:
        return []
    first = (facts.get('evidence') or [{}])[0]
    known = [f"{contract.buyer} named {supplier} as supplier ({first.get('source') or 'a published notice'}, published {(first.get('published_at') or '')[:10] or 'date not recorded'})",
             status['label']]
    v = value_of(facts)
    if v:
        known.append(f"{v['label']}: £{v['amount']:,.0f}. {v['basis']}")
    checks = list(facts.get('contradictions') or []) + list(facts.get('checks') or [])
    base = {'facts': known, 'disconfirming': ['A published extension, or a new award to the same supplier, would close the window.'] + checks,
            'missing': ['Whether the buyer will extend, re-tender or call off from a framework', 'Who manages the contract day to day',
                        'How satisfied the buyer is: nothing published says either way']}
    if code == 'end_approaching':
        return [{**base, 'kind': code, 'title': 'The published term ends within 18 months',
                 'mechanism': 'Public buyers prepare an extension, a re-tender or a framework call-off before a maintenance term ends, usually 6 to 12 months ahead.',
                 'alternatives': ['An unpublished extension option may be used', 'The work may be called off from a framework without an open tender',
                                  'The service may move into a wider facilities contract'],
                 'action': 'Investigate the customer: confirm the route to market and who manages fire and security.',
                 'next_step': "Check the buyer's procurement pipeline or forward plan, then contact the procurement route on the notice."}]
    if code in {'extension_possible', 'extension_window'}:
        return [{**base, 'kind': code, 'title': 'An extension decision falls inside the window',
                 'mechanism': 'Before using an extension, buyers review cost and performance; that review is a legitimate moment to offer an alternative.',
                 'alternatives': ['The extension may already have been agreed without a published notice', 'The buyer may be satisfied and extend without review'],
                 'action': 'Investigate the customer before the extension decision.',
                 'next_step': 'Ask the procurement contact whether the extension has been taken up and when it is next reviewed.'}]
    if code == 'replacement_identified':
        replacement = facts.get('replacement') or {}
        return [{**base, 'kind': code, 'title': 'A newer notice with a similar title exists',
                 'mechanism': 'A successor procurement is the most direct opportunity, if it really replaces this contract.',
                 'alternatives': ['The newer notice may cover a different site, lot or service', 'It may be a separate, unrelated purchase'],
                 'action': 'Read the newer notice and confirm whether it replaces this contract.',
                 'next_step': f"Open the newer notice{(': ' + replacement.get('title')) if isinstance(replacement, dict) and replacement.get('title') else ''} and compare its scope with this one."}]
    return [{**base, 'kind': code, 'title': 'The published end passed without a published successor',
             'mechanism': 'Without a published successor the buyer may be running on an extension, a direct award or a contract below the advertising threshold: each is a conversation worth having.',
             'alternatives': ['It may have been extended or re-let without a notice we can see', 'The service may have stopped or moved in house'],
             'action': 'Investigate the customer and ask how the service is currently delivered.',
             'next_step': 'Ask the buyer who maintains the systems now and when that arrangement is next reviewed.'}]


def shadow_reasons(db: Session, customer_key: str) -> list[dict]:
    """Shadow Radar hypotheses about the same organisation, in the same structure."""
    from app.models.shadow import ShadowHypothesis, ShadowHypothesisRevision
    out = []
    rows = db.scalars(select(ShadowHypothesis).where(ShadowHypothesis.active.is_(True))).all()
    for row in rows:
        if normalise(row.entity_name) != customer_key or row.current_revision_id is None:
            continue
        revision = db.get(ShadowHypothesisRevision, row.current_revision_id)
        a = revision.assessment if revision else {}
        out.append({'kind': 'shadow_signal', 'key': f'sh:{row.id}', 'title': f"{a.get('sensor_name') or 'Shadow Radar'}: {a.get('state_label') or row.state}",
                    'facts': [e.get('label') for e in a.get('timeline') or [] if e.get('role') in ('anchor', 'supports') and e.get('label')][:4],
                    'mechanism': a.get('hypothesis') or '', 'alternatives': [x.get('explanation') for x in a.get('alternatives') or [] if x.get('explanation')],
                    'disconfirming': list(a.get('disconfirming') or []), 'missing': list(a.get('unknown') or []),
                    'action': 'Open the Shadow Radar lead to see its evidence timeline.', 'next_step': (a.get('alternatives') or [{}])[0].get('test') or ''})
    return out


def contract_view(contract: MarketContract, party: AtlasContractParty, supplier: str, today: date) -> dict:
    facts = contract.facts or {}
    status = status_of(contract, party.route, today)
    return {'key': f'mc:{contract.id}', 'id': contract.id, 'customer': contract.buyer, 'customer_key': party.customer_key, 'title': contract.title,
            'supplier': supplier, 'supplier_name_seen': party.supplier_name_seen, 'match': {'basis': party.match_basis, 'label': MATCH_LABEL[party.match_basis]},
            'services': [{'family': f, 'label': FAMILY_LABEL.get(f, f)} for f in party.disciplines], 'scope': {'code': party.scope, 'label': SCOPE_LABEL[party.scope]},
            'route': {'code': party.route, 'label': ROUTE_LABEL[party.route]}, 'nation': contract.nation, 'region': party.region,
            'region_approximate': bool(party.region), 'value': value_of(facts),
            'dates': {'published': facts.get('published'), 'start': facts.get('start_date'), 'end': facts.get('published_end_date'),
                      'estimated_end': facts.get('estimated_end_date'), 'latest_end': facts.get('latest_end'), 'extension_note': facts.get('extension_note')},
            'status': status, 'sources': _sources(facts), 'checks': list(facts.get('contradictions') or []) + list(facts.get('checks') or []),
            'timeline': timeline(contract, today), 'reasons': reasons(contract, supplier, status), 'first_seen': contract.first_seen.date().isoformat()}


# ------------------------------------------------------------------ profile and filters

def _profile_families(services: list[str]) -> set[str]:
    return {f for s in services for f in PROFILE_FAMILIES.get(s, {s})}


def own_company(name: str, company_name: str) -> bool:
    if OWN_GROUP.search(name or ''):
        return True
    own = normalise(company_name)
    return bool(own) and own.split(' ')[0] == normalise(name).split(' ')[0] and len(own.split(' ')[0]) > 3


def _matches(party: AtlasContractParty, contract: MarketContract, f: dict, today: date) -> bool:
    if f.get('discipline') and f['discipline'] not in party.disciplines:
        return False
    if f.get('nation') and contract.nation != f['nation']:
        return False
    if f.get('region') and party.region != f['region']:
        return False
    if f.get('ending_months'):
        end = _day((contract.facts or {}).get('published_end_date')) or _day((contract.facts or {}).get('estimated_end_date'))
        if end is None or end < today or (end - today).days > f['ending_months'] * 30.4:
            return False
    return True


def search(db: Session, q: str = '', *, discipline: str = '', nation: str = '', region: str = '', ending_months: int | None = None,
           limit: int = 25, today: date | None = None) -> dict:
    """Contractors and customers matching a name, with the contracts that meet the filters."""
    today = today or date.today()
    f = {'discipline': discipline, 'nation': nation, 'region': region, 'ending_months': ending_months}
    rows = db.execute(select(AtlasContractParty, MarketContract, AtlasContractor).join(MarketContract, MarketContract.id == AtlasContractParty.contract_id)
                      .join(AtlasContractor, AtlasContractor.id == AtlasContractParty.contractor_id)).all()
    term = normalise(q)
    aliases: dict[int, set[str]] = defaultdict(set)
    for contractor_id, norm in db.execute(select(AtlasAlias.contractor_id, AtlasAlias.normalised)).all():
        aliases[contractor_id].add(norm)
    by_contractor: dict[int, dict] = {}
    by_customer: dict[str, dict] = {}
    for party, contract, contractor in rows:
        if not _matches(party, contract, f, today):
            continue
        status = status_of(contract, party.route, today)['code']
        hit_contractor = not term or term in normalise(contractor.display_name) or any(term in a for a in aliases[contractor.id]) or term == (contractor.company_number or '').lower()
        hit_customer = not term or term in party.customer_key
        if hit_contractor:
            c = by_contractor.setdefault(contractor.id, {'id': contractor.id, 'name': contractor.display_name, 'company_number': contractor.company_number,
                                                         'identity_basis': contractor.identity_basis, 'contracts': 0, 'live': 0, 'ending_soon': 0,
                                                         'customers': set(), 'services': Counter()})
            c['contracts'] += 1
            c['live'] += status in {'in_term', 'end_approaching', 'extension_possible'}
            c['ending_soon'] += status in {'end_approaching', 'extension_possible', 'extension_window'}
            c['customers'].add(party.customer_key)
            c['services'].update(party.disciplines)
        if hit_customer:
            k = by_customer.setdefault(party.customer_key, {'key': party.customer_key, 'name': contract.buyer, 'contracts': 0, 'ending_soon': 0,
                                                             'suppliers': set(), 'services': Counter(), 'region': party.region, 'nation': contract.nation})
            k['contracts'] += 1
            k['ending_soon'] += status in {'end_approaching', 'extension_possible', 'extension_window'}
            k['suppliers'].add(contractor.display_name)
            k['services'].update(party.disciplines)

    def done(x: dict) -> dict:
        x = dict(x)
        x['services'] = [{'family': k, 'label': FAMILY_LABEL.get(k, k), 'contracts': n} for k, n in x['services'].most_common(4)]
        if 'customers' in x:
            x['customers'] = len(x['customers'])
        if 'suppliers' in x:
            x['suppliers'] = sorted(x['suppliers'])
        return x
    contractors = sorted(by_contractor.values(), key=lambda x: (-x['ending_soon'], -x['contracts'], x['name']))
    customers = sorted(by_customer.values(), key=lambda x: (-x['ending_soon'], -x['contracts'], x['name']))
    return {'contractors': [done(x) for x in contractors[:limit]], 'customers': [done(x) for x in customers[:limit]],
            'totals': {'contractors': len(contractors), 'customers': len(customers)}, 'filters': f}


# ------------------------------------------------------------------ records

def _relationship_view(r: AtlasRelationship) -> dict:
    return {'id': r.id, 'kind': r.kind, 'supplier': r.supplier_name, 'contractor_id': r.contractor_id, 'customer': r.customer_name, 'customer_key': r.customer_key,
            'intermediary': r.intermediary, 'services': [{'family': f, 'label': FAMILY_LABEL.get(f, f)} for f in r.services], 'sites_mentioned': r.sites_mentioned,
            'published_on': r.published_on, 'duration_stated': r.duration_stated, 'currency': r.currency, 'source': {'url': r.source_url, 'title': r.source_title,
            'type': r.source_type}, 'quote': r.quote, 'quote_verified': r.quote_verified, 'checks': r.checks, 'status': r.status, 'unknowns': r.unknowns,
            'first_seen': r.first_seen.date().isoformat(), 'retrieved': r.retrieved_at.date().isoformat(),
            'caveat': ('Reported by a public source; the contract terms are not published. ' +
                       ('A past relationship, not evidence of a current one.' if r.currency == 'historical' else 'Whether it is still current is not established.'))}


def _research(db: Session, kind_subject: tuple[str, str]) -> dict | None:
    from app.models.acquisition import ResearchJob
    direction, subject = kind_subject
    jobs = db.scalars(select(ResearchJob).where(ResearchJob.kind == 'atlas_relationships').order_by(ResearchJob.id.desc()).limit(40)).all()
    for job in jobs:
        params = job.params or {}
        if params.get('direction') == direction and normalise(params.get('subject') or '') == subject:
            return {'id': job.id, 'status': job.status, 'when': job.created_at.date().isoformat(), 'result': job.result or {},
                    'cost_cents': job.actual_cents}
    return None


def contractor_record(db: Session, contractor_id: int, *, prefs: dict | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    contractor = db.get(AtlasContractor, contractor_id)
    if contractor is None:
        raise LookupError('Contractor not found')
    prefs = prefs or {}
    aliases = db.scalars(select(AtlasAlias).where(AtlasAlias.contractor_id == contractor.id).order_by(AtlasAlias.alias)).all()
    conflicts = [c for c in db.scalars(select(AtlasIdentityConflict)) if contractor.id in (c.contractor_ids or [])]
    rows = db.execute(select(AtlasContractParty, MarketContract).join(MarketContract, MarketContract.id == AtlasContractParty.contract_id)
                      .where(AtlasContractParty.contractor_id == contractor.id)).all()
    contracts = [contract_view(c, p, contractor.display_name, today) for p, c in rows]
    order = {'end_approaching': 0, 'extension_possible': 1, 'extension_window': 2, 'replacement_identified': 3, 'end_passed_unknown': 4, 'in_term': 5,
             'term_not_published': 6, 'framework': 7, 'historical': 8}
    contracts.sort(key=lambda x: (order.get(x['status']['code'], 9), x['status'].get('end') or '9999'))
    norms = {a.normalised for a in aliases}
    relationships = db.scalars(select(AtlasRelationship).where((AtlasRelationship.contractor_id == contractor.id) | AtlasRelationship.supplier_key.in_(norms))
                               .order_by(AtlasRelationship.status, AtlasRelationship.customer_name)).all()
    yours = own_company(contractor.display_name, prefs.get('company_name') or '')
    wanted, territory = _profile_families(prefs.get('services') or []), set(prefs.get('territory') or [])
    worth = [] if yours else [c for c in contracts if c['reasons'] and (not wanted or wanted & {s['family'] for s in c['services']})
                              and (not territory or c['nation'] in territory or c['region'] in territory)]
    services = Counter(f for c in contracts for f in [s['family'] for s in c['services']])
    research = _research(db, ('contractor', normalise(contractor.display_name)))
    shown = [r for r in relationships if r.status != 'unsupported']
    return {
        'id': contractor.id, 'name': contractor.display_name, 'yours': yours,
        'identity': {'company_number': contractor.company_number, 'basis': contractor.identity_basis,
                     'basis_label': 'Companies House number published on the procurement records' if contractor.company_number else 'Name only: no company number published for this name',
                     'aliases': [{'name': a.alias, 'source': 'Supplier name on a published contract'} for a in aliases],
                     'group': contractor.group or None,
                     'conflicts': [{'kind': c.kind, 'names': c.names, 'company_numbers': c.company_numbers, 'contractor_ids': c.contractor_ids,
                                    'note': ('This name is published with more than one company number. They are kept apart until a person confirms which is which.'
                                             if c.kind == 'two_numbers' else
                                             'Similar names kept apart: a branch, trading name or different company can look alike. A person can confirm whether they are one company.')}
                                   for c in conflicts]},
        'services': [{'family': k, 'label': FAMILY_LABEL.get(k, k), 'contracts': n, 'basis': 'Named in the contract title or description'} for k, n in services.most_common()],
        'nations': contractor.nations, 'contracts': contracts, 'relationships': [_relationship_view(r) for r in shown],
        'unsupported_relationships': sum(1 for r in relationships if r.status == 'unsupported'),
        'worth_investigating': worth[:12],
        'coverage': {
            'public': f'{len(contracts)} published contract(s) from Find a Tender, Contracts Finder and Public Contracts Scotland. Sell2Wales and Northern Ireland sources are not yet collected.',
            'private': (f"Published case studies and announcements researched on {research['when']}." if research and research['status'] == 'succeeded'
                        else 'Published case studies and announcements not researched yet.'),
            'subcontracts': 'Subcontract and FM delivery links appear only where a source states them.',
            'regions': "Regions come from the buyer's postcode area (approximate at some boundaries), or the region the notice publishes when it names just one.",
            'values': 'Values are shown only as published, with their basis. A framework ceiling is never revenue.'},
        'research': research}


def customer_record(db: Session, customer_key: str, *, today: date | None = None) -> dict:
    today = today or date.today()
    rows = db.execute(select(AtlasContractParty, MarketContract, AtlasContractor).join(MarketContract, MarketContract.id == AtlasContractParty.contract_id)
                      .join(AtlasContractor, AtlasContractor.id == AtlasContractParty.contractor_id)
                      .where(AtlasContractParty.customer_key == customer_key)).all()
    relationships = db.scalars(select(AtlasRelationship).where(AtlasRelationship.customer_key == customer_key, AtlasRelationship.status != 'unsupported')).all()
    if not rows and not relationships:
        name = None
    else:
        name = rows[0][1].buyer if rows else relationships[0].customer_name
    contracts = [{**contract_view(c, p, k.display_name, today), 'contractor_id': k.id} for p, c, k in rows]
    contracts.sort(key=lambda x: x['status'].get('end') or '0000', reverse=True)
    live = [c for c in contracts if c['status']['code'] in {'in_term', 'end_approaching', 'extension_possible'}]
    reported = [_relationship_view(r) for r in relationships]
    if live:
        incumbent = {'state': 'published', 'label': 'Published supplier in term: ' + ', '.join(sorted({c['supplier'] for c in live}))}
    elif reported:
        incumbent = {'state': 'reported', 'label': 'Reported by a public source; current status not established: ' + ', '.join(sorted({r['supplier'] for r in reported}))}
    else:
        incumbent = {'state': 'unknown', 'label': 'Current supplier not publicly established'}
    return {'key': customer_key, 'name': name or customer_key, 'incumbent': incumbent, 'contracts': contracts, 'relationships': reported,
            'signals': shadow_reasons(db, customer_key), 'research': _research(db, ('customer', customer_key)),
            'coverage': 'Published contracts are searched automatically. Private relationships appear when you research them; most private maintenance contracts are never published.'}
