"""Contract Atlas API: who holds fire and security work, for whom, until when, and what is worth investigating.

Published contracts are shared public facts, read from the Market Network. Relationships researched from case studies and
announcements, and every research job, belong to the workspace that asked for them.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Context, current_context, tenant_db
from app.config import get_settings
from app.idempotency import idempotent
from app.routers.salesintel import Strict, _start, permitted, run
from app.services import atlas, field
from app.services import si_core as core
from app.services.ai_costs import research_provider
from app.tenancy import SYSTEM

router = APIRouter(prefix='/api/si/atlas', tags=['atlas'], dependencies=[Depends(permitted)])


def _ensure(db: Session) -> None:
    """Bring the shared contractor index up to date with the Market Network, in a system session of its own: a
    workspace's request may read shared public facts but never write them. Two requests racing is harmless."""
    system = Session(bind=db.get_bind())
    system.info[SYSTEM] = True
    try:
        atlas.ensure_built(system)
        system.commit()
    except IntegrityError:
        system.rollback()
    finally:
        system.close()


@router.get('/search')
def search(q: str = Query('', max_length=120), discipline: str = Query('', max_length=40), nation: str = Query('', max_length=40),
           region: str = Query('', max_length=48), ending_months: int | None = Query(None, ge=1, le=60), db: Session = Depends(tenant_db)):
    def work():
        _ensure(db)
        found = atlas.search(db, q, discipline=discipline, nation=nation, region=region, ending_months=ending_months)
        return {**found, 'options': {'disciplines': [{'family': k, 'label': v} for k, v in atlas.FAMILY_LABEL.items()], 'regions': list(atlas.REGIONS),
                                     'nations': ['England', 'Scotland', 'Wales', 'Northern Ireland']}}
    return run(db, work)


@router.get('/contractors/{contractor_id}')
def contractor(contractor_id: int, db: Session = Depends(tenant_db)):
    def work():
        _ensure(db)
        prefs = core.preferences(db)
        return {**atlas.contractor_record(db, contractor_id, prefs=prefs), 'footprint': field.footprint(db, contractor_id, own_name=prefs.get('company_name') or '')}
    return run(db, work)


@router.get('/customers/{customer_key}')
def customer(customer_key: str, db: Session = Depends(tenant_db)):
    def work():
        _ensure(db)
        return atlas.customer_record(db, atlas.normalise(customer_key))
    return run(db, work)


@router.get('/account/{account_id}')
def account_suppliers(account_id: int, db: Session = Depends(tenant_db)):
    """The Atlas view of an account: its known suppliers, by its exact name."""
    from app.models.crm import Account

    def work():
        found = db.get(Account, account_id)
        if found is None:
            raise LookupError('Account not found')
        _ensure(db)
        return atlas.customer_record(db, atlas.normalise(found.name))
    return run(db, work)


class AtlasResearch(Strict):
    direction: Literal['contractor', 'customer']
    subject: str = Field(min_length=2, max_length=255)
    contractor_id: int | None = None


@router.post('/research')
def research(payload: AtlasResearch, request: Request, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Research what public sources say about one contractor's customers, or one customer's suppliers. A durable job
    within the approved research budget; nothing is spent without one."""
    ctx.require('research.run')
    if research_provider(get_settings()) is None:
        raise HTTPException(status_code=403, detail='Web research is switched off in demo mode, so no API credit is used.' if get_settings().app_env == 'demo'
                            else 'Web research is not configured here.')
    params = {'direction': payload.direction, 'subject': payload.subject.strip(), 'contractor_id': payload.contractor_id}
    return run(db, lambda: idempotent(db, request.headers.get('idempotency-key'), 'atlas.research', payload.model_dump(),
                                      lambda: _start(db, ctx, 'atlas_relationships', None, params)))
