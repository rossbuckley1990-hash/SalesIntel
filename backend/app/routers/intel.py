"""The daily intelligence layer: best opportunities, the customer profile, the guided play and buying committee for an
account, research on demand for its missing information, and what discovery led to."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Context, current_context, tenant_db
from app.config import get_settings
from app.idempotency import idempotent
from app.models.acquisition import ResearchJob
from app.models.gaps import GapRequest
from app.routers.salesintel import permitted, run
from app.services import best, gaps, jobs, plays
from app.services.ai_costs import research_provider
from app.services.spend import SpendLimitReached
from app.services.spend import refusal as spend_refusal
from app.tenancy import can

router = APIRouter(prefix='/api/si', tags=['intelligence'], dependencies=[Depends(permitted)])


@router.get('/best')
def best_opportunities(limit: int = 10, explore: int | None = None, db: Session = Depends(tenant_db)):
    return run(db, lambda: best.opportunities(db, limit=max(1, min(limit, 40)), explore_limit=None if explore is None else max(0, min(explore, 40))))


class Seen(BaseModel):
    model_config = ConfigDict(extra='forbid')
    keys: list[str] = Field(min_length=1, max_length=40)

    def model_post_init(self, _):
        import re
        if not all(re.fullmatch(r'(mo|pr|sh):\d{1,12}', k) for k in self.keys):
            raise ValueError('Unknown lead reference.')


@router.post('/best/seen')
def best_seen(payload: Seen, db: Session = Depends(tenant_db)):
    """The interface reports which leads were actually on screen. Only this counts as a lead being presented."""
    return run(db, lambda: {'recorded': best.seen(db, payload.keys)})


@router.get('/icp')
def icp(db: Session = Depends(tenant_db)):
    return best.profile(db)


@router.get('/results')
def results(db: Session = Depends(tenant_db)):
    return best.results(db)


def _sync(db: Session, rows: list[GapRequest]) -> None:
    """A request whose job failed or was cancelled says so, rather than spinning forever."""
    for r in rows:
        if r.status in gaps.OPEN and r.job_id:
            job = db.get(ResearchJob, r.job_id)
            if job and job.status in ('failed', 'cancelled'):
                r.status, r.summary = 'failed', job.error or ('Cancelled.' if job.status == 'cancelled' else 'The research did not complete.')


@router.get('/accounts/{account_id}/play')
def account_play(account_id: int, db: Session = Depends(tenant_db)):
    def work():
        _sync(db, db.scalars(select(GapRequest).where(GapRequest.account_id == account_id)).all())
        view = plays.view(db, account_id)
        for g in view['gaps']:
            if g['request'] and g['request'].get('job_id'):
                job = db.get(ResearchJob, g['request']['job_id'])
                g['request']['job'] = jobs.job_dict(job) if job else None
        return view
    return run(db, work)


class GapAsk(BaseModel):
    model_config = ConfigDict(extra='forbid')
    gap: Literal['find_role', 'verify_contact', 'incumbent', 'contract_end', 'site_operator', 'award_document', 'evaluation_criteria', 'site_status',
                 'need', 'package_status', 'eligibility', 'route', 'relationship_status', 'hypothesis_test']
    subject: str = Field(min_length=1, max_length=160)
    question: str = Field('', max_length=1000)
    lead_key: str | None = Field(None, pattern=r'^(sh|mo|pr|mc):\d+$')
    refresh: bool = False


@router.post('/accounts/{account_id}/gaps')
def resolve_gap(account_id: int, payload: GapAsk, request: Request, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Resolve this gap: start (or return) a scoped research request. Never answers from a guess."""
    def work():
        use_ai = research_provider(get_settings()) is not None and can(ctx.role, 'research.run')
        question = payload.question or next((q for g, s, q in sum(plays.GAPS.values(), []) if g == payload.gap and s == payload.subject),
                                            f"Who is the {payload.subject.lower()}, and how can they be reached?" if payload.gap == 'find_role'
                                            else 'Can this business contact detail be confirmed on an official page?' if payload.gap == 'verify_contact' else payload.subject)
        try:
            row, new = gaps.request(db, account_id, payload.gap, payload.subject, question, lead_key=payload.lead_key, user_id=ctx.user_id,
                                    use_ai=use_ai, refresh=payload.refresh)
        except SpendLimitReached as exc:
            raise HTTPException(**spend_refusal(exc)) from exc
        job = db.get(ResearchJob, row.job_id) if row.job_id else None
        return plays.request_dict(row) | {'reused': not new, 'job': jobs.job_dict(job) if job else None}
    return run(db, lambda: idempotent(db, request.headers.get('idempotency-key'), f'gap.{account_id}', payload.model_dump(), work))


@router.get('/gaps/{request_id}')
def gap_status(request_id: int, db: Session = Depends(tenant_db)):
    def work():
        row = db.get(GapRequest, request_id)
        if row is None:
            raise LookupError('Request not found')
        _sync(db, [row])
        job = db.get(ResearchJob, row.job_id) if row.job_id else None
        return plays.request_dict(row) | {'job': jobs.job_dict(job) if job else None}
    return run(db, work)


class Investigate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    refresh: bool = False


@router.post('/accounts/{account_id}/investigate')
def investigate_account(account_id: int, payload: Investigate, request: Request, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Investigate any account (public, private or Shadow Radar): a bounded, budgeted deep investigation that also tries to disprove itself."""
    from app.models.crm import Account
    from app.services import si_core as core
    from app.services.ai_costs import ESTIMATE_CENTS

    def work():
        if db.get(Account, account_id) is None:
            raise LookupError('Account not found')
        use_ai = research_provider(get_settings()) is not None and can(ctx.role, 'research.run')
        try:
            job, new = jobs.enqueue(db, 'deep_investigation', account_id=account_id, params={'hypothesis_key': None, 'use_ai': use_ai},
                                    estimated_cents=ESTIMATE_CENTS['deep_investigation'] if use_ai else 0, user_id=ctx.user_id, refresh=payload.refresh)
        except SpendLimitReached as exc:
            raise HTTPException(**spend_refusal(exc)) from exc
        if new:
            core.track(db, 'investigation_started', account_id=account_id, ref=f'job:{job.id}')
        return {'account_id': account_id, 'job': jobs.job_dict(job) | {'reused': not new}}
    return run(db, lambda: idempotent(db, request.headers.get('idempotency-key'), f'investigate.account.{account_id}', payload.model_dump(), work))


class BudgetApproval(BaseModel):
    model_config = ConfigDict(extra='forbid')
    amount_cents: int = Field(ge=100, le=100_000)  # $1 to $1,000 per approval
    note: str = Field('', max_length=500)


@router.get('/research-budget')
def research_budget(db: Session = Depends(tenant_db)):
    """The budget an administrator approved for live paid research, and what is committed against it."""
    from app.services import spend
    return spend.programme(db) | {'live_provider': spend.live_provider()}


@router.post('/research-budget')
def approve_research_budget(payload: BudgetApproval, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Approve (or top up) the hard ceiling for live paid research. Administrators only; recorded in the audit trail."""
    from app.services import spend
    from app.tenancy import record
    ctx.require('members.manage')

    def work():
        row = spend.approve(db, ctx.organisation_id, payload.amount_cents)
        record(db, 'budget_up', 'si_spend_budgets', row.id, {'added_cents': payload.amount_cents, 'note': payload.note})
        return spend.programme(db)
    return run(db, work)
