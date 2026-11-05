"""OCDS procurement notices reduced to the fields a renewal lead needs (OGL v3).

https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages
Find a Tender is read here, and the same reduction serves Contracts Finder and
Public Contracts Scotland releases stored by SalesIntel's monitors. Older award notices
omit contract dates, so an end date can be the tender notice's lot duration added
to the signature date; contract_terms marks that as an estimate. The API has no
keyword search, and its stages filter omits notices: on sampled days it returned
18 to 42 percent fewer tender notices than an unfiltered page. Every stage is
therefore paged together and routed by tag.
"""
from __future__ import annotations
from datetime import date, timedelta
import time

import httpx

from app.ingestion.find_a_tender import API_URL, MAX_RESPONSE_BYTES, _next_cursor
from app.ingestion.market_contracts_search import DESCRIPTION_LIMIT, Budget, _day, _text
from app.ingestion.market_find_tender import NOTICE_ID, OCID, relevant_release
from app.intelligence.contract_terms import award_term, framework_stage
from app.intelligence.renewal_radar import CORE_CPV, classify, clean_supplier, families

SOURCE = 'find_a_tender'
NOTICE_URL = 'https://www.find-tender.service.gov.uk/Notice/'
MAX_WAITS = 3
MAX_WAIT_SECONDS = 300
DEFAULT_WAIT_SECONDS = 30
LOOKBACK_DAYS = 2190
_INACTIVE = {'cancelled', 'unsuccessful', 'withdrawn'}
_ENDED = {'terminated', 'cancelled'}


STAGE_TAGS = {'planning': 'planning', 'planningupdate': 'planning', 'tender': 'tender', 'tenderupdate': 'tender', 'tenderamendment': 'tender',
              'tendercancellation': 'tender', 'award': 'award', 'awardupdate': 'award', 'awardcancellation': 'award', 'contract': 'award',
              'contractupdate': 'award', 'contractamendment': 'award', 'contracttermination': 'award'}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _iso(value):
    day = _day(value)
    return day.isoformat() if day else ''


def cpv_codes(tender: dict) -> list[str]:
    found = [tender.get('classification'), *_list(tender.get('additionalClassifications'))]
    for item in _list(tender.get('items')):
        found += [_dict(item).get('classification'), *_list(_dict(item).get('additionalClassifications'))]
    return sorted({str(x['id']).split('-')[0] for x in found if isinstance(x, dict) and x.get('id')})


def _full_text(tender: dict) -> str:
    parts = [tender.get('title'), tender.get('description')]
    for lot in _list(tender.get('lots')):
        parts += [_dict(lot).get('title'), _dict(lot).get('description')]
    return ' '.join(x for x in parts if isinstance(x, str))


def relevant(release: dict) -> bool:
    tender = _dict(release.get('tender'))
    return bool(families(_full_text(tender))) or bool(CORE_CPV & set(cpv_codes(tender)))


def monitored(release: dict) -> bool:
    """Whether a live monitor keeps a release: anything SalesIntel or the radar could use."""
    return relevant_release(release) or relevant(release)


def _lots(tender: dict) -> list[dict]:
    lots = _list(tender.get('lots')) or [{'id': '', 'contractPeriod': tender.get('contractPeriod')}]
    found = []
    for lot in lots:
        lot, period = _dict(lot), _dict(_dict(lot).get('contractPeriod'))
        days = period.get('durationInDays')
        found.append({'id': str(lot.get('id') or ''), 'title': _text(lot.get('title'), 200), 'start': _iso(period.get('startDate')),
                      'end': _iso(period.get('endDate')), 'days': days if isinstance(days, int) and days > 0 else None,
                      'renewal': _text(_dict(lot.get('renewal')).get('description'), 300)})
    return found


def _context(release: dict) -> dict:
    """The stored source of a release, or the Find a Tender notice it came from."""
    context = _dict(release.get('x_misi'))
    release_id = str(release.get('id'))
    return {'source': context.get('source') or SOURCE, 'url': context.get('url') or NOTICE_URL + release_id}


