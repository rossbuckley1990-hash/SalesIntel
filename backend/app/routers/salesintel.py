"""SalesIntel 2.0 workspace API: Today, Discover, Accounts, Engage and Deals."""
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.auth import Context, current_context, tenant_db
from app.models.prospect import ProspectSearch
from app.tenancy import hosted
from app.models.crm import Account, Contact, Draft, FunnelEvent, SavedView, Site
from app.services import si_core as core
from app.services import si_engage as engage
from app.idempotency import idempotent
from app.services import jobs, navigator, spend
from app.services import research_handlers  # noqa: F401  registers the job handlers
from app.services.ai_costs import ESTIMATE_CENTS, research_provider
from app.services.spend import SpendLimitReached
from app.tenancy import can



def permitted(request: Request, ctx: Context = Depends(current_context)) -> Context:
    """Enforced on every SalesIntel endpoint: reading needs crm.read, any change needs crm.write."""
    ctx.require('crm.read')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        ctx.require('crm.write')
    return ctx


router = APIRouter(prefix='/api/si', tags=['salesintel'], dependencies=[Depends(permitted)])


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


def run(db: Session, fn: Callable[[], Any]) -> Any:
    """Commit on success; turn domain errors into clear HTTP responses."""
    try:
        result = fn()
        db.commit()
        return result
    except (KeyError, IndexError):
        db.rollback()
        raise  # a programming error, not a missing record
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------- today and discover

@router.get('/today')
def today(db: Session = Depends(tenant_db)):
    return core.today_queue(db)


@router.get('/discover')
def discover(q: str = Query('', max_length=300), source: Literal['all', 'public', 'private'] = 'all', nation: str = Query('', max_length=40),
             service: str = Query('', max_length=40), status: Literal['active', 'all', 'new', 'watching', 'investigating', 'dismissed'] = 'active',
             category: str = Query('', max_length=40), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(tenant_db)):
    return core.discover(db, q=q, source=source, nation=nation, service=service, status=status, category=category, limit=limit, offset=offset)


class LeadStatus(Strict):
    status: Literal['new', 'watching', 'dismissed', 'investigating']


@router.post('/discover/{key}/status')
def lead_status(key: str, payload: LeadStatus, db: Session = Depends(tenant_db)):
    return run(db, lambda: core.set_status(db, key, payload.status) or {'key': key, 'status': payload.status})


class LinkRequest(Strict):
    account_id: int | None = None


@router.post('/discover/{key}/account')
def lead_account(key: str, payload: LinkRequest, db: Session = Depends(tenant_db)):
    def work():
        entity_type, entity_id = core.parse_key(key)
        account, link, created = core.link_source(db, entity_type, entity_id, payload.account_id)
        core.track(db, 'lead_investigated')
        return {'account_id': account.id, 'created': created, 'basis': link.basis, 'confirmed': link.confirmed}
    return run(db, work)


class WebResearch(Strict):
    query: str = Field(min_length=3, max_length=1000)


