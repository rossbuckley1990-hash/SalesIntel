"""Operate the UK renewal radar from the command line.

The scheduled worker does this unattended; these commands are for a first load,
an extended history pull or a one-off rebuild. Nothing here contacts a buyer.

Examples:
  python backend/scripts/renewal_radar.py --load --refresh --report
  python backend/scripts/renewal_radar.py --find-a-tender --tender-first-year 2021 --load --refresh
"""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
import json
import sys
import time

from app.db import Base, SessionLocal, engine
from app.ingestion.market_contracts_search import Budget, client as search_client, collect
from app.models.market_contract import MarketContract, MarketContractLink
from app.services.renewal_history import SEARCH_CACHE, fetch_tenders, import_checkpoints, load_json, load_tenders, save_json, weeks_between
from app.services.renewal_radar import radar_summary, refresh_if_due, stored_counts, write_report

TERMS = [{'cpvCodes': ['50413200', '50610000', '79711000']}, {'keyword': 'fire alarm'}, {'keyword': 'extinguisher'}, {'keyword': 'sprinkler'}, {'keyword': 'cctv'},
         {'keyword': 'intruder alarm'}, {'keyword': '"access control"'}, {'keyword': '"emergency lighting"'}]


def _half_years(first_year: int, today: date):
    for year in range(first_year, today.year + 1):
        for start, end in ((date(year, 1, 1), date(year, 6, 30)), (date(year, 7, 1), date(year, 12, 31))):
            if start <= today:
                yield start, min(end, today)


def _plan(today: date, first_year: int) -> list:
    """Early-stage notices first: they are few and matter most if the budget runs out."""
    stages = [({**term, 'types': ['Pipeline', 'PreProcurement']}, today - timedelta(days=730), today) for term in TERMS]
    return stages + [({**term, 'types': ['Contract'], 'statuses': ['Awarded']}, start, end) for term in TERMS for start, end in _half_years(first_year, today)]


def _key(criteria: dict, start: date, end: date) -> str:
    return json.dumps([criteria, start.isoformat(), end.isoformat()], sort_keys=True)


def fetch_search(cache: dict, today: date, first_year: int, max_requests: int):
    """Resume the Contracts Finder keyword sweep from its last complete window."""
    done = cache.setdefault('done', [])
    plan = [step for step in _plan(today, first_year) if _key(*step) not in set(done)]
    budget, error = Budget(requests_left=max_requests), None
    with search_client() as http:
        try:
            for criteria, start, end in plan:
                if budget.exhausted or budget.requests_left <= 0:
                    break
                found = collect(http, criteria, start, end, budget)
                if budget.exhausted:
                    break
                cache['notices'].update({x['id']: x for x in found})
                done.append(_key(criteria, start, end))
                save_json(cache, SEARCH_CACHE)
                time.sleep(1.5)
        except Exception as exc:
            error = type(exc).__name__
    cache['fetches'].append({'date': today.isoformat(), 'requests': budget.requests_made, 'truncated_hits': budget.truncated_hits, 'budget_exhausted': budget.exhausted, 'error': error})
    save_json(cache, SEARCH_CACHE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--fetch', action='store_true', help='Resume the Contracts Finder keyword sweep')
    parser.add_argument('--find-a-tender', action='store_true', help='Resume the Find a Tender weekly history')
    parser.add_argument('--load', action='store_true', help='Load checkpoints into MiSi; unchanged records are not duplicated')
    parser.add_argument('--refresh', action='store_true', help='Re-evaluate every stored record now')
    parser.add_argument('--report', action='store_true', help='Write the report and CSV from the database')
    parser.add_argument('--first-year', type=int, default=2021)
    parser.add_argument('--tender-first-year', type=int, default=2023)
    parser.add_argument('--max-requests', type=int, default=160)
    parser.add_argument('--tender-max-requests', type=int, default=6000)
    parser.add_argument('--today', type=date.fromisoformat, default=datetime.now(UTC).date())
    args = parser.parse_args()
    if args.fetch:
        fetch_search(load_json(SEARCH_CACHE, {'notices': {}, 'fetches': []}), args.today, args.first_year, args.max_requests)
    if args.find_a_tender:
        fetch_tenders(load_tenders(), args.today, list(weeks_between(date(args.tender_first_year, 1, 1), args.today)), args.tender_max_requests)
    Base.metadata.create_all(engine, tables=[MarketContract.__table__, MarketContractLink.__table__])
    real_now = datetime.now(UTC)
    now = real_now if args.today == real_now.date() else datetime(args.today.year, args.today.month, args.today.day, 12, tzinfo=UTC)
    with SessionLocal() as db:
        if args.load:
            print(json.dumps({'load': import_checkpoints(db)}), flush=True)
        if args.refresh:
            print(json.dumps({'refresh': refresh_if_due(db, now=now, force=True)}, default=str), flush=True)
        if args.report:
            print(json.dumps(write_report(db, today=args.today)), flush=True)
        print(json.dumps({'stored': stored_counts(db), 'by_category': radar_summary(db, now=now)['by_category']}), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