def _common(release: dict) -> dict | None:
    """Fields shared by every stage, or None when identifiers fail validation."""
    tender, buyer = _dict(release.get('tender')), _dict(release.get('buyer'))
    ocid, release_id = release.get('ocid'), release.get('id')
    title, name, published = _text(tender.get('title')), _text(buyer.get('name'), 250), _iso(release.get('date'))
    context = _context(release)
    # A stored record passed its source's own identifier checks when it was captured.
    stored = 'x_misi' in release and isinstance(ocid, str) and isinstance(release_id, str)
    if not stored and (not isinstance(ocid, str) or not OCID.fullmatch(ocid) or not isinstance(release_id, str) or not NOTICE_ID.fullmatch(release_id)):
        return None
    if not title or not name or not published:
        return None
    party = next((_dict(x) for x in _list(release.get('parties')) if _dict(x).get('id') == buyer.get('id')), {})
    address = _dict(party.get('address'))
    reference = _text(tender.get('id'), 120)
    return {'ocid': ocid, 'release_id': release_id, 'title': title, 'buyer': name, 'published': published,
            'description': _text(_full_text({**tender, 'title': None}), DESCRIPTION_LIMIT), 'cpv': cpv_codes(tender),
            'region': _text(address.get('region'), 120), 'postcode': _text(address.get('postalCode'), 12), **context,
            'buyer_id': _text(buyer.get('id'), 120), 'reference': '' if reference == ocid else reference,
            'route': _text(tender.get('procurementMethodDetails'), 120), 'approach': _iso(_dict(tender.get('tenderPeriod')).get('startDate'))}


def tender_record(release: dict) -> dict | None:
    common = _common(release)
    if common is None:
        return None
    tender = _dict(release.get('tender'))
    stage = framework_stage(release)[0]
    return {**common, 'updated': common['published'], 'tender_seen': True, 'status': _text(tender.get('status'), 40).lower(),
            'deadline': _iso(_dict(tender.get('tenderPeriod')).get('endDate')), 'framework_stage': stage or '',
            'framework': stage in {'framework_first_stage', 'conflicting_framework_flags'}, 'lots': _lots(tender)}


def planning_notice(release: dict) -> dict | None:
    common = _common(release)
    if common is None:
        return None
    tender = _dict(release.get('tender'))
    amount = _dict(tender.get('value'))
    value = amount.get('amount') if amount.get('currency') == 'GBP' else None
    withdrawn = _text(tender.get('status'), 40).lower() in _INACTIVE
    return {**{k: v for k, v in common.items() if k not in ('release_id', 'approach')}, 'id': f"{common['source']}:{common['release_id']}", 'type': 'Pipeline',
            'status': 'Withdrawn' if withdrawn else 'Planned', 'start': '', 'end': '', 'approach': _iso(_dict(tender.get('communication')).get('futureNoticeDate')),
            'value': float(value) if isinstance(value, (int, float)) and value > 0 else None, 'suppliers': []}


def _gbp(*values) -> float | None:
    """Pounds from an amount, or from the net or gross figure the 2023 Act notices use."""
    found = []
    for value in map(_dict, values):
        amount = next((value[k] for k in ('amount', 'amountNet', 'amountGross') if isinstance(value.get(k), (int, float)) and value[k] > 0), None)
        if amount and value.get('currency') == 'GBP':
            found.append(float(amount))
    return max(found) if found else None


def _company_number(supplier_id: str) -> str:
    return supplier_id.removeprefix('GB-COH-') if supplier_id.startswith('GB-COH-') else ''


def _reduced_tender(record: dict) -> dict:
    """The record's tender fields in the shape contract_terms reads."""
    lots = [{'id': lot['id'], 'renewal': {'description': lot['renewal']} if lot['renewal'] else {},
             'contractPeriod': {'startDate': lot['start'], 'endDate': lot['end'], 'durationInDays': lot['days']}} for lot in record['lots']]
    return {'tender': {'description': record['description'], 'lots': lots}}


