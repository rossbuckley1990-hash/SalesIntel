"""People and workspaces: who I am, which companies I work for, who is in my team and what they may do."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import re
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import Caller, Context, current_caller, current_context, new_invitation_token
from app.config import get_settings
from app.db import get_db
from app.models.tenancy import Invitation, Membership, Organisation, User, WorkspaceAuditEvent
from app.tenancy import ORG, ROLE_LABELS, ROLES, USER, PERMISSIONS, record

router = APIRouter(prefix='/api', tags=['workspaces'])
TARGET_BASES = {'annual_contract_value': 'Annual contract value', 'total_contract_value': 'Total contract value', 'gross_margin': 'Gross margin'}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


def _hosted_only() -> None:
    if get_settings().auth_mode == 'local':
        raise HTTPException(status_code=409, detail='This is a single-user local install. Workspaces need sign-in (AUTH_MODE=oidc).')


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _member_view(m: Membership, u: User) -> dict:
    return {'user_id': u.id, 'name': u.name, 'email': u.email, 'role': m.role, 'role_label': ROLE_LABELS[m.role],
            'territory': m.territory, 'services': m.services,
            'target': {'amount': m.target_amount, 'basis': m.target_basis, 'basis_label': TARGET_BASES.get(m.target_basis or ''), 'period': m.target_period}}


@router.get('/me')
def me(caller: Caller = Depends(current_caller), db: Session = Depends(get_db)):
    if get_settings().auth_mode == 'local':
        return {'mode': 'local', 'user': {'name': 'You'}, 'workspaces': [{'id': 1, 'name': 'Local workspace', 'role': 'admin'}]}
    rows = db.execute(select(Membership, Organisation).join(Organisation, Organisation.id == Membership.organisation_id)
                      .where(Membership.user_id == caller.user_id).order_by(Organisation.name)).all()
    return {'mode': get_settings().auth_mode, 'user': {'id': caller.user_id, 'name': caller.name, 'email': caller.email},
            'workspaces': [{'id': o.id, 'name': o.name, 'role': m.role, 'role_label': ROLE_LABELS[m.role]} for m, o in rows]}


class NewWorkspace(Strict):
    name: str = Field(min_length=2, max_length=160)
    industry: Literal['fire_and_security'] = 'fire_and_security'


@router.post('/workspaces')
def create_workspace(payload: NewWorkspace, caller: Caller = Depends(current_caller), db: Session = Depends(get_db)):
    _hosted_only()
    moment = datetime.now(UTC)
    slug = (re.sub(r'[^a-z0-9]+', '-', payload.name.lower()).strip('-')[:60] or 'workspace') + '-' + secrets.token_hex(3)
    org = Organisation(name=payload.name.strip(), slug=slug, industry=payload.industry, created_at=moment)
    db.add(org)
    db.flush()
    db.add(Membership(organisation_id=org.id, user_id=caller.user_id, role='admin', territory=[], services=[], created_at=moment))
    db.info[ORG], db.info[USER] = org.id, caller.user_id
    record(db, 'create', 'workspace', org.id)
    db.commit()
    return {'id': org.id, 'name': org.name, 'role': 'admin'}


@router.get('/workspace')
def workspace(ctx: Context = Depends(current_context), db: Session = Depends(get_db)):
    if get_settings().auth_mode == 'local':
        return {'id': 1, 'name': 'Local workspace', 'role': 'admin', 'permissions': sorted(PERMISSIONS['admin']), 'me': None}
    org = db.get(Organisation, ctx.organisation_id)
    mine = db.scalar(select(Membership).where(Membership.organisation_id == ctx.organisation_id, Membership.user_id == ctx.user_id))
    return {'id': org.id, 'name': org.name, 'role': ctx.role, 'role_label': ROLE_LABELS[ctx.role], 'permissions': sorted(PERMISSIONS[ctx.role]),
            'me': _member_view(mine, db.get(User, ctx.user_id)), 'target_bases': TARGET_BASES}


class MyProfile(Strict):
    territory: list[str] | None = Field(None, max_length=12)
    services: list[str] | None = Field(None, max_length=16)
    target_amount: StrictStr | StrictInt | StrictFloat | None = None
    target_basis: Literal['annual_contract_value', 'total_contract_value', 'gross_margin'] | None = None
    target_period: Literal['annual', 'quarterly', 'monthly'] | None = None


@router.patch('/workspace/me')
def update_my_profile(payload: MyProfile, ctx: Context = Depends(current_context), db: Session = Depends(get_db)):
    """My territory, the services I sell and my new-business target, with the basis that target is measured on."""
    _hosted_only()
    from app.services.si_engage import money
    mine = db.scalar(select(Membership).where(Membership.organisation_id == ctx.organisation_id, Membership.user_id == ctx.user_id))
    if payload.territory is not None:
        mine.territory = [t.strip()[:60] for t in payload.territory if t.strip()]
    if payload.services is not None:
        mine.services = [s.strip()[:40] for s in payload.services if s.strip()]
    if payload.target_amount is not None:
        if not (payload.target_basis or mine.target_basis) or not (payload.target_period or mine.target_period):
            raise HTTPException(status_code=422, detail='Say what the target measures and over what period: contract value, total contract value and margin are not interchangeable.')
        try:
            mine.target_amount = str(money(payload.target_amount, 'Target'))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.target_basis is not None:
        mine.target_basis = payload.target_basis
    if payload.target_period is not None:
        mine.target_period = payload.target_period
    db.info[ORG], db.info[USER] = ctx.organisation_id, ctx.user_id
    record(db, 'update', 'membership', mine.id, {'fields': sorted(payload.model_dump(exclude_none=True))})
    db.commit()
    return _member_view(mine, db.get(User, ctx.user_id))


@router.get('/workspace/members')
def members(ctx: Context = Depends(current_context), db: Session = Depends(get_db)):
    _hosted_only()
    rows = db.execute(select(Membership, User).join(User, User.id == Membership.user_id)
                      .where(Membership.organisation_id == ctx.organisation_id).order_by(User.name)).all()
    pending = db.scalars(select(Invitation).where(Invitation.organisation_id == ctx.organisation_id, Invitation.status == 'pending')).all() \
        if 'members.manage' in PERMISSIONS[ctx.role] else []
    return {'items': [_member_view(m, u) for m, u in rows], 'roles': [{'role': r, 'label': ROLE_LABELS[r]} for r in ROLES],
            'invitations': [{'id': i.id, 'email': i.email, 'role': i.role, 'expires_at': i.expires_at.isoformat()} for i in pending]}


class Invite(Strict):
    email: str = Field(min_length=3, max_length=255, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    role: Literal['admin', 'sales_manager', 'salesperson', 'bid_contributor', 'reviewer']


@router.post('/workspace/invitations')
def invite(payload: Invite, ctx: Context = Depends(current_context), db: Session = Depends(get_db)):
    """Create an invitation. SalesIntel does not email it: the administrator shares the link."""
    _hosted_only()
    ctx.require('members.manage')
    token, moment = new_invitation_token(), datetime.now(UTC)
    row = Invitation(organisation_id=ctx.organisation_id, email=payload.email.lower(), role=payload.role, token_hash=_hash(token),
                     invited_by=ctx.user_id, status='pending', expires_at=moment + timedelta(days=7), created_at=moment)
    db.add(row)
    db.flush()
    db.info[ORG], db.info[USER] = ctx.organisation_id, ctx.user_id
    record(db, 'invite', 'invitation', row.id, {'role': payload.role})
    db.commit()
    return {'id': row.id, 'email': row.email, 'role': row.role, 'token': token, 'expires_at': row.expires_at.isoformat(),
            'note': 'Shown once. Share it with the person directly; SalesIntel does not send email.'}


@router.delete('/workspace/invitations/{invitation_id}')
def revoke(invitation_id: int, ctx: Context = Depends(current_context), db: Session = Depends(get_db)):
    _hosted_only()
    ctx.require('members.manage')
    row = db.get(Invitation, invitation_id)
    if not row or row.organisation_id != ctx.organisation_id or row.status != 'pending':
        raise HTTPException(status_code=404, detail='Invitation not found')
    row.status = 'revoked'
    db.commit()
    return {'id': row.id, 'status': row.status}


class Accept(Strict):
    token: str = Field(min_length=20, max_length=200)


@router.post('/invitations/accept')
def accept(payload: Accept, caller: Caller = Depends(current_caller), db: Session = Depends(get_db)):
    _hosted_only()
    row = db.scalar(select(Invitation).where(Invitation.token_hash == _hash(payload.token)))
    expires = row.expires_at if row and row.expires_at.tzinfo else (row.expires_at.replace(tzinfo=UTC) if row else None)
    # One message for every failure, so the endpoint does not reveal which invitations exist.
    if not row or row.status != 'pending' or expires < datetime.now(UTC) or row.email != caller.email.lower():
        raise HTTPException(status_code=404, detail='This invitation is not valid for your account.')
    existing = db.scalar(select(Membership).where(Membership.organisation_id == row.organisation_id, Membership.user_id == caller.user_id))
    if existing is None:
        db.add(Membership(organisation_id=row.organisation_id, user_id=caller.user_id, role=row.role, territory=[], services=[], created_at=datetime.now(UTC)))
    row.status = 'accepted'
    db.info[ORG], db.info[USER] = row.organisation_id, caller.user_id
    record(db, 'join', 'membership', None, {'role': row.role})
    db.commit()
    org = db.get(Organisation, row.organisation_id)
    return {'id': org.id, 'name': org.name, 'role': row.role}


class RoleChange(Strict):
    role: Literal['admin', 'sales_manager', 'salesperson', 'bid_contributor', 'reviewer']


def _member(db: Session, ctx: Context, user_id: int) -> Membership:
    m = db.scalar(select(Membership).where(Membership.organisation_id == ctx.organisation_id, Membership.user_id == user_id))
    if m is None:
        raise HTTPException(status_code=404, detail='Member not found')
    return m


def _last_admin(db: Session, ctx: Context, m: Membership) -> bool:
    admins = db.scalar(select(func.count()).select_from(Membership).where(Membership.organisation_id == ctx.organisation_id, Membership.role == 'admin'))
    return m.role == 'admin' and admins <= 1


@router.patch('/workspace/members/{user_id}')
def change_role(user_id: int, payload: RoleChange, ctx: Context = Depends(current_context), db: Session = Depends(get_db)):
    _hosted_only()
    ctx.require('members.manage')
    m = _member(db, ctx, user_id)
    if payload.role != 'admin' and _last_admin(db, ctx, m):
        raise HTTPException(status_code=409, detail='A workspace needs at least one administrator.')
    before, m.role = m.role, payload.role
    db.info[ORG], db.info[USER] = ctx.organisation_id, ctx.user_id
    record(db, 'role', 'membership', m.id, {'from': before, 'to': payload.role, 'member': user_id})
    db.commit()
    return {'user_id': user_id, 'role': m.role}


@router.delete('/workspace/members/{user_id}')
def remove_member(user_id: int, ctx: Context = Depends(current_context), db: Session = Depends(get_db)):
    _hosted_only()
    ctx.require('members.manage')
    m = _member(db, ctx, user_id)
    if _last_admin(db, ctx, m):
        raise HTTPException(status_code=409, detail='A workspace needs at least one administrator.')
    db.delete(m)
    db.info[ORG], db.info[USER] = ctx.organisation_id, ctx.user_id
    record(db, 'remove', 'membership', m.id, {'member': user_id})
    db.commit()
    return {'user_id': user_id, 'removed': True}


@router.get('/workspace/audit')
def audit(limit: int = Query(100, ge=1, le=500), ctx: Context = Depends(current_context), db: Session = Depends(get_db)):
    ctx.require('audit.read')
    db.info[ORG], db.info[USER] = ctx.organisation_id, ctx.user_id  # row-level security shows only this workspace's audit trail
    rows = db.scalars(select(WorkspaceAuditEvent).where(WorkspaceAuditEvent.organisation_id == ctx.organisation_id)
                      .order_by(WorkspaceAuditEvent.id.desc()).limit(limit)).all()
    return {'items': [{'at': r.at.isoformat(), 'user_id': r.user_id, 'action': r.action, 'entity_type': r.entity_type,
                       'entity_id': r.entity_id, 'fields': r.fields, 'detail': r.detail} for r in rows]}
