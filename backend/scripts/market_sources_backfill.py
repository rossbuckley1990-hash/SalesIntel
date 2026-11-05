"""Run one bounded historical batch without disturbing live source checkpoints.

For Contracts Finder, repeat the same year until year_complete=true. An existing
checkpoint retains its fixed date range on resume. Public Contracts Scotland
is month-atomic, so repeating a month safely refreshes that month.
"""
import argparse
from datetime import UTC,datetime
import json
import sys
from app.db import SessionLocal
from app.models.market_network import MarketSourceState
from app.services.market_contracts_monitor import SourceCooldown,run_contracts_finder_window
from app.services.market_scotland_monitor import run_scotland_month


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',choices=['contracts-finder','scotland'])
    parser.add_argument('--year',type=int,required=True)
    parser.add_argument('--month',type=int,help='Required for Scotland')
    parser.add_argument('--notice-type',type=int,default=3,help='Scottish published notice type, default 3 (awards)')
    parser.add_argument('--max-pages',type=int,default=1,help='Contracts Finder pages per invocation, 1-10')
    parser.add_argument('--system-curl',action='store_true',help='Use OS curl TLS store for Scotland')
    args=parser.parse_args()
    now=datetime.now(UTC)
    if not 2019<=args.year<=now.year: parser.error('year must be 2019 through the current year')
    if args.source=='scotland' and (args.month is None or not 1<=args.month<=12): parser.error('Scotland requires --month 1-12')
    if args.source=='contracts-finder' and not 1<=args.max_pages<=10: parser.error('max-pages must be 1-10')
    try:
        with SessionLocal() as db:
            if args.source=='contracts-finder':
                start=datetime(args.year,1,1,tzinfo=UTC)
                end=min(datetime(args.year+1,1,1,tzinfo=UTC),now)
                state_key=f'contracts_finder_backfill_{args.year}'
                state=db.get(MarketSourceState,state_key)
                def aware(value):
                    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
                if state and state.window_to is None and state.watermark and aware(state.watermark)>=end:
                    result={'year_complete':True,'already_complete':True}
                else:
                    result=run_contracts_finder_window(db,max_pages=args.max_pages,start_at=start,end_at=end,state_key=state_key)
                    db.expire_all()
                    state=db.get(MarketSourceState,state_key)
                    result['year_complete']=bool(state and state.window_to is None and state.watermark and aware(state.watermark)>=end)
            else:
                result=run_scotland_month(db,year=args.year,month=args.month,notice_type=args.notice_type,system_curl=args.system_curl)
        print(json.dumps(result))
        return 0
    except SourceCooldown as exc:
        print(f'Contracts Finder cooldown: retry in at least {exc.retry_after_seconds} seconds.',file=sys.stderr)
        return 2
    except Exception as exc:
        # Avoid dumping source content, request headers, or secret values.
        print(f'Backfill failed: {type(exc).__name__}. See source health.',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