@router.post('/discover/research')
def web_research(payload: WebResearch, request: Request, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Find private-sector organisations for a brief. Runs as a durable job within today's spending limit."""
    ctx.require('research.run')
    if research_provider(get_settings()) is None:
        raise HTTPException(status_code=403, detail='Web research is switched off in demo mode, so no API credit is used.' if get_settings().app_env == 'demo'
                            else 'Web research is not configured here.')
    return run(db, lambda: idempotent(db, request.headers.get('idempotency-key'), 'research.prospects', payload.model_dump(), lambda: _start(
        db, ctx, 'prospect_search', None, {'query': payload.query})))


def _start(db: Session, ctx: Context, kind: str, account_id: int | None, params: dict, refresh: bool = False) -> dict:
    try:
        job, created = jobs.enqueue(db, kind, account_id=account_id, params=params, estimated_cents=ESTIMATE_CENTS[kind], user_id=ctx.user_id, refresh=refresh)
    except SpendLimitReached as exc:
        who = 'your own' if str(exc) == 'person' else "this workspace's"
        raise HTTPException(status_code=429, detail=f"This would exceed {who} AI spending limit for today, so nothing was started or charged."
                            if any(spend.limits()) else 'Paid research is switched off for this workspace until a spending limit is set.') from exc
    return jobs.job_dict(job) | {'reused': not created}


class PeopleSearch(Strict):
    refresh: bool = False


@router.post('/accounts/{account_id}/people-search')
def people_search(account_id: int, payload: PeopleSearch, request: Request, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Find the right people: roles, named people where sources support them, and legitimate business routes."""
    def work():
        if db.get(Account, account_id) is None:
            raise LookupError('Account not found')
        use_ai = research_provider(get_settings()) is not None and can(ctx.role, 'research.run')
        return _start(db, ctx, 'contact_navigator', account_id, {'use_ai': use_ai}, payload.refresh) if use_ai else \
            jobs.job_dict(jobs.enqueue(db, 'contact_navigator', account_id=account_id, params={'use_ai': False}, estimated_cents=0, user_id=ctx.user_id,
                                       refresh=payload.refresh)[0])
    return run(db, lambda: idempotent(db, request.headers.get('idempotency-key'), f'people.{account_id}', payload.model_dump(), work))


@router.get('/accounts/{account_id}/people')
def people(account_id: int, db: Session = Depends(tenant_db)):
    """Who to contact at this account, best route first, with the latest research."""
    def work():
        from app.models.acquisition import ResearchJob
        account = db.get(Account, account_id)
        if account is None:
            raise LookupError('Account not found')
        roles = navigator.choose_roles(db, account)
        latest = db.scalar(select(ResearchJob).where(ResearchJob.account_id == account_id, ResearchJob.kind == 'contact_navigator').order_by(ResearchJob.id.desc()))
        return {'roles': roles, 'routes': navigator.ranked(db, account, roles), 'job': jobs.job_dict(latest) if latest else None,
                'quality_labels': navigator.QUALITY_LABEL, 'partial_message': navigator.PARTIAL}
    return run(db, work)


@router.get('/research-jobs')
def research_jobs(account_id: int | None = Query(None), db: Session = Depends(tenant_db)):
    from app.models.acquisition import ResearchJob
    query = select(ResearchJob).order_by(ResearchJob.id.desc()).limit(20)
    if account_id is not None:
        query = query.where(ResearchJob.account_id == account_id)
    return {'items': [jobs.job_dict(j) for j in db.scalars(query)]}


@router.get('/research-jobs/{job_id}')
def research_job(job_id: int, db: Session = Depends(tenant_db)):
    from app.models.acquisition import ResearchJob
    def work():
        job = db.get(ResearchJob, job_id)
        if job is None:
            raise LookupError('Research not found')
        return jobs.job_dict(job)
    return run(db, work)


@router.post('/research-jobs/{job_id}/cancel')
def cancel_research(job_id: int, db: Session = Depends(tenant_db)):
    return run(db, lambda: jobs.job_dict(jobs.cancel(db, job_id)))


@router.get('/spend')
def spending(db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    return spend.today(db, ctx.user_id)


# ---------------------------------------------------------------- accounts

@router.get('/accounts')
def accounts(q: str = Query('', max_length=120), db: Session = Depends(tenant_db)):
    return {'items': core.accounts_list(db, q)}


class NewAccount(Strict):
    name: str = Field(min_length=2, max_length=255)
    sector: str | None = Field(None, max_length=160)
    region: str | None = Field(None, max_length=160)
    website: str | None = Field(None, max_length=512)


@router.post('/accounts')
def create_account(payload: NewAccount, request: Request, db: Session = Depends(tenant_db)):
    def work():
        return idempotent(db, request.headers.get('idempotency-key'), 'account.create', payload.model_dump(), create)

    def create():
        found, basis = core.resolve_account(db, payload.name, None)
        if found:
            return {'account_id': found.id, 'created': False, 'basis': basis}
        moment = core.now()
        account = Account(name=payload.name.strip(), key=core.name_key(payload.name), kind='unknown', sector=payload.sector, region=payload.region, website=payload.website,
                          status='prospect', watched=False, notes='', created_at=moment, updated_at=moment)
        db.add(account)
        db.flush()
        core.track(db, 'account_created')
        return {'account_id': account.id, 'created': True, 'basis': 'user_entered'}
    return run(db, work)


@router.get('/accounts/{account_id}')
def account(account_id: int, db: Session = Depends(tenant_db)):
    return run(db, lambda: core.account_view(db, account_id))


class AccountUpdate(Strict):
    watched: bool | None = None
    notes: str | None = Field(None, max_length=5000)
    sector: str | None = Field(None, max_length=160)
    region: str | None = Field(None, max_length=160)
    website: str | None = Field(None, max_length=512)


@router.patch('/accounts/{account_id}')
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(tenant_db)):
    def work():
        row = db.get(Account, account_id)
        if not row:
            raise LookupError('Account not found')
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(row, key, value)
        if payload.watched is not None:
            row.watched_seen_at = core.now()
        row.updated_at = core.now()
        return core.account_view(db, account_id)
    return run(db, work)


@router.post('/accounts/{account_id}/seen')
def mark_seen(account_id: int, db: Session = Depends(tenant_db)):
    def work():
        row = db.get(Account, account_id)
        if not row:
            raise LookupError('Account not found')
        row.watched_seen_at = core.now()
        return {'ok': True}
    return run(db, work)


@router.get('/accounts/{account_id}/suggestions')
def account_suggestions(account_id: int, db: Session = Depends(tenant_db)):
    def work():
        row = db.get(Account, account_id)
        if not row:
            raise LookupError('Account not found')
        return {'items': core.suggestions(db, row)}
    return run(db, work)


class ConfirmLink(Strict):
    source_key: str = Field(max_length=40)


@router.post('/accounts/{account_id}/links')
def confirm_link(account_id: int, payload: ConfirmLink, db: Session = Depends(tenant_db)):
    def work():
        entity_type, entity_id = core.parse_key(payload.source_key)
        account, link, _ = core.link_source(db, entity_type, entity_id, account_id)
        if account.id != account_id:
            raise ValueError('That record is already linked to another account.')
        return {'account_id': account.id, 'basis': link.basis}
    return run(db, work)


class NewContact(Strict):
    name: str | None = Field(None, max_length=180)
    role: str | None = Field(None, max_length=240)
    email: str | None = Field(None, max_length=255, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    phone: str | None = Field(None, max_length=40)
    label: str | None = Field(None, max_length=160)
    source_url: str | None = Field(None, max_length=2048)
    influence: Literal['', 'decision_maker', 'influencer', 'user', 'gatekeeper'] = ''
    verified: bool = False


@router.post('/accounts/{account_id}/contacts')
def add_contact(account_id: int, payload: NewContact, db: Session = Depends(tenant_db)):
    return run(db, lambda: core.contact_dict(engage.add_contact(db, account_id, payload.model_dump())))


class ContactStatus(Strict):
    status: Literal['unverified', 'verified', 'do_not_contact']


@router.patch('/contacts/{contact_id}')
def contact_status(contact_id: int, payload: ContactStatus, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    def work():
        contact = engage.update_contact(db, contact_id, payload.status)
        if payload.status == 'do_not_contact':
            navigator.suppress(db, contact, ctx.user_id)  # survives repeated research and new sources
        return core.contact_dict(contact)
    return run(db, work)


class NewSite(Strict):
    name: str = Field(min_length=2, max_length=255)
    address: str = Field('', max_length=1000)
    postcode: str | None = Field(None, max_length=12)
    uprn: str | None = Field(None, pattern=r'^\d{1,12}$')
    source_url: str | None = Field(None, max_length=2048)
    systems: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


@router.post('/accounts/{account_id}/sites')
def add_site(account_id: int, payload: NewSite, db: Session = Depends(tenant_db)):
    def work():
        if not db.get(Account, account_id):
            raise LookupError('Account not found')
        site = Site(account_id=account_id, name=payload.name, address=payload.address, postcode=payload.postcode, uprn=payload.uprn,
                    basis='published' if payload.source_url else 'user_entered', source_url=payload.source_url, systems=payload.systems, created_at=core.now())
        db.add(site)
        db.flush()
        return {'id': site.id}
    return run(db, work)


# ---------------------------------------------------------------- engage

class IntroRequest(Strict):
    contact_id: int | None = None
    source_key: str | None = Field(None, max_length=40)


@router.post('/accounts/{account_id}/introduction')
def introduction(account_id: int, payload: IntroRequest, db: Session = Depends(tenant_db)):
    return run(db, lambda: engage.prepare_introduction(db, account_id, contact_id=payload.contact_id, source_key=payload.source_key))


class DraftIn(Strict):
    subject: str = Field('', max_length=255)
    body: str = Field(min_length=1, max_length=20000)
    contact_id: int | None = None
    deal_id: int | None = None
    channel: Literal['email', 'call'] = 'email'
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    gaps: list[str] = Field(default_factory=list, max_length=20)


@router.post('/accounts/{account_id}/drafts')
def create_draft(account_id: int, payload: DraftIn, db: Session = Depends(tenant_db)):
    return run(db, lambda: core.draft_dict(engage.save_draft(db, account_id, payload.model_dump())))


class DraftEdit(Strict):
    subject: str | None = Field(None, max_length=255)
    body: str | None = Field(None, min_length=1, max_length=20000)
    contact_id: int | None = None


@router.patch('/drafts/{draft_id}')
def edit_draft(draft_id: int, payload: DraftEdit, db: Session = Depends(tenant_db)):
    def work():
        draft = db.get(Draft, draft_id)
        if not draft:
            raise LookupError('Draft not found')
        return core.draft_dict(engage.save_draft(db, draft.account_id, payload.model_dump(exclude_none=True), draft_id))
    return run(db, work)


@router.post('/drafts/{draft_id}/approve')
def approve(draft_id: int, db: Session = Depends(tenant_db)):
    return run(db, lambda: core.draft_dict(engage.approve_draft(db, draft_id)))


class FollowUp(Strict):
    title: str | None = Field(None, max_length=255)
    due_on: date | None = None
    complete_task_ids: list[int] = Field(default_factory=list, max_length=10)


class LogSent(Strict):
    sent_externally: bool
    follow_up: FollowUp | None = None


@router.post('/drafts/{draft_id}/log')
def log_sent(draft_id: int, payload: LogSent, request: Request, db: Session = Depends(tenant_db)):
    def work():
        return idempotent(db, request.headers.get('idempotency-key'), f'draft.log.{draft_id}', payload.model_dump(mode='json'), logged)

    def logged():
        activity, task = engage.log_draft_sent(db, draft_id, sent_externally=payload.sent_externally,
                                               follow_up=payload.follow_up.model_dump(mode='json') if payload.follow_up else None)
        return {'activity': core.activity_dict(activity), 'task': core.task_dict(task) if task else None}
    return run(db, work)


@router.get('/drafts')
def drafts(status: Literal['open', 'all'] = 'open', db: Session = Depends(tenant_db)):
    query = select(Draft).order_by(Draft.updated_at.desc())
    if status == 'open':
        query = query.where(Draft.status.in_(['draft', 'approved']))
    names = {a.id: a.name for a in db.scalars(select(Account))}
    return {'items': [core.draft_dict(d) | {'account': names.get(d.account_id)} for d in db.scalars(query)]}


class ActivityIn(Strict):
    kind: Literal['call', 'email', 'meeting', 'site_visit', 'note']
    direction: Literal['outbound', 'inbound', 'internal'] = 'outbound'
    summary: str = Field(min_length=1, max_length=5000)
    outcome: Literal['', 'connected', 'no_answer', 'left_message', 'interested', 'not_interested', 'meeting_booked', 'requirement_captured', 'call_back'] = ''
    requirements: str = Field('', max_length=5000)
    objections: str = Field('', max_length=5000)
    commitments: str = Field('', max_length=5000)
    contact_id: int | None = None
    deal_id: int | None = None
    occurred_at: datetime | None = None
    follow_up: FollowUp | None = None


@router.post('/accounts/{account_id}/activities')
def log_activity(account_id: int, payload: ActivityIn, request: Request, db: Session = Depends(tenant_db)):
    def work():
        return idempotent(db, request.headers.get('idempotency-key'), f'activity.{account_id}', payload.model_dump(mode='json'), logged)

    def logged():
        data = payload.model_dump(mode='json', exclude={'follow_up'})
        activity, task = engage.log_activity(db, account_id, data, payload.follow_up.model_dump(mode='json') if payload.follow_up else None)
        return {'activity': core.activity_dict(activity), 'task': core.task_dict(task) if task else None}
    return run(db, work)


class TaskIn(Strict):
    title: str = Field(min_length=1, max_length=255)
    due_on: date
    deal_id: int | None = None


@router.post('/accounts/{account_id}/tasks')
def add_task(account_id: int, payload: TaskIn, db: Session = Depends(tenant_db)):
    return run(db, lambda: core.task_dict(engage.add_task(db, account_id, payload.model_dump())))


@router.post('/tasks/{task_id}/complete')
def complete(task_id: int, db: Session = Depends(tenant_db)):
    return run(db, lambda: core.task_dict(engage.complete_task(db, task_id)))


class Reschedule(Strict):
    due_on: date


@router.patch('/tasks/{task_id}')
def reschedule(task_id: int, payload: Reschedule, db: Session = Depends(tenant_db)):
    return run(db, lambda: core.task_dict(engage.reschedule_task(db, task_id, payload.due_on.isoformat())))


# ---------------------------------------------------------------- deals

class Qualification(Strict):
    requirement: str = Field(min_length=3, max_length=2000)
    decision_maker: str = Field('', max_length=300)
    timing: str = Field('', max_length=300)
    budget: str = Field('', max_length=300)
    incumbent: str = Field('', max_length=300)
    drivers: str = Field('', max_length=1000)


class NewDeal(Strict):
    source_key: str | None = Field(None, max_length=40)
    title: str | None = Field(None, max_length=255)
    services: list[str] = Field(default_factory=list, max_length=8)
    work_type: str = Field('', max_length=32)
    qualification: Qualification
    next_step: str = Field('', max_length=1000)
    value_total: StrictStr | StrictInt | StrictFloat | None = None


@router.post('/accounts/{account_id}/deals')
def create_deal(account_id: int, payload: NewDeal, request: Request, db: Session = Depends(tenant_db)):
    return run(db, lambda: idempotent(db, request.headers.get('idempotency-key'), f'deal.create.{account_id}', payload.model_dump(),
                                      lambda: engage.deal_view(db, engage.create_deal(db, account_id, payload.model_dump()).id)))


@router.get('/deals')
def deals(db: Session = Depends(tenant_db)):
    return engage.deals_board(db)


@router.get('/deals/{deal_id}')
def deal(deal_id: int, db: Session = Depends(tenant_db)):
    return run(db, lambda: engage.deal_view(db, deal_id))


class DealUpdate(Strict):
    stage: str | None = Field(None, max_length=24)
    reason: str = Field('', max_length=2000)
    services: list[str] | None = Field(None, max_length=8)
    work_type: str | None = Field(None, max_length=32)
    next_step: str | None = Field(None, max_length=1000)
    value_total: StrictStr | StrictInt | StrictFloat | None = None
    seller_confidence: Literal['low', 'medium', 'high'] | None = None


@router.get('/deals/{deal_id}/assessment')
def deal_assessment(deal_id: int, db: Session = Depends(tenant_db)):
    """Can we win this? Fit, readiness and the seller's view, and a win rate only when history supports one."""
    from app.services.si_assess import assessment
    return run(db, lambda: assessment(db, deal_id))


@router.patch('/deals/{deal_id}')
def update_deal(deal_id: int, payload: DealUpdate, db: Session = Depends(tenant_db)):
    def work():
        from app.models.crm import DealRecord
        row = db.get(DealRecord, deal_id)
        if not row:
            raise LookupError('Deal not found')
        engage.update_terms(db, deal_id, services=payload.services, work_type=payload.work_type)
        if payload.next_step is not None:
            row.next_step = payload.next_step
        if payload.seller_confidence is not None:
            row.seller_confidence = payload.seller_confidence
        if payload.value_total is not None:
            row.value_total, row.value_basis = float(engage.money(payload.value_total, 'Deal value')), 'user_estimate'
        if payload.stage:
            engage.move_stage(db, deal_id, payload.stage, payload.reason)
        row.updated_at = core.now()
        return engage.deal_view(db, deal_id)
    return run(db, work)


class ScopeEntry(Strict):
    service: str = Field(max_length=32)
    field: str = Field(max_length=32)
    value: StrictStr | StrictInt | StrictFloat | None = None
    basis: Literal['surveyed', 'customer_stated', 'estimate'] | None = None


class ScopeIn(Strict):
    entries: list[ScopeEntry] = Field(max_length=80)


@router.put('/deals/{deal_id}/scope')
def scope(deal_id: int, payload: ScopeIn, db: Session = Depends(tenant_db)):
    return run(db, lambda: engage.update_scope(db, deal_id, [e.model_dump() for e in payload.entries]) and engage.deal_view(db, deal_id))


class QuoteIn(Strict):
    rates: dict[str, StrictStr | StrictInt | StrictFloat | None] = Field(default_factory=dict, max_length=60)


@router.post('/deals/{deal_id}/quote')
def quote(deal_id: int, payload: QuoteIn, db: Session = Depends(tenant_db)):
    return run(db, lambda: engage.build_quote(db, deal_id, payload.rates) and engage.deal_view(db, deal_id))


class Approval(Strict):
    reviewer: str = Field(min_length=2, max_length=120)


@router.post('/deals/{deal_id}/quote/approve')
def approve_quote(deal_id: int, payload: Approval, request: Request, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    key = request.headers.get('idempotency-key')
    if not hosted():
        return run(db, lambda: idempotent(db, key, f'quote.approve.{deal_id}', payload.model_dump(),
                                          lambda: engage.approve_quote(db, deal_id, payload.reviewer) and engage.deal_view(db, deal_id)))
    # Hosted: the approver is the signed-in person, never a typed name, and never the deal's owner.
    ctx.require('quote.approve')

    def work():
        from app.models.crm import DealRecord
        from app.tenancy import record
        deal = db.get(DealRecord, deal_id)
        if deal is None:
            raise LookupError('Deal not found')
        if deal.owner_user_id == ctx.user_id:
            raise HTTPException(status_code=403, detail='Someone other than the deal owner must approve its quotation.')
        engage.approve_quote(db, deal_id, ctx.name)
        record(db, 'approve', 'si_deals', deal_id, {'version': deal.quote.get('version')})
        return engage.deal_view(db, deal_id)
    return run(db, lambda: idempotent(db, key, f'quote.approve.{deal_id}', payload.model_dump(), work))


class OwnerChange(Strict):
    user_id: int


@router.patch('/accounts/{account_id}/owner')
def reassign_account(account_id: int, payload: OwnerChange, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Give an account, its open deals and its open follow-ups to another member of this workspace."""
    ctx.require('crm.assign')

    def work():
        from app.models.crm import DealRecord, Task
        from app.models.tenancy import Membership
        if hosted() and db.scalar(select(Membership).where(Membership.organisation_id == ctx.organisation_id, Membership.user_id == payload.user_id)) is None:
            raise LookupError('Member not found in this workspace')
        account = db.get(Account, account_id)
        if account is None:
            raise LookupError('Account not found')
        account.owner_user_id = payload.user_id
        for deal in db.scalars(select(DealRecord).where(DealRecord.account_id == account_id, DealRecord.stage.not_in(['won', 'lost']))):
            deal.owner_user_id = payload.user_id
        for task in db.scalars(select(Task).where(Task.account_id == account_id, Task.status == 'open')):
            task.assignee_user_id = payload.user_id
        return {'account_id': account_id, 'owner_user_id': payload.user_id}
    return run(db, work)


# ---------------------------------------------------------------- settings, views and measurement

@router.get('/preferences')
def get_preferences(db: Session = Depends(tenant_db)):
    return core.preferences(db)


class PreferencesIn(Strict):
    territory: list[str] | None = Field(None, max_length=10)
    services: list[str] | None = Field(None, max_length=10)
    sectors: list[str] | None = Field(None, max_length=12)
    deal_size_min: StrictStr | StrictInt | None = None
    deal_size_max: StrictStr | StrictInt | None = None
    capabilities: list[str] | None = Field(None, max_length=20)
    company_name: str | None = Field(None, max_length=160)
    sender_name: str | None = Field(None, max_length=160)


@router.put('/preferences')
def put_preferences(payload: PreferencesIn, db: Session = Depends(tenant_db)):
    return run(db, lambda: core.set_preferences(db, payload.model_dump(exclude_none=True)))


@router.get('/saved-views')
def saved_views(db: Session = Depends(tenant_db)):
    return {'items': [{'id': v.id, 'name': v.name, 'filters': v.filters} for v in db.scalars(select(SavedView).order_by(SavedView.name))]}


class ViewIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    filters: dict[str, str] = Field(default_factory=dict)


@router.post('/saved-views')
def save_view(payload: ViewIn, db: Session = Depends(tenant_db)):
    def work():
        allowed = {'q', 'source', 'nation', 'service', 'status', 'category'}
        view = SavedView(name=payload.name, filters={k: v for k, v in payload.filters.items() if k in allowed}, created_at=core.now())
        db.add(view)
        db.flush()
        return {'id': view.id, 'name': view.name, 'filters': view.filters}
    return run(db, work)


@router.delete('/saved-views/{view_id}')
def delete_view(view_id: int, db: Session = Depends(tenant_db)):
    def work():
        view = db.get(SavedView, view_id)
        if not view:
            raise LookupError('Saved view not found')
        db.delete(view)
        return {'ok': True}
    return run(db, work)


@router.get('/metrics')
def metrics(days: int = Query(30, ge=1, le=365), db: Session = Depends(tenant_db)):
    since = datetime.now(UTC).date() - timedelta(days=days)
    rows = db.execute(select(FunnelEvent.event, func.count()).where(FunnelEvent.day >= since).group_by(FunnelEvent.event)).all()
    return {'since': since.isoformat(), 'counts': {event: count for event, count in rows},
            'note': 'Counts of actions only. No people, accounts or content are recorded.'}
