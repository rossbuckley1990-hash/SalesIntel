"""Collect and load the historical procurement records the radar reads.

Contracts Finder keyword rows and Find a Tender weeks are held in resumable local
checkpoints, then loaded into market_source_revisions in the OCDS shape every
MiSi rule reads. Loading is idempotent, so unchanged history is never duplicated.
A record loaded from a checkpoint is a reduced copy of the published notice and
says so in x_misi_capture; its source_url remains the original notice.
"""
from __future__ import annotations
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import REPO_ROOT
from app.ingestion.market_contracts_search import Budget, client as search_client
from app.ingestion.market_find_tender_radar import collect_window, fetch_process, ingest, needs_process
from app.intelligence.renewal_radar import CORE_CPV, families
from app.models.market_network import MarketSourceState
from app.services.market_network import ingest_market_release

OUTPUT = REPO_ROOT / '.runtime' / 'renewal-radar'
SEARCH_CACHE = OUTPUT / 'notices.json'
TENDER_CACHE = OUTPUT / 'find-a-tender.json'
CAPTURE = 'renewal_radar_history'
HISTORY_STATE = 'find_a_tender_history'
SEARCH_URL = 'https://www.contractsfinder.service.gov.uk/Notice/'
BATCH = 250


def load_json(path: Path, empty: dict) -> dict:
    return json.loads(path.read_text()) if path.exists() else empty


def save_json(cache: dict, path: Path):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(cache))
    os.replace(temporary, path)


def load_tenders(path: Path = TENDER_CACHE) -> dict:
    return load_json(path, {'tenders': {}, 'processes': {}, 'planning': {}, 'done': [], 'fetches': []})


def weeks_between(first: date, today: date) -> Iterator[tuple[date, date]]:
    """Monday-aligned update windows, newest first, so recent notices arrive first."""
    start = today - timedelta(days=today.weekday())
    while start >= first:
        yield start, min(start + timedelta(days=6), today)
        start -= timedelta(days=7)


def fetch_tenders(cache: dict, today: date, plan: list[tuple[date, date]], max_requests: int, *, path: Path = TENDER_CACHE) -> dict:
    """Every stage week by week, then fill any award still missing its tender notice."""
    budget, http, error = Budget(requests_left=max_requests), search_client(), None
    with http:
        try:
            for number, (first, last) in enumerate(plan, 1):
                key = f'week:{first}'
                if key in cache['done']:
                    continue
                releases = collect_window(http, first, last, budget)
                if releases is None:
                    break
                for release in releases:
                    ingest(cache, release)
                if last < today:
                    cache['done'].append(key)
                save_json(cache, path)
                print(json.dumps({'week': str(first), 'step': f'{number}/{len(plan)}', 'requests': budget.requests_made, 'waits': budget.waits,
                                  'tenders': len(cache['tenders']), 'planning': len(cache['planning'])}), flush=True)
            wanted = [] if budget.exhausted else [ocid for ocid, record in cache['tenders'].items() if needs_process(record, today) and not cache['processes'].get(ocid, {}).get('checked')]
            print(json.dumps({'processes_to_check': len(wanted)}), flush=True)
            for number, ocid in enumerate(wanted, 1):
                releases = fetch_process(http, ocid, budget)
                if releases is None:
                    break
                for release in releases:
                    ingest(cache, release)
                cache['processes'].setdefault(ocid, {'checked': None, 'releases': []})['checked'] = today.isoformat()
                if number % 50 == 0:
                    save_json(cache, path)
        except Exception as exc:
            error = type(exc).__name__
            print(json.dumps({'stopped': error, 'detail': str(exc)[:200]}), flush=True)
    outcome = {'date': today.isoformat(), 'requests': budget.requests_made, 'waits': budget.waits, 'budget_exhausted': budget.exhausted,
               'weeks_complete': sum(f'week:{first}' in cache['done'] for first, _ in plan), 'weeks_planned': len(plan), 'error': error}
    cache['fetches'].append(outcome)
    save_json(cache, path)
    return outcome


def _stamp(day: str) -> str:
    return f'{day}T00:00:00Z' if day else ''


def _shared(buyer: str, region: str, postcode: str) -> dict:
    party = {'id': 'buyer', 'roles': ['buyer'], 'address': {'region': region, 'postalCode': postcode}}
    return {'buyer': {'id': 'buyer', 'name': buyer}, 'parties': [party], 'x_misi_capture': CAPTURE}


