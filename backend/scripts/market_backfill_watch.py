"""Supervised, bounded historical backfill for Contracts Finder and Scotland.

Checkpoints, shared source leases and the daily request budget are database
persisted. Existing source-specific live monitors continue independently.
"""
from __future__ import annotations
import argparse
from datetime import UTC,datetime
import json
import signal
import threading
import httpx
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from app.db import SessionLocal
from app.models.market_network import MarketSourceState
from app.services.market_contracts_monitor import SourceCooldown,run_contracts_finder_window
from app.services.market_scotland_monitor import run_scotland_month

BUDGET='market_backfill_budget'


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def candidates(db,first_year,last_year):
    """Return oldest incomplete annual CF and monthly PCS award windows."""
    states={s.source_key:s for s in db.scalars(select(MarketSourceState)).all()}
    cf=None
    for year in range(first_year,last_year+1):
        key=f'contracts_finder_backfill_{year}'
        state=states.get(key)
        end=datetime(year+1,1,1,tzinfo=UTC)
        if state is None or state.window_to is not None or state.watermark is None or utc(state.watermark)<end:
            cf=year; break
    pcs=None
    for year in range(first_year,last_year+1):
        for month in range(1,13):
            for notice_type in (3,103):
                state=states.get(f'pcs_{year}_{month:02d}_{notice_type}')
                if not state or (not state.last_success_at and (state.failure_count or 0)<3):
                    pcs=(year,month,notice_type); break
            if pcs: break
        if pcs: break
    return cf,pcs


def failed_windows(db,first_year,last_year):
    states=db.scalars(select(MarketSourceState).where(MarketSourceState.failure_count>=3)).all()
    expected={f'pcs_{year}_{month:02d}_{notice_type}' for year in range(first_year,last_year+1)
              for month in range(1,13) for notice_type in (3,103)}
    return [s.source_key for s in states if s.source_key in expected and not s.last_success_at]


def reserve_budget(db,daily_budget,now):
    """Atomically consume a request allowance; counts failures conservatively."""
    if db.get(MarketSourceState,BUDGET) is None:
        db.add(MarketSourceState(source_key=BUDGET))
        try: db.commit()
        except IntegrityError: db.rollback()
    for _ in range(5):
        db.expire_all()
        state=db.get(MarketSourceState,BUDGET)
        original=state.cursor
        try: value=json.loads(original) if original else {}
        except (ValueError,TypeError): value={}
        date=now.date().isoformat()
        count=value.get('count',0) if value.get('date')==date else 0
        if not isinstance(count,int) or count<0: count=0
        if count>=daily_budget: return False
        updated=json.dumps({'date':date,'count':count+1},separators=(',',':'))
        predicate=MarketSourceState.cursor.is_(None) if original is None else MarketSourceState.cursor==original
        result=db.execute(update(MarketSourceState).where(MarketSourceState.source_key==BUDGET,predicate)
                          .values(cursor=updated,last_checked_at=now).execution_options(synchronize_session=False))
        if result.rowcount:
            db.commit(); return True
        db.rollback()
    raise RuntimeError('Unable to reserve backfill budget')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from-year',type=int,default=2021)
    p.add_argument('--to-year',type=int,default=2025)
    p.add_argument('--interval',type=int,default=60,help='Minimum seconds between source calls (>=30)')
    p.add_argument('--daily-budget',type=int,default=96,help='Combined source requests per UTC day (1-500)')
    p.add_argument('--system-curl',action='store_true',help='Use system TLS transport for Scotland')
    a=p.parse_args()
    if not (2019<=a.from_year<=a.to_year<datetime.now(UTC).year): p.error('Choose completed years from 2019 to last year')
    if a.interval<30 or not 1<=a.daily_budget<=500: p.error('Interval must be >=30 seconds and daily budget 1-500')
    stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,lambda *_:stop.set())
    preferred='contracts_finder'
    while not stop.is_set():
        delay=a.interval
        try:
            with SessionLocal() as db:
                cf,pcs=candidates(db,a.from_year,a.to_year)
                if cf is None and pcs is None:
                    failed=failed_windows(db,a.from_year,a.to_year)
                    print(json.dumps({'status':'completed_with_failures' if failed else 'completed',
                                      'failed_windows':failed,'from_year':a.from_year,'to_year':a.to_year}),flush=True)
                    return 0
                source=preferred if (cf if preferred=='contracts_finder' else pcs) else ('public_contracts_scotland' if preferred=='contracts_finder' else 'contracts_finder')
                preferred='public_contracts_scotland' if source=='contracts_finder' else 'contracts_finder'
                if not reserve_budget(db,a.daily_budget,datetime.now(UTC)):
                    print(json.dumps({'status':'daily_budget_exhausted'}),flush=True)
                elif source=='contracts_finder':
                    result=run_contracts_finder_window(db,max_pages=1,start_at=datetime(cf,1,1,tzinfo=UTC),
                        end_at=datetime(cf+1,1,1,tzinfo=UTC),state_key=f'contracts_finder_backfill_{cf}')
                    print(json.dumps({'source':source,'year':cf,'result':result}),flush=True)
                else:
                    year,month,notice_type=pcs
                    result=run_scotland_month(db,year=year,month=month,notice_type=notice_type,system_curl=a.system_curl)
                    print(json.dumps({'source':source,'year':year,'month':month,'notice_type':notice_type,'result':result}),flush=True)
        except SourceCooldown as exc:
            # Wait no longer than one regular cycle; the other source may proceed next.
            print(json.dumps({'source':'contracts_finder','status':'cooldown','retry_after':exc.retry_after_seconds}),flush=True)
        except Exception as exc:
            # Source errors and checkpoints are persisted by the source collectors.
            status=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
            print(json.dumps({'status':'error','category':type(exc).__name__,'http_status':status}),flush=True)
            if status==403: delay=max(delay,300)
        # Bound waits so process termination is immediate.
        while delay>0 and not stop.is_set():
            step=min(delay,60); stop.wait(step); delay-=step
    return 0


if __name__=='__main__': raise SystemExit(main())