def _award_slots(record: dict, releases: list[dict]) -> dict:
    """The latest published state of each lot, so an amendment replaces what it changed.

    Awards in one release share a lot's slot, which keeps a framework's suppliers
    together. Older releases only fill fields the newer ones leave empty.
    """
    lots = {lot['id']: lot for lot in record['lots']}
    only = record['lots'][0] if len(record['lots']) == 1 else None
    tender = _reduced_tender(record)
    slots, closed = {}, set()
    for release in sorted(releases, key=lambda x: str(x.get('date') or ''), reverse=True):
        contracts = {str(_dict(x).get('awardID')): _dict(x) for x in _list(release.get('contracts'))}
        for award in map(_dict, _list(release.get('awards'))):
            contract = contracts.get(str(award.get('id')), {})
            related = [str(x) for x in _list(award.get('relatedLots'))]
            lot = (lots.get(related[0]) if related else None) or only or {}
            key = lot.get('id', '')
            if key in closed:
                continue
            ended = str(contract.get('status') or '').lower() in _ENDED
            if str(award.get('status') or '').lower() in _INACTIVE or ended:
                if key not in slots:
                    closed.add(key)
                continue
            suppliers = [_dict(x) for x in _list(award.get('suppliers'))]
            names = [clean_supplier(_text(x.get('name'), 200)) for x in suppliers]
            names = [x for x in names if x]
            if not names:
                continue
            release_id = str(release.get('id'))
            slot = slots.setdefault(key, {'lot': lot, 'suppliers': [], 'supplier_ids': [], 'value': None, 'award_date': '', 'release_id': release_id,
                                          'url': _context(release)['url'], 'published': _iso(release.get('date')), 'award_id': str(award.get('id') or ''),
                                          'contract_id': str(contract.get('id') or ''), 'term': None})
            if slot['release_id'] == release_id:
                slot['suppliers'] = list(dict.fromkeys(slot['suppliers'] + names))
                slot['supplier_ids'] = list(dict.fromkeys(slot['supplier_ids'] + [str(x['id']) for x in suppliers if x.get('id')]))
            amount = _gbp(contract.get('value'), award.get('value'))
            slot['value'] = max(x for x in (slot['value'], amount, 0.0) if x is not None) or None
            slot['award_date'] = slot['award_date'] or _iso(contract.get('dateSigned')) or _iso(award.get('date'))
            term = award_term(tender, award, contract)
            if slot['term'] is None:
                slot['term'] = term
            else:
                held = slot['term']
                for field in ('start', 'latest_end', 'latest_end_basis', 'extension_note'):
                    held[field] = held[field] or term[field]
                held['has_extension'] = held['has_extension'] or term['has_extension']
                if term['end'] and not held['end']:
                    held.update(end=term['end'], end_basis=term['end_basis'], estimated_end='', end_estimated=False)
    return slots


def notices(record: dict, releases: list[dict], today: date) -> list[dict]:
    """One notice per awarded lot, or one for a tender still without an award."""
    if record['status'] in _INACTIVE:
        return []
    shared = {k: record.get(k, '') for k in ('ocid', 'title', 'buyer', 'description', 'cpv', 'region', 'postcode', 'framework', 'framework_stage', 'source',
                                             'buyer_id', 'reference', 'route')}
    market = record['published'] if record['tender_seen'] else record.get('approach', '')
    slots = _award_slots(record, releases)
    if not slots:
        if any(str(_dict(x).get('status') or '').lower() in _ENDED for release in releases for x in _list(release.get('contracts'))):
            return []
        deadline = _day(record['deadline'])
        return [{**shared, 'id': f"{record['source']}:{record['ocid']}", 'url': record['url'], 'lot': '', 'type': 'Contract',
                 'status': 'Open' if deadline and deadline >= today else 'Closed', 'published': record['published'], 'start': '', 'end': '',
                 'approach': market, 'deadline': record['deadline'], 'tender_status': record['status'], 'value': None, 'suppliers': []}]
    found = []
    for key, slot in slots.items():
        term, lot = slot['term'], slot['lot']
        title = f"{record['title']}: {lot['title']}" if lot.get('title') and len(record['lots']) > 1 else record['title']
        found.append({**shared, 'id': f"{record['source']}:{record['ocid']}:{key}", 'url': slot['url'], 'title': title, 'lot': key, 'type': 'Contract',
                      'status': 'Awarded', 'published': slot['published'] or record['published'], 'start': term['start'], 'end': term['end'] or term['estimated_end'],
                      'approach': market, 'value': slot['value'], 'suppliers': slot['suppliers'], 'supplier_ids': slot['supplier_ids'],
                      'company_numbers': [x for x in map(_company_number, slot['supplier_ids']) if x], 'award_id': slot['award_id'], 'contract_id': slot['contract_id'],
                      'award_date': slot['award_date'], 'end_estimated': term['end_estimated'], 'end_basis': term['end_basis'], 'start_basis': term['start_basis'],
                      'latest_end': term['latest_end'], 'latest_end_basis': term['latest_end_basis'], 'extension_note': term['extension_note'],
                      'has_extension': term['has_extension'], 'term_conflict': term['conflict']})
    return found


