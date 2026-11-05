"""Resumable, page-atomic polling of the official Find a Tender feed.

Runs on demand or from the optional external worker; no background thread is
started by importing the application. Watermarks reflect completed windows, not
proof that all sector notices have been captured.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ingestion.market_find_tender import fetch_page, record_for_release
from app.ingestion.market_find_tender_radar import monitored
from app.models.market_network import MarketSourceState, SourceRevision
from app.services.market_network import ingest_market_release

SOURCE = 'find_a_tender'
OVERLAP = timedelta(minutes=5)
LEASE = timedelta(minutes=10)


class MonitorBusy(RuntimeError):
    """Another worker holds the source lease."""


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def run_find_tender_window(db: Session, *, max_pages: int = 2, client=None,
                           now: datetime | None = None, start_at: datetime | None = None) -> dict:
    if not 1 <= max_pages <= 10:
        raise ValueError('max_pages must be between 1 and 10')
    if now is not None and now.tzinfo is None or start_at is not None and start_at.tzinfo is None:
        raise ValueError('Timestamps must have a timezone')
    started = _utc(now or datetime.now(UTC))
    if start_at and _utc(start_at) >= started:
        raise ValueError('start_at must be before now')
    token = uuid4().hex
    if db.get(MarketSourceState, SOURCE) is None:
        db.add(MarketSourceState(source_key=SOURCE))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # another worker created the state
    result = db.execute(update(MarketSourceState).where(
        MarketSourceState.source_key == SOURCE,
        or_(MarketSourceState.lease_until.is_(None), MarketSourceState.lease_until < started)
    ).values(lease_token=token, lease_until=started + LEASE, last_checked_at=started).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise MonitorBusy('Find a Tender monitoring is already running')
    db.commit()
    db.expire_all()
    stats = {'incomplete': False, 'pages': 0, 'scanned': 0, 'matched': 0,
             'new': 0, 'changed': 0, 'historical': 0, 'unchanged': 0, 'invalid': 0}
    try:
        state = db.get(MarketSourceState, SOURCE)
        if state.window_from is None or state.window_to is None:
            state.window_from = _utc(state.watermark) - OVERLAP if state.watermark else _utc(start_at or (started - timedelta(days=1)))
            state.window_to = started
            state.cursor = None
            db.commit()
        for _ in range(max_pages):
            state = db.get(MarketSourceState, SOURCE)
            releases, next_cursor = fetch_page(updated_from=_utc(state.window_from), updated_to=_utc(state.window_to),
                                               cursor=state.cursor, client=client)
            page_time = _utc(now or datetime.now(UTC))
            # Renew atomically before writing the page; a worker whose lease
            # expired while fetching must not commit a stale checkpoint.
            renewed = db.execute(update(MarketSourceState).where(
                MarketSourceState.source_key == SOURCE, MarketSourceState.lease_token == token,
                MarketSourceState.lease_until >= page_time
            ).values(lease_until=page_time + LEASE).execution_options(synchronize_session=False))
            if renewed.rowcount != 1:
                raise MonitorBusy('Source lease expired during collection')
            db.expire_all()
            page_changes = 0
            for release in releases:
                record = record_for_release(release, page_time)
                if record is None:
                    stats['invalid'] += 1
                    continue
                # Previously retained records must be re-examined even if a correction
                # removes all sector terms; corrections must not silently vanish.
                known = db.scalar(select(SourceRevision.id).where(SourceRevision.source_key == SOURCE,
                                  SourceRevision.record_key == record['release_id'],
                                  SourceRevision.superseded_at.is_(None)).limit(1)) is not None
                if not monitored(release) and not known:
                    continue
                stats['matched'] += 1
                outcome = ingest_market_release(db, record)
                stats[outcome['state']] += 1
                if outcome['state'] in ('new', 'changed'):
                    page_changes += 1
            state = db.get(MarketSourceState, SOURCE)
            if state.lease_token != token:
                raise MonitorBusy('Source lease changed during collection')
            state.cursor = next_cursor
            state.last_success_at = page_time
            state.last_error = None
            state.failure_count = 0
            state.lease_until = page_time + LEASE
            if page_changes:
                state.last_new_at = page_time
            stats['pages'] += 1
            stats['scanned'] += len(releases)
            if not next_cursor:
                state.watermark = state.window_to
                state.window_from = state.window_to = None
            # The page data and checkpoint are committed together.
            db.commit()
            if not next_cursor:
                break
        stats['incomplete'] = bool(db.get(MarketSourceState, SOURCE).window_to)
        return stats
    except Exception as exc:
        db.rollback()
        state = db.get(MarketSourceState, SOURCE)
        if state and state.lease_token == token:
            # Store an operational error category, not untrusted response bodies or URLs.
            state.last_error = f'HTTP {exc.response.status_code}' if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
            state.failure_count = (state.failure_count or 0) + 1
            db.commit()
        raise
    finally:
        state = db.get(MarketSourceState, SOURCE)
        if state and state.lease_token == token:
            state.lease_token = None
            state.lease_until = None
            db.commit()
