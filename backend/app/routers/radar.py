"""Shadow Radar for a workspace: inspect a hypothesis, investigate it, record what you learned, and see what it led to."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Context, current_context, tenant_db
from app.config import get_settings
from app.idempotency import idempotent
from app.intelligence.shadow_radar import registry
from app.models.acquisition import ResearchJob
from app.models.crm import Account, AccountLink, Activity, Contact, DealRecord
from app.models.shadow import Dossier, LeadFeedback, ShadowHypothesis
from app.routers.salesintel import permitted, run
from app.services import investigator, jobs, shadow
from app.services import si_core as core
from app.services.ai_costs import ESTIMATE_CENTS, research_provider
from app.services.spend import SpendLimitReached
from app.tenancy import can

router = APIRouter(prefix='/api/si/radar', tags=['shadow radar'], dependencies=[Depends(permitted)])
REASONS = {'not_our_service': 'Not a service we sell', 'outside_territory': 'Outside our territory', 'too_small': 'Too small', 'already_known': 'Already known to us',
           'wrong_organisation': 'Wrong organisation or site', 'evidence_wrong': 'The evidence does not say this', 'timing_wrong': 'Timing is wrong',
           'existing_supplier': 'Locked in with an existing supplier', 'other': 'Other'}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


@router.get('/sensors')
def sensors():
    """How the radar reasons: every sensor, its indicators, timing, rivals and what would disprove it."""
    return {'items': registry(), 'reasons': REASONS}


@router.get('/hypotheses/{hypothesis_id}')
def hypothesis(hypothesis_id: int, db: Session = Depends(tenant_db)):
    def work():
        found = shadow.current(db, hypothesis_id)
        if found is None:
            raise LookupError('Lead not found')
        row, a = found
        link = db.scalar(select(AccountLink).where(AccountLink.entity_type == 'shadow_hypothesis', AccountLink.entity_id == hypothesis_id))
        history = []
        if link:
            account = db.get(Account, link.account_id)
            acts = db.scalars(select(Activity).where(Activity.account_id == link.account_id).order_by(Activity.occurred_at.desc())).all()
            history = [{'kind': x.kind, 'summary': x.summary, 'outcome': x.outcome, 'occurred_at': x.occurred_at.isoformat()} for x in acts[:6]]
        else:
            account = None
        return {'id': row.id, 'key': f'sh:{row.id}', 'assessment': a, 'revisions': shadow.history(db, hypothesis_id), 'formed_at': row.formed_at.isoformat(),
                'account_id': account.id if account else None, 'relationship': history,
                'feedback': [{'decision': f.decision, 'reason': REASONS.get(f.reason, f.reason), 'note': f.note, 'at': f.created_at.isoformat()}
                             for f in db.scalars(select(LeadFeedback).where(LeadFeedback.lead_key == f'sh:{row.id}').order_by(LeadFeedback.id.desc()))]}
    return run(db, work)


class Investigate(Strict):
    refresh: bool = False


@router.post('/hypotheses/{hypothesis_id}/investigate')
def investigate(hypothesis_id: int, payload: Investigate, request: Request, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Open (or reuse) the account and start a deep investigation that tries to confirm and to disprove the hypothesis."""
    def work():
        found = shadow.current(db, hypothesis_id)
        if found is None:
            raise LookupError('Lead not found')
        account, _, created = core.link_source(db, 'shadow_hypothesis', hypothesis_id)
        use_ai = research_provider(get_settings()) is not None and can(ctx.role, 'research.run')
        try:
            job, new = jobs.enqueue(db, 'deep_investigation', account_id=account.id, params={'hypothesis_key': found[1]['key'], 'use_ai': use_ai},
                                    estimated_cents=ESTIMATE_CENTS['deep_investigation'] if use_ai else 0, user_id=ctx.user_id, refresh=payload.refresh)
        except SpendLimitReached as exc:
            raise HTTPException(status_code=429, detail='This would exceed today\'s AI spending limit, so nothing was started or charged.') from exc
        core.set_status(db, f'sh:{hypothesis_id}', 'investigating')
        if new:
            core.track(db, 'investigation_started', account_id=account.id, ref=f'job:{job.id}')
        return {'account_id': account.id, 'account_created': created, 'job': jobs.job_dict(job) | {'reused': not new}}
    return run(db, lambda: idempotent(db, request.headers.get('idempotency-key'), f'investigate.{hypothesis_id}', payload.model_dump(), work))


@router.get('/accounts/{account_id}/dossier')
def dossier(account_id: int, db: Session = Depends(tenant_db)):
    def work():
        if db.get(Account, account_id) is None:
            raise LookupError('Account not found')
        rows = db.scalars(select(Dossier).where(Dossier.account_id == account_id).order_by(Dossier.version.desc())).all()
        latest_job = db.scalar(select(ResearchJob).where(ResearchJob.account_id == account_id, ResearchJob.kind == 'deep_investigation').order_by(ResearchJob.id.desc()))
        return {'latest': investigator.dossier_view(rows[0]) if rows else None, 'versions': [{'version': r.version, 'verdict': r.verdict, 'created_at': r.created_at.isoformat()} for r in rows],
                'job': jobs.job_dict(latest_job) if latest_job else None, 'sections': investigator.SECTIONS}
    return run(db, work)


