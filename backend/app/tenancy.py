"""Tenant isolation enforced by the database session, and the role permissions.

The guarantees, in hosted modes (``AUTH_MODE`` = ``oidc`` or ``dev``):

1. A request session carries the authenticated workspace in ``session.info``. It is set by
   the server from a verified membership, never taken from a browser-supplied identifier.
2. Every ORM read, update or delete gets ``organisation_id = <workspace>`` added for every
   ``TenantScoped`` entity, including ``Session.get``, counts and joins. Another company's
   record therefore looks exactly like a record that does not exist.
3. Every write is stamped with the workspace; writing a record into, or moving a record to,
   another workspace raises.
4. A session without a workspace that touches tenant data raises (fail closed). Only
   explicitly marked system sessions (collectors, migrations) are unscoped.
5. A request session may read the shared public-market tables but never write them, and may
   not touch the single-user legacy tables at all.
6. Each change to a tenant record writes an audit event: who, what, which fields.

In ``local`` mode (a single-user install on this machine) everything belongs to the local
workspace, so existing behaviour and data are unchanged.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import Session, with_loader_criteria

from app.config import get_settings
from app.models.tenancy import (LOCAL_ORG_ID, Invitation, Membership, Organisation, TenantScoped, User,
                                WorkspaceAuditEvent)

ORG = 'organisation_id'
USER = 'user_id'
SYSTEM = 'system'

# Public, openly licensed market intelligence that every workspace may read and none may write.
SHARED_PUBLIC_TABLES = frozenset({
    'market_opportunities', 'market_opportunity_revisions', 'market_contracts', 'market_contract_links', 'market_source_states',
    'market_source_revisions', 'market_entities', 'market_awards', 'market_entity_evidence', 'market_relationships',
    'market_observations', 'market_hypotheses', 'market_hypothesis_revisions',
})
IDENTITY_MODELS = (Organisation, User, Membership, Invitation)

ROLES = ('admin', 'sales_manager', 'salesperson', 'bid_contributor', 'reviewer')
ROLE_LABELS = {'admin': 'Administrator', 'sales_manager': 'Sales manager', 'salesperson': 'Salesperson',
               'bid_contributor': 'Bid and commercial contributor', 'reviewer': 'Read-only reviewer'}
PERMISSIONS: dict[str, frozenset[str]] = {
    'admin': frozenset({'crm.read', 'crm.write', 'crm.assign', 'quote.approve', 'research.run', 'members.manage', 'audit.read', 'team.read'}),
    'sales_manager': frozenset({'crm.read', 'crm.write', 'crm.assign', 'quote.approve', 'research.run', 'audit.read', 'team.read'}),
    'salesperson': frozenset({'crm.read', 'crm.write', 'research.run'}),
    'bid_contributor': frozenset({'crm.read', 'crm.write'}),
    'reviewer': frozenset({'crm.read'}),
}


class TenantScopeError(RuntimeError):
    """A programming error: tenant data was reached without a workspace. Never mapped to a 4xx."""


class ForeignReferenceError(LookupError):
    """A record named a related record that is not in its workspace. Reported as not found."""


def _references():
    from app.models.crm import Account, Activity, Contact, DealRecord, Draft
    return {'account_id': Account, 'deal_id': DealRecord, 'contact_id': Contact, 'activity_id': Activity, 'draft_id': Draft}


def _check_references(session: Session, obj) -> None:
    """Every id a tenant record holds must name a record in the same workspace."""
    state = sa_inspect(obj)
    for attr, model in _references().items():
        if not hasattr(obj, attr):
            continue
        value = getattr(obj, attr)
        if value is None or (obj not in session.new and not state.attrs[attr].history.has_changes()):
            continue
        with session.no_autoflush:
            target = session.get(model, value)
        if target is None or target.organisation_id != obj.organisation_id:
            raise ForeignReferenceError(f'{model.__name__.replace("Record", "")} not found')


def hosted() -> bool:
    return get_settings().auth_mode != 'local'


def can(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, frozenset())


def workspace_of(session: Session) -> int | None:
    """The workspace a session acts for; None only for a system session."""
    org = session.info.get(ORG)
    if org is not None:
        return org
    if session.info.get(SYSTEM):
        return None
    if not hosted():
        return LOCAL_ORG_ID
    raise TenantScopeError('Tenant data was accessed without a workspace. Use a request session or a marked system session.')


def system_session(session: Session) -> Session:
    """Mark a session as a trusted background process that reads shared data across workspaces."""
    session.info[SYSTEM] = True
    return session


def _is_request(session: Session) -> bool:
    return hosted() and not session.info.get(SYSTEM)


def _table(mapper) -> str:
    return getattr(mapper.local_table, 'name', '')


def _sync_database_setting(session: Session) -> None:
    """Keep PostgreSQL's transaction-local workspace setting equal to this session's workspace (row-level security)."""
    bind = session.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    org = session.info.get(ORG)
    if org is None and not session.info.get(SYSTEM) and not hosted():
        org = LOCAL_ORG_ID
    want = ('on' if session.info.get(SYSTEM) and org is None else 'off', '' if org is None else str(org))
    connection = session.connection()
    if connection.info.get('si_rls') == (want, id(session.get_transaction())):
        return
    connection.exec_driver_sql("SELECT set_config('salesintel.bypass', %(b)s, true), set_config('salesintel.organisation_id', %(o)s, true)",
                               {'b': want[0], 'o': want[1]})
    connection.info['si_rls'] = (want, id(session.get_transaction()))


@event.listens_for(Session, 'after_begin')
def _new_transaction(session: Session, transaction, connection) -> None:
    connection.info.pop('si_rls', None)  # transaction-local settings end with the transaction


@event.listens_for(Session, 'do_orm_execute')
def _scope_statements(state) -> None:
    _sync_database_setting(state.session)
    if not (state.is_select or state.is_update or state.is_delete):
        return
    session = state.session
    mappers = list(state.all_mappers)
    if _is_request(session):
        for mapper in mappers:
            cls = mapper.class_
            if issubclass(cls, TenantScoped) or issubclass(cls, IDENTITY_MODELS) or issubclass(cls, WorkspaceAuditEvent):
                continue
            if _table(mapper) in SHARED_PUBLIC_TABLES and state.is_select:
                continue
            raise TenantScopeError(f'{cls.__name__} is not available to a hosted workspace.')
    if session.info.get(SYSTEM) and session.info.get(ORG) is None:
        return
    org = workspace_of(session) if any(issubclass(m.class_, TenantScoped) for m in mappers) else session.info.get(ORG, None if hosted() else LOCAL_ORG_ID)
    if org is None:
        return
    # Applied even when no tenant entity was detected, so a count or join cannot slip through.
    state.statement = state.statement.options(
        with_loader_criteria(TenantScoped, lambda cls: cls.organisation_id == org, include_aliases=True))


@event.listens_for(Session, 'before_flush')
def _stamp_writes(session: Session, flush_context, instances) -> None:
    _sync_database_setting(session)
    request = _is_request(session)
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        if isinstance(obj, TenantScoped):
            org = workspace_of(session)
            if obj in session.new and getattr(obj, 'organisation_id', None) is None:
                if org is None:
                    raise TenantScopeError(f'A system session must set the workspace of a new {type(obj).__name__}.')
                obj.organisation_id = org
            if obj in session.new:  # whoever creates an account, deal or follow-up owns it until reassigned
                for owner in ('owner_user_id', 'assignee_user_id'):
                    if hasattr(obj, owner) and getattr(obj, owner) is None and session.info.get(USER) is not None:
                        setattr(obj, owner, session.info[USER])
            history = sa_inspect(obj).attrs.organisation_id.history
            if obj not in session.new and history.has_changes():
                raise TenantScopeError('A record cannot be moved to another workspace.')
            if org is not None and obj.organisation_id != org:
                raise TenantScopeError('A record was written to a workspace other than the one this session acts for.')
            if obj not in session.deleted:
                _check_references(session, obj)
        elif request and not isinstance(obj, IDENTITY_MODELS):
            raise TenantScopeError(f'{type(obj).__name__} cannot be written by a hosted workspace.')


@event.listens_for(Session, 'after_flush')
def _audit(session: Session, flush_context) -> None:
    rows = []
    moment = datetime.now(UTC)
    for action, objects in (('create', session.new), ('update', session.dirty), ('delete', session.deleted)):
        for obj in objects:
            if not isinstance(obj, TenantScoped):
                continue
            state = sa_inspect(obj)
            if action == 'update':
                fields = sorted(a.key for a in state.attrs if a.history.has_changes())
                if not fields:
                    continue
            else:
                fields = []
            rows.append({'organisation_id': obj.organisation_id, 'user_id': session.info.get(USER), 'action': action,
                         'entity_type': type(obj).__tablename__, 'entity_id': getattr(obj, 'id', None) if isinstance(getattr(obj, 'id', None), int) else None,
                         'fields': fields, 'detail': {}, 'at': moment})
    if rows:
        _sync_database_setting(session)
        session.connection().execute(WorkspaceAuditEvent.__table__.insert(), rows)


def record(session: Session, action: str, entity_type: str, entity_id: int | None, detail: dict | None = None) -> None:
    """A named audit event, such as an approval, a role change or a refused cross-workspace attempt."""
    org = session.info.get(ORG, None if hosted() else LOCAL_ORG_ID)
    if org is None:
        return
    _sync_database_setting(session)
    session.connection().execute(WorkspaceAuditEvent.__table__.insert(), [{
        'organisation_id': org, 'user_id': session.info.get(USER), 'action': action[:12], 'entity_type': entity_type[:48],
        'entity_id': entity_id, 'fields': [], 'detail': detail or {}, 'at': datetime.now(UTC)}])
