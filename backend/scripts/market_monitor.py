"""Run the Find a Tender market monitor once, or as a single-host periodic worker.

Example: python backend/scripts/market_monitor.py --watch --interval 900
Run as a supervised process; this command does not install or start a system service.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import threading

from app.config import REPO_ROOT
from app.db import SessionLocal
from app.services.market_monitor import run_find_tender_window


def retry_after_seconds(exc: Exception, now: datetime | None = None, *, include_403: bool = False) -> int:
    """Respect an upstream Retry-After without retaining or printing its body."""
    response = getattr(exc, 'response', None)
    statuses = (403, 429, 503) if include_403 else (429, 503)
    if response is None or getattr(response, 'status_code', None) not in statuses:
        return 0
    value = response.headers.get('Retry-After', '')
    try:
        seconds = int(value)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                return 0
            seconds = int((parsed - (now or datetime.now(UTC))).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 0
    return max(0, seconds)


def save_retry_deadline(path: Path, seconds: int, now: datetime | None = None) -> datetime:
    """Persist backoff so a supervisor restart cannot bypass a provider delay."""
    now = now or datetime.now(UTC)
    try:
        deadline = now + timedelta(seconds=seconds)
    except OverflowError:
        deadline = datetime.max.replace(tzinfo=UTC)
    tmp = path.with_name(path.name + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump({'retry_after': deadline.isoformat()}, output)
        output.flush()
        os.fsync(output.fileno())
    os.replace(tmp, path)
    return deadline


def load_retry_deadline(path: Path) -> datetime | None:
    try:
        data = json.loads(path.read_text())
        result = datetime.fromisoformat(data['retry_after'])
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError('Missing timezone')
        return result.astimezone(UTC)
    except FileNotFoundError:
        return None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        # Fail closed; a damaged backoff file must not cause an early retry.
        raise RuntimeError('Invalid persisted market monitor retry deadline') from exc


def refresh_intelligence(runtime: Path) -> dict | None:
    """Re-evaluate dated suggestions even when no new source record arrives.

    A local lock keeps this lightweight deterministic pass from overlapping
    across the separate source workers. The next poll retries if busy.
    """
    with (runtime / 'market-inference.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        from app.services.renewal_radar import refresh_if_due
        with SessionLocal() as db:
            return refresh_if_due(db)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true', help='Keep polling until stopped')
    parser.add_argument('--source', choices=('find-a-tender', 'contracts-finder', 'public-contracts-scotland', 'renewal-radar'), default='find-a-tender',
                        help='One source per worker, with independent checkpoint and backoff')
    parser.add_argument('--interval', type=int, default=900, help='Seconds between completed windows (minimum 60)')
    parser.add_argument('--max-pages', type=int, default=2, help='Maximum pages per batch (1–10)')
    parser.add_argument('--start-at', help='Initial backfill start in ISO 8601 with timezone; ignored once a checkpoint exists')
    args = parser.parse_args()
    if args.interval < 60 or not 1 <= args.max_pages <= 10:
        parser.error('interval must be at least 60 seconds and max-pages must be 1–10')
    start_at = None
    if args.start_at:
        try:
            start_at = datetime.fromisoformat(args.start_at.replace('Z', '+00:00'))
            if start_at.tzinfo is None or start_at.utcoffset() is None:
                raise ValueError('timezone required')
            start_at = start_at.astimezone(UTC)
            if start_at > datetime.now(UTC):
                raise ValueError('start must not be in the future')
        except ValueError:
            parser.error('start-at must be an ISO 8601 timestamp with timezone and not in the future')
    prefixes = {'find-a-tender': 'market-monitor', 'contracts-finder': 'market-contracts-monitor',
                'public-contracts-scotland': 'market-scotland-monitor', 'renewal-radar': 'market-renewal-radar'}
    prefix = prefixes[args.source]
    lock_path = REPO_ROOT / '.runtime' / (prefix + '.lock')
    retry_path = REPO_ROOT / '.runtime' / (prefix + '.retry.json')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another market monitor is already running on this host.', file=sys.stderr)
            return 2
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        failures = 0
        while not stop.is_set():
            try:
                deadline = load_retry_deadline(retry_path)
                while deadline and not stop.is_set():
                    remaining = (deadline - datetime.now(UTC)).total_seconds()
                    if remaining <= 0:
                        retry_path.unlink(missing_ok=True)
                        break
                    if not args.watch:
                        print('Market monitor is waiting for its persisted retry deadline.', file=sys.stderr)
                        return 1
                    stop.wait(min(remaining, 86400))
                if stop.is_set():
                    break
                with SessionLocal() as db:
                    if args.source == 'contracts-finder':
                        from app.services.market_contracts_monitor import run_contracts_finder_window
                        result = run_contracts_finder_window(db, max_pages=args.max_pages, start_at=start_at)
                    elif args.source == 'public-contracts-scotland':
                        from app.services.market_scotland_monitor import run_scotland_current
                        result = run_scotland_current(db, system_curl=True)
                    elif args.source == 'renewal-radar':
                        from app.services.market_inference import collect_all
                        from app.services.renewal_radar import run_daily_cycle
                        result = run_daily_cycle(db, refresh=False, collect=collect_all)
                    else:
                        result = run_find_tender_window(db, max_pages=args.max_pages, start_at=start_at)
                print(json.dumps({'time': datetime.now(UTC).isoformat(), 'result': result}, default=str), flush=True)
                # A separate transaction also ages out time-sensitive suggestions
                # when no source changes. Failure never invalidates collection.
                try:
                    update = refresh_intelligence(REPO_ROOT / '.runtime')
                    if update is not None:
                        print(json.dumps({'time': datetime.now(UTC).isoformat(), 'inference': update}, default=str), flush=True)
                    if args.source == 'renewal-radar':
                        from app.services.renewal_radar import ensure_report
                        with SessionLocal() as db:
                            ensure_report(db, today=datetime.now(UTC).date())
                except Exception as exc:
                    print(json.dumps({'time': datetime.now(UTC).isoformat(), 'inference_error': type(exc).__name__}), flush=True)
                failures = 0
                delay = 30 if result.get('incomplete') else args.interval
            except Exception as exc:
                # Details are recorded by the monitor; avoid logging credentials or arbitrary responses here.
                print(json.dumps({'time': datetime.now(UTC).isoformat(), 'error': type(exc).__name__}), flush=True)
                failures += 1
                if isinstance(exc, RuntimeError) and str(exc) == 'Invalid persisted market monitor retry deadline':
                    print('Invalid retry deadline; operator review is required.', file=sys.stderr)
                    return 1
                response = getattr(exc, 'response', None)
                cf_forbidden = args.source == 'contracts-finder' and getattr(response, 'status_code', None) == 403
                source_cooldown = getattr(exc, 'retry_after_seconds', 0)
                if not isinstance(source_cooldown, int) or source_cooldown < 0:
                    source_cooldown = 0
                delay = max(source_cooldown, retry_after_seconds(exc, include_403=cf_forbidden), 300 if cf_forbidden else 0,
                            min(3600, 60 * (2 ** min(failures - 1, 6))))
                save_retry_deadline(retry_path, delay)
                if not args.watch:
                    return 1
            if not args.watch:
                break
            stop.wait(min(delay, 86400))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