def _items(cpv: list[str]) -> list[dict]:
    return [{'id': str(n), 'classification': {'scheme': 'CPV', 'id': code}} for n, code in enumerate(cpv, 1)]


def _record(source: str, record_key: str, ocid: str, url: str, published: str, retrieved: datetime, raw: dict) -> dict | None:
    if not published:
        return None
    return {'source_key': source, 'release_id': record_key, 'ocid': ocid, 'source_url': url, 'retrieved_at': retrieved,
            'published_at': datetime.fromisoformat(published).replace(tzinfo=UTC), 'raw': raw}


def search_record(notice: dict, retrieved: datetime) -> dict | None:
    """A Contracts Finder search row in OCDS shape; the ocid is its notice id with the publisher prefix."""
    ocid, published = f"ocds-b5fd17-{notice['id']}", notice.get('published') or ''
    awarded = notice.get('type') == 'Contract' and notice.get('status') == 'Awarded'
    planning = notice.get('type') in {'Pipeline', 'PreProcurement'}
    if not awarded and not planning:
        return None
    status = 'withdrawn' if notice.get('status') == 'Withdrawn' else 'complete' if awarded else 'planned'
    tender = {'title': notice.get('title'), 'description': notice.get('description'), 'status': status, 'items': _items(notice.get('cpv') or [])}
    if notice.get('approach'):
        tender['tenderPeriod'] = {'startDate': _stamp(notice['approach'])}
        tender['communication'] = {'futureNoticeDate': _stamp(notice['approach'])}
    raw = {'ocid': ocid, 'id': notice['id'], 'date': _stamp(published), 'tag': ['award'] if awarded else ['planning'],
           **_shared(notice.get('buyer') or '', notice.get('region') or '', notice.get('postcode') or ''), 'x_misi_notice_type': notice.get('type'), 'tender': tender}
    if notice.get('value') and planning:
        tender['value'] = {'amount': notice['value'], 'currency': 'GBP'}
    if awarded:
        period = {k: _stamp(v) for k, v in (('startDate', notice.get('start')), ('endDate', notice.get('end'))) if v}
        raw['awards'] = [{'id': '1', 'status': 'active', 'suppliers': [{'name': x} for x in notice.get('suppliers') or []], 'contractPeriod': period,
                          **({'value': {'amount': notice['value'], 'currency': 'GBP'}} if notice.get('value') else {})}]
    return _record('contracts_finder', f"radar:{notice['id']}", ocid, notice.get('url') or SEARCH_URL + notice['id'], published, retrieved, raw)


def _tender_block(record: dict) -> dict:
    lots = [{'id': lot['id'], 'title': lot['title'], 'renewal': {'description': lot['renewal']} if lot['renewal'] else {},
             'contractPeriod': {k: v for k, v in (('startDate', _stamp(lot['start'])), ('endDate', _stamp(lot['end'])), ('durationInDays', lot['days'])) if v}}
            for lot in record['lots']]
    return {'title': record['title'], 'description': record['description'], 'status': record['status'], 'items': _items(record['cpv']), 'lots': lots,
            'techniques': {'hasFrameworkAgreement': bool(record.get('framework'))},
            **({'tenderPeriod': {'endDate': _stamp(record['deadline'])}} if record.get('deadline') else {})}


def _supplier_parties(awards: list) -> list[dict]:
    found = {}
    for award in awards or []:
        for supplier in award.get('suppliers') or []:
            supplier_id = str(supplier.get('id') or '')
            if supplier_id.startswith('GB-COH-'):
                found[supplier_id] = {'id': supplier_id, 'roles': ['supplier'], 'identifier': {'scheme': 'GB-COH', 'id': supplier_id.removeprefix('GB-COH-')}}
    return list(found.values())


