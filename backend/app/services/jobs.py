"""Durable research jobs: queued in the database, claimed with a lease, retried, cancellable, costed.

A job survives a browser refresh and a server restart. A worker claims the next due job with a
compare-and-swap update and holds a lease while it runs. If the process dies, the lease expires and
another worker picks the job up again, up to `max_attempts`. Cancellation is checked between steps,
so a cancelled job makes no further provider call. The estimated maximum cost is reserved when the
job is created (see spend.py); the measured cost is settled when it ends.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
import secrets
import threading
from typing import Any, Callable

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.acquisition import ResearchJob
from app.services import spend
from app.tenancy import ORG, SYSTEM, USER

log = logging.getLogger(__name__)
ACTIVE = ('queued', 'running')
FINAL = ('succeeded', 'partial', 'failed', 'cancelled')


class Cancelled(Exception):
    pass


class Transient(Exception):
    """A failure worth retrying, such as a provider timeout."""


def now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def job_dict(job: ResearchJob) -> dict[str, Any]:
    return {'id': job.id, 'kind': job.kind, 'account_id': job.account_id, 'status': job.status, 'stage': job.stage, 'attempts': job.attempts,
            'max_attempts': job.max_attempts, 'cancel_requested': job.cancel_requested, 'estimated_cents': job.estimated_cents, 'actual_cents': job.actual_cents,
            'usage': job.usage, 'result': job.result, 'error': job.error, 'params': {k: v for k, v in job.params.items() if k != 'internal'},
            'created_at': job.created_at.isoformat(), 'finished_at': job.finished_at.isoformat() if job.finished_at else None}


def enqueue(db: Session, kind: str, *, account_id: int | None, params: dict, estimated_cents: int, user_id: int | None, reuse_days: int = 30,
            refresh: bool = False, per_account: bool = True) -> tuple[ResearchJob, bool]:
    """Create a job, or return the active or recent one for the same subject. Reserves its cost first.
    per_account=False is for jobs that answer one narrower question each (gap research): the caller keeps them idempotent."""
    same = select(ResearchJob).where(ResearchJob.kind == kind, ResearchJob.account_id == account_id) if account_id is not None and per_account else None
    if same is not None:
        active = db.scalar(same.where(ResearchJob.status.in_(ACTIVE)).order_by(ResearchJob.id.desc()))
        if active:
            return active, False
        recent = db.scalar(same.where(ResearchJob.status.in_(('succeeded', 'partial')), ResearchJob.finished_at >= now() - timedelta(days=reuse_days))
                           .order_by(ResearchJob.id.desc()))
        if recent and not refresh:
            return recent, False  # results are reused and linked to the account, not regenerated
    org = db.info.get(ORG) or 1
    day = spend.uk_today()
    if estimated_cents:
        spend.reserve(db, org, user_id, estimated_cents, day)  # refused before anything is queued or called
    moment = now()
    job = ResearchJob(requested_by=user_id, kind=kind, account_id=account_id, params={**params, 'internal': {'spend_day': day.isoformat()}},
                      status='queued', stage='Waiting to start', attempts=0, max_attempts=3, next_run_at=moment, cancel_requested=False,
                      estimated_cents=estimated_cents, reserved_cents=estimated_cents, actual_cents=0, usage={}, result={}, error='',
                      created_at=moment, updated_at=moment)
    db.add(job)
    db.flush()
    return job, True


def cancel(db: Session, job_id: int) -> ResearchJob:
    job = db.get(ResearchJob, job_id)
    if job is None:
        raise LookupError('Research not found')
    if job.status in FINAL:
        return job
    job.cancel_requested, job.updated_at = True, now()
    if job.status == 'queued':  # never started: nothing was spent
        _finish(db, job, 'cancelled', stage='Cancelled before it started')
    return job


def _finish(db: Session, job: ResearchJob, status: str, *, stage: str = '', error: str = '') -> None:
    job.status, job.finished_at, job.updated_at = status, now(), now()
    job.lease_token, job.lease_until = None, None
    if stage:
        job.stage = stage
    if error:
        job.error = error[:2000]
    if job.reserved_cents or job.actual_cents:
        internal = job.params.get('internal', {})
        day = datetime.fromisoformat(internal.get('spend_day', spend.uk_today().isoformat())).date()
        # A provider call cut off by a crash cannot be measured, so a recovered job is charged at least its estimate.
        charged = max(job.actual_cents, job.estimated_cents) if internal.get('interrupted') else job.actual_cents
        spend.settle(db, job.requested_by, job.reserved_cents, charged, day)
        job.reserved_cents = 0


def claim(engine, worker: str = '') -> tuple[int, int, str] | None:
    """Claim the next due job across workspaces. Returns (job id, workspace, lease token)."""
    lease = timedelta(seconds=get_settings().research_lease_seconds)
    with Session(engine) as db:
        db.info[SYSTEM] = True
        moment = now()
        due = or_(and_(ResearchJob.status == 'queued', ResearchJob.next_run_at <= moment),
                  and_(ResearchJob.status == 'running', ResearchJob.lease_until < moment))  # its worker stopped: recover it
        for job in db.scalars(select(ResearchJob).where(due).order_by(ResearchJob.next_run_at, ResearchJob.id).limit(5)):
            if job.attempts >= job.max_attempts:
                db.info[ORG] = job.organisation_id
                _finish(db, job, 'failed', stage='Stopped after repeated interruptions', error='The research was interrupted too many times.')
                db.commit()
                db.info.pop(ORG)
                continue
            token = secrets.token_hex(16)
            params = job.params if job.status == 'queued' else {**job.params, 'internal': {**job.params.get('internal', {}), 'interrupted': True}}
            won = db.execute(update(ResearchJob).where(ResearchJob.id == job.id, ResearchJob.status == job.status,
                                                       or_(ResearchJob.lease_token.is_(None), ResearchJob.lease_token == job.lease_token))
                             .values(status='running', lease_token=token, lease_until=moment + lease, attempts=ResearchJob.attempts + 1,
                                     started_at=moment, updated_at=moment, stage='Recovering after an interruption' if job.status == 'running' else 'Starting',
                                     params=params), execution_options={'synchronize_session': False})
            db.commit()
            if won.rowcount == 1:
                return job.id, job.organisation_id, token
    return None


class Run:
    """What a handler may do while it holds the lease."""

    def __init__(self, db: Session, job: ResearchJob, token: str):
        self.db, self.job, self.token = db, job, token
        self.meter = None  # set by a handler that calls a provider, so cost is recorded even on failure
        self.base_cents = job.actual_cents  # cost of earlier attempts

    def attach(self, meter) -> None:
        """Measure a provider for this job: cap it at the reservation and save usage after every call."""
        self.meter = meter
        if meter is not None:
            meter.ceiling_cents = self.job.estimated_cents
            meter.on_call = self.record_cost

    def record_cost(self) -> None:
        self.job.actual_cents, self.job.usage = self.base_cents + self.meter.cents, self.meter.summary()
        self.db.commit()

    def step(self, stage: str) -> None:
        """Record progress, renew the lease and stop if cancelled."""
        self.db.flush()  # keep what the handler has recorded before re-reading the job
        self.db.refresh(self.job)
        if self.job.lease_token != self.token:
            raise Cancelled('Another worker took over this research.')
        if self.job.cancel_requested:
            raise Cancelled('Cancelled')
        self.job.stage, self.job.updated_at = stage[:120], now()
        self.job.lease_until = now() + timedelta(seconds=get_settings().research_lease_seconds)
        self.db.commit()


HANDLERS: dict[str, Callable[[Run], dict]] = {}


def handler(kind: str):
    def register(fn):
        HANDLERS[kind] = fn
        return fn
    return register


def _record_spend(job: ResearchJob, run: Run) -> None:
    """Money spent before a failure or cancellation is still spent."""
    if run.meter is not None:
        job.actual_cents = max(job.actual_cents, run.base_cents + run.meter.cents)
        job.usage = run.meter.summary()


def run_one(engine) -> int | None:
    claimed = claim(engine)
    if claimed is None:
        return None
    job_id, org, token = claimed
    with Session(engine) as db:
        db.info[ORG] = org
        job = db.get(ResearchJob, job_id)
        db.info[USER] = job.requested_by
        run = Run(db, job, token)
        try:
            result = HANDLERS[job.kind](run)
            if db.scalar(select(ResearchJob.lease_token).where(ResearchJob.id == job_id)) != token:
                db.rollback()
                return job_id  # another worker took over; it will record the outcome
            job.result = result
            _finish(db, job, result.get('status', 'succeeded'), stage=result.get('stage', 'Complete'))
        except Cancelled as exc:
            db.rollback()
            job = db.get(ResearchJob, job_id)
            _record_spend(job, run)
            if job.lease_token == token:
                _finish(db, job, 'cancelled', stage=str(exc))
        except Transient as exc:
            db.rollback()
            job = db.get(ResearchJob, job_id)
            _record_spend(job, run)
            if job.attempts >= job.max_attempts:
                _finish(db, job, 'failed', stage='Failed after retries', error=str(exc))
            else:
                job.status, job.lease_token, job.lease_until = 'queued', None, None
                job.next_run_at, job.stage, job.error = now() + timedelta(seconds=5 * 2 ** job.attempts), 'Will retry shortly', str(exc)[:2000]
        except Exception as exc:  # never leave research spinning
            log.exception('research job %s failed', job_id)
            db.rollback()
            job = db.get(ResearchJob, job_id)
            _record_spend(job, run)
            _finish(db, job, 'failed', stage='Failed', error='The research stopped unexpectedly.' if not isinstance(exc, (ValueError, LookupError)) else str(exc))
        db.commit()
    return job_id


def drain(engine, limit: int = 20) -> int:
    """Run due jobs now (tests and the command-line worker)."""
    done = 0
    while done < limit and run_one(engine) is not None:
        done += 1
    return done


_worker_started = False


def start_inline_worker(engine, interval: float = 1.0) -> None:
    """A background thread in the API process. A separate worker process is the production choice."""
    global _worker_started
    if _worker_started or get_settings().research_worker != 'inline':
        return
    _worker_started = True
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            try:
                if run_one(engine) is None:
                    stop.wait(interval)
            except Exception:  # keep serving if one claim fails
                log.exception('research worker error')
                stop.wait(interval)
    threading.Thread(target=loop, name='salesintel-research-worker', daemon=True).start()