class Feedback(Strict):
    lead_key: str = Field(pattern=r'^(sh|mo|pr):\d+$')
    decision: Literal['relevant', 'not_relevant', 'disproved']
    reason: Literal['not_our_service', 'outside_territory', 'too_small', 'already_known', 'wrong_organisation', 'evidence_wrong', 'timing_wrong',
                    'existing_supplier', 'other', ''] = ''
    note: str = Field('', max_length=2000)


@router.post('/feedback')
def feedback(payload: Feedback, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Record whether a lead was worth it, and why not. Dismissing with a reason hides it for this workspace."""
    def work():
        if payload.decision != 'relevant' and not payload.reason:
            raise ValueError('Say why it was not relevant, so the radar can be evaluated honestly.')
        targets = [(payload.lead_key, '')]
        if payload.lead_key.startswith('sh:'):
            row = db.get(ShadowHypothesis, int(payload.lead_key[3:]))
            if row is None:
                raise LookupError('Lead not found')
            targets = [(payload.lead_key, row.sensor)]
            if payload.decision != 'relevant':
                # Competing hypotheses read from the same evidence share its fate: "outside our territory" is about the project.
                evidence = row.key.split('|', 1)[1]
                targets += [(f'sh:{x.id}', x.sensor) for x in db.scalars(select(ShadowHypothesis).where(ShadowHypothesis.key.like(f'%|{evidence}'), ShadowHypothesis.id != row.id))]
        for key, sensor in targets:
            db.add(LeadFeedback(lead_key=key, sensor=sensor, decision=payload.decision, reason=payload.reason, note=payload.note,
                                created_by=ctx.user_id, created_at=datetime.now(UTC)))
            if payload.decision in ('not_relevant', 'disproved'):
                core.set_status(db, key, 'dismissed')
        return {'recorded': True, 'lead_key': payload.lead_key, 'decision': payload.decision, 'also_applied_to': [k for k, _ in targets[1:]]}
    return run(db, work)


@router.get('/scorecard')
def scorecard(db: Session = Depends(tenant_db)):
    """What each sensor's leads led to in this workspace, from recorded outcomes only."""
    hypotheses = {h.id: h for h in db.scalars(select(ShadowHypothesis))}
    links = db.scalars(select(AccountLink).where(AccountLink.entity_type == 'shadow_hypothesis')).all()
    feedback = db.scalars(select(LeadFeedback).where(LeadFeedback.lead_key.like('sh:%'))).all()
    dossiers = db.scalars(select(Dossier).where(Dossier.hypothesis_key.is_not(None))).all()
    out = {}
    for key in {h.sensor for h in hypotheses.values()} | {f.sensor for f in feedback if f.sensor}:
        accounts = {l.account_id: hypotheses[l.entity_id] for l in links if l.entity_id in hypotheses and hypotheses[l.entity_id].sensor == key}
        acts = db.scalars(select(Activity).where(Activity.account_id.in_(list(accounts)))).all() if accounts else []
        deals = db.scalars(select(DealRecord).where(DealRecord.account_id.in_(list(accounts)))).all() if accounts else []
        contacts = db.scalars(select(Contact).where(Contact.account_id.in_(list(accounts)))).all() if accounts else []
        costs = db.scalars(select(ResearchJob).where(ResearchJob.account_id.in_(list(accounts)))).all() if accounts else []
        mine = [f for f in feedback if f.sensor == key]
        won = [d for d in deals if d.stage == 'won']
        lead_days = [(d.created_at.date() - accounts[d.account_id].first_published_on).days for d in deals if d.account_id in accounts]
        out[key] = {'leads': sum(1 for h in hypotheses.values() if h.sensor == key and h.active), 'investigated': len({d.account_id for d in dossiers if d.hypothesis_key and d.hypothesis_key.startswith(key + '|')}),
                    'marked_relevant': sum(1 for f in mine if f.decision == 'relevant'), 'dismissed': sum(1 for f in mine if f.decision == 'not_relevant'),
                    'disproved': sum(1 for f in mine if f.decision == 'disproved') + sum(1 for d in dossiers if d.verdict == 'weakened' and d.hypothesis_key.startswith(key + '|')),
                    'dismiss_reasons': {REASONS[r]: sum(1 for f in mine if f.reason == r) for r in REASONS if any(f.reason == r for f in mine)},
                    'contacts_verified': sum(1 for c in contacts if c.quality in ('public_source', 'provider_verified') or c.status == 'verified'),
                    'conversations': sum(1 for a in acts if a.outcome in ('connected', 'interested', 'meeting_booked', 'requirement_captured', 'call_back')),
                    'meetings': sum(1 for a in acts if a.outcome == 'meeting_booked'), 'requirements_confirmed': sum(1 for a in acts if a.outcome == 'requirement_captured'),
                    'qualified': len(deals), 'won': len(won), 'lost': sum(1 for d in deals if d.stage == 'lost'),
                    'won_value': {'total_contract_value': sum(d.value_total or 0 for d in won if d.value_basis in ('user_estimate', 'published')),
                                  'basis': 'Deal value recorded by the team (total contract value); margin is not recorded yet'},
                    'research_cents': sum(j.actual_cents for j in costs), 'days_from_first_signal_to_deal': sorted(lead_days)}
    return {'as_of': str(date.today()), 'sensors': out,
            'note': 'Outcomes are what this workspace recorded. No sensor is claimed to predict purchases until outcomes support it.'}
