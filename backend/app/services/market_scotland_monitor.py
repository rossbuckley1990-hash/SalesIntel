"""Ingest one Scottish public-procurement month atomically and idempotently."""
from datetime import UTC,datetime,timedelta
from uuid import uuid4
import httpx
from sqlalchemy import or_,select,update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.ingestion.market_scotland import fetch_month,record_for_release,_params
from app.ingestion.market_find_tender_radar import monitored
from app.models.market_network import MarketSourceState,SourceRevision
from app.services.market_network import ingest_market_release

SOURCE='public_contracts_scotland'
LEASE=timedelta(minutes=10)
# Pipeline, contract and award notices, above and below threshold.
LIVE_NOTICE_TYPES=(1,2,3,102,103)
ROLLOVER_DAYS=7


def run_scotland_month(db:Session, *, year:int, month:int, notice_type:int=3,
                       client=None, system_curl=False, now:datetime|None=None) -> dict:
    _params(year,month,notice_type)
    if now is not None and now.tzinfo is None: raise ValueError('Timestamp must have a timezone')
    started=(now or datetime.now(UTC)).astimezone(UTC)
    if (year,month)>(started.year,started.month): raise ValueError('Cannot collect a future month')
    state_key=f'pcs_{year}_{month:02d}_{notice_type}'
    for key in (SOURCE,state_key):
        if db.get(MarketSourceState,key) is None:
            db.add(MarketSourceState(source_key=key))
            try: db.commit()
            except IntegrityError: db.rollback()
    token=uuid4().hex
    leased=db.execute(update(MarketSourceState).where(MarketSourceState.source_key==SOURCE,
        or_(MarketSourceState.lease_until.is_(None),MarketSourceState.lease_until<started))
        .values(lease_token=token,lease_until=started+LEASE,last_checked_at=started).execution_options(synchronize_session=False))
    if leased.rowcount != 1:
        db.rollback(); raise RuntimeError('Public Contracts Scotland monitor is already running')
    db.commit(); db.expire_all()
    try:
        releases=fetch_month(year,month,notice_type,client=client,system_curl=system_curl)
        retrieved=(now or datetime.now(UTC)).astimezone(UTC)
        renewed=db.execute(update(MarketSourceState).where(MarketSourceState.source_key==SOURCE,
            MarketSourceState.lease_token==token,MarketSourceState.lease_until>=retrieved)
            .values(lease_until=retrieved+LEASE).execution_options(synchronize_session=False))
        if renewed.rowcount != 1: raise RuntimeError('Public Contracts Scotland lease expired')
        db.expire_all()
        stats={'scanned':len(releases),'matched':0,'new':0,'changed':0,'historical':0,'unchanged':0,'invalid':0}
        for release in releases:
            record=record_for_release(release,retrieved)
            if record is None:
                stats['invalid']+=1; continue
            known=db.scalar(select(SourceRevision.id).where(SourceRevision.source_key==SOURCE,
                SourceRevision.record_key==record['release_id'],SourceRevision.superseded_at.is_(None)).limit(1)) is not None
            if not monitored(release) and not known: continue
            stats['matched']+=1
            outcome=ingest_market_release(db,record)
            stats[outcome['state']]+=1
        month_state=db.get(MarketSourceState,state_key)
        source=db.get(MarketSourceState,SOURCE)
        for state in (month_state,source):
            state.last_checked_at=retrieved; state.last_success_at=retrieved; state.last_error=None; state.failure_count=0
            if stats['new'] or stats['changed']: state.last_new_at=retrieved
        month_state.window_from=datetime(year,month,1,tzinfo=UTC)
        month_state.window_to=datetime(year+1,1,1,tzinfo=UTC) if month==12 else datetime(year,month+1,1,tzinfo=UTC)
        month_state.watermark=month_state.window_to
        db.commit()
        return stats
    except Exception as exc:
        db.rollback(); source=db.get(MarketSourceState,SOURCE)
        if source and source.lease_token==token:
            source.last_error=f'HTTP {exc.response.status_code}' if isinstance(exc,httpx.HTTPStatusError) else type(exc).__name__
            source.last_checked_at=(now or datetime.now(UTC)).astimezone(UTC)
            source.failure_count=(source.failure_count or 0)+1
            month_state=db.get(MarketSourceState,state_key)
            month_state.last_error=source.last_error
            month_state.last_checked_at=source.last_checked_at
            month_state.failure_count=(month_state.failure_count or 0)+1
            db.commit()
        raise
    finally:
        source=db.get(MarketSourceState,SOURCE)
        if source and source.lease_token==token:
            source.lease_token=None; source.lease_until=None; db.commit()


def run_scotland_current(db:Session, *, client=None, system_curl=False, now:datetime|None=None) -> dict:
    """Collect this month and, just after a rollover, the end of last month.

    One failed notice type does not stop the others. The first failure is raised
    afterwards, so the worker backs off and the source is never reported healthy.
    """
    today=(now or datetime.now(UTC)).astimezone(UTC)
    months=[(today.year,today.month)]
    if today.day<=ROLLOVER_DAYS:
        months.append((today.year-1,12) if today.month==1 else (today.year,today.month-1))
    total={'incomplete':False,'scanned':0,'matched':0,'new':0,'changed':0,'historical':0,'unchanged':0,'invalid':0}
    failure=None
    for year,month in months:
        for notice_type in LIVE_NOTICE_TYPES:
            try:
                stats=run_scotland_month(db,year=year,month=month,notice_type=notice_type,client=client,system_curl=system_curl,now=now)
            except Exception as exc:
                failure=failure or exc
                continue
            for key,value in stats.items(): total[key]+=value
    if failure: raise failure
    return total