def tender_records(cache: dict, retrieved: datetime) -> Iterator[dict]:
    """Find a Tender checkpoints as one tender record plus one record per award release."""
    for ocid, record in cache['tenders'].items():
        shared = _shared(record['buyer'], record.get('region') or '', record.get('postcode') or '')
        tender = _tender_block(record)
        if record['tender_seen']:
            url = f"https://www.find-tender.service.gov.uk/Notice/{record['release_id']}"
            raw = {'ocid': ocid, 'id': record['release_id'], 'date': _stamp(record['published']), 'tag': ['tender'], **shared, 'tender': tender}
            yield _record('find_a_tender', f"radar:{record['release_id']}", ocid, url, record['published'], retrieved, raw)
        for release in cache['processes'].get(ocid, {}).get('releases', []):
            day = (release.get('date') or '')[:10] or record['published']
            awards = release.get('awards') or []
            raw = {'ocid': ocid, 'id': release['id'], 'date': release.get('date') or _stamp(day), 'tag': ['award', 'contract'], **shared, 'tender': tender,
                   'awards': awards, 'contracts': release.get('contracts') or []}
            raw['parties'] = raw['parties'] + _supplier_parties(awards)
            yield _record('find_a_tender', f"radar:{release['id']}", ocid, f"https://www.find-tender.service.gov.uk/Notice/{release['id']}", day, retrieved, raw)
    for key, notice in cache['planning'].items():
        release_id = key.split(':', 1)[1]
        tender = {'title': notice['title'], 'description': notice['description'], 'status': 'withdrawn' if notice.get('status') == 'Withdrawn' else 'planned',
                  'items': _items(notice.get('cpv') or [])}
        if notice.get('approach'):
            tender['communication'] = {'futureNoticeDate': _stamp(notice['approach'])}
        if notice.get('value'):
            tender['value'] = {'amount': notice['value'], 'currency': 'GBP'}
        raw = {'ocid': notice['ocid'], 'id': release_id, 'date': _stamp(notice['published']), 'tag': ['planning'],
               **_shared(notice['buyer'], notice.get('region') or '', notice.get('postcode') or ''), 'tender': tender}
        yield _record('find_a_tender', f'radar:{release_id}', notice['ocid'], notice['url'], notice['published'], retrieved, raw)


def _sector(notice: dict) -> bool:
    return bool(families(f"{notice.get('title')} {notice.get('description') or ''}") or CORE_CPV & set(notice.get('cpv') or []))


def _checked_at(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC)


def import_checkpoints(db: Session, *, search_path: Path = SEARCH_CACHE, tender_path: Path = TENDER_CACHE) -> dict:
    """Load every checkpointed record not already stored, committing in small batches."""
    stats = {'scanned': 0, 'new': 0, 'changed': 0, 'unchanged': 0, 'historical': 0, 'skipped': 0, 'search_rows': 0, 'search_rows_outside_sector': 0}
    def load(records):
        pending = 0
        for record in records:
            stats['scanned'] += 1
            if record is None:
                stats['skipped'] += 1
                continue
            stats[ingest_market_release(db, record)['state']] += 1
            pending += 1
            if pending == BATCH:
                db.commit()
                pending = 0
        db.commit()
    if search_path.exists():
        rows = list(load_json(search_path, {'notices': {}})['notices'].values())
        kept = [x for x in rows if _sector(x)]
        stats['search_rows'], stats['search_rows_outside_sector'] = len(rows), len(rows) - len(kept)
        retrieved = _checked_at(search_path)
        load(search_record(x, retrieved) for x in kept)
    if tender_path.exists():
        cache = load_tenders(tender_path)
        load(tender_records(cache, _checked_at(tender_path)))
        record_history(db, cache)
    return stats


def record_history(db: Session, cache: dict):
    """Keep the Find a Tender coverage on MiSi's own source state, so limits stay visible."""
    weeks = sorted(x[5:] for x in cache['done'] if x.startswith('week:'))
    if not weeks:
        return
    state = db.get(MarketSourceState, HISTORY_STATE)
    if state is None:
        state = MarketSourceState(source_key=HISTORY_STATE)
        db.add(state)
    # Selective older weeks sit outside the unbroken run, so only that run counts as coverage.
    newest = date.fromisoformat(weeks[-1])
    run = newest
    while f'week:{run - timedelta(days=7)}' in cache['done']:
        run -= timedelta(days=7)
    now = datetime.now(UTC)
    state.window_from, state.window_to = datetime(run.year, run.month, run.day, tzinfo=UTC), datetime(newest.year, newest.month, newest.day, tzinfo=UTC)
    state.watermark = state.window_from
    state.cursor = json.dumps({'weeks_outside_run': [x for x in weeks if date.fromisoformat(x) < run], 'processes_checked': sum(1 for x in cache['processes'].values() if x.get('checked'))})
    state.last_checked_at = state.last_success_at = now
    db.commit()