def stage_of(release: dict) -> str | None:
    """The latest stage a release reports, because award notices carry older tags too."""
    stages = {STAGE_TAGS.get(str(tag).lower()) for tag in _list(release.get('tag'))}
    return next((stage for stage in ('award', 'tender', 'planning') if stage in stages), None)


def merge_tender(existing: dict | None, record: dict) -> dict:
    """Keep the newest wording but the first date the work went to market."""
    if not existing or not existing['tender_seen']:
        return record
    newest, oldest = sorted((existing, record), key=lambda x: x['updated'], reverse=True)
    lots = newest['lots'] if any(lot['days'] or lot['end'] for lot in newest['lots']) else oldest['lots']
    return {**newest, 'published': oldest['published'], 'lots': lots, 'framework_stage': newest.get('framework_stage') or oldest.get('framework_stage', '')}


def ingest(cache: dict, release: dict):
    """Route one release into the cache by stage, keeping only what a lead needs."""
    stage = stage_of(release)
    if stage == 'planning':
        record = planning_notice(release)
        if record:
            cache['planning'][record['id']] = record
        return
    record = tender_record(release) if stage else None
    if record is None:
        return
    ocid = record['ocid']
    if stage == 'tender':
        cache['tenders'][ocid] = merge_tender(cache['tenders'].get(ocid), record)
        return
    cache['tenders'].setdefault(ocid, {**record, 'tender_seen': False})
    entry = cache['processes'].setdefault(ocid, {'checked': None, 'releases': []})
    if not any(x['id'] == release.get('id') for x in entry['releases']):
        entry['releases'].append({k: release.get(k) for k in ('id', 'date', 'awards', 'contracts', 'x_misi')})


def needs_process(record: dict, today: date) -> bool:
    """Spend a request only where a missing tender notice could supply the term."""
    if record['tender_seen'] or any(lot['days'] or lot['end'] for lot in record['lots']):
        return False
    if classify({**record, 'suppliers': [], 'start': '', 'end': ''})[0] == 'exclude':
        return False
    return date.fromisoformat(record['published']) >= today - timedelta(days=LOOKBACK_DAYS)


def _get(client, path: str, params: dict | None, budget: Budget, sleep):
    """One logical request, waiting as the documented Retry-After header asks."""
    for attempt in range(MAX_WAITS + 1):
        budget.requests_left -= 1
        budget.requests_made += 1
        response = client.get(API_URL + path, params=params)
        if response.status_code not in {429, 503} or attempt == MAX_WAITS:
            break
        retry = response.headers.get('Retry-After', '')
        budget.waits += 1
        sleep(min(int(retry), MAX_WAIT_SECONDS) if retry.isdigit() else DEFAULT_WAIT_SECONDS)
    response.raise_for_status()
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ValueError('Find a Tender page exceeded the response size limit')
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get('releases'), list):
        raise ValueError('Invalid Find a Tender release package')
    return payload


def collect_window(client, first: date, last: date, budget: Budget, *, pause: float = 1.5, sleep=time.sleep) -> list[dict] | None:
    """Relevant releases of every stage for one update window, or None if the budget ran out."""
    params, found, cursor = {'limit': 100, 'updatedFrom': f'{first}T00:00:00', 'updatedTo': f'{last}T23:59:59'}, [], None
    while True:
        if budget.requests_left <= 0:
            budget.exhausted = True
            return None
        payload = _get(client, '', {**params, 'cursor': cursor} if cursor else params, budget, sleep)
        found += [x for x in payload['releases'] if isinstance(x, dict) and relevant(x)]
        following = _next_cursor(payload.get('links'))
        if following and following == cursor:
            raise ValueError('Find a Tender returned a repeated pagination cursor')
        sleep(pause)
        if not following:
            return found
        cursor = following


def fetch_process(client, ocid: str, budget: Budget, *, pause: float = 1.5, sleep=time.sleep) -> list[dict] | None:
    """Every release for one process, or None if the budget ran out."""
    if not OCID.fullmatch(ocid):
        raise ValueError('Invalid procurement process identifier')
    if budget.requests_left <= 0:
        budget.exhausted = True
        return None
    try:
        payload = _get(client, f'/{ocid}', None, budget, sleep)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return []
    sleep(pause)
    return [x for x in payload['releases'] if isinstance(x, dict)]
