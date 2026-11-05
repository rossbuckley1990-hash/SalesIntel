"""Who uses SalesIntel and whose records are whose.

Every private commercial record carries an ``organisation_id`` (``TenantScoped``). The
database session filters reads and stamps writes from the authenticated workspace, so a
service function cannot reach another company's records even if it forgets to filter
(see ``app/tenancy.py``). Identity comes from a managed provider: SalesIntel stores the
provider's issuer and subject, never a password.
"""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db import Base

LOCAL_ORG_ID = 1  # the single workspace of a local, single-user install


class TenantScoped:
    """Mixin for records that belong to exactly one organisation."""

    @declared_attr
    def organisation_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True)


class Organisation(Base):
    __tablename__ = 'organisations'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    industry: Mapped[str] = mapped_column(String(48), nullable=False, default='fire_and_security')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@event.listens_for(Organisation.__table__, 'after_create')
def _local_workspace(target, connection, **kw) -> None:
    """A freshly created schema (tests, demo, local) gets the local workspace that owns local records."""
    connection.execute(target.insert().values(id=LOCAL_ORG_ID, name='Local workspace', slug='local', industry='fire_and_security',
                                              created_at=datetime(2026, 1, 1)))
    if connection.dialect.name == 'postgresql':  # an explicit id does not advance the sequence
        from sqlalchemy import text
        connection.execute(text("SELECT setval(pg_get_serial_sequence('organisations', 'id'), (SELECT MAX(id) FROM organisations))"))


class User(Base):
    """A person, as asserted by the identity provider. No password is ever stored here."""
    __tablename__ = 'users'
    __table_args__ = (UniqueConstraint('issuer', 'subject', name='uq_users_identity'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Membership(Base):
    __tablename__ = 'memberships'
    __table_args__ = (UniqueConstraint('organisation_id', 'user_id', name='uq_membership'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    territory: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    services: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # A personal new-business target is meaningless without its basis: these are never interchangeable.
    target_amount: Mapped[str | None] = mapped_column(String(24))  # exact decimal string, GBP
    target_basis: Mapped[str | None] = mapped_column(String(24))  # annual_contract_value, total_contract_value, gross_margin
    target_period: Mapped[str | None] = mapped_column(String(16))  # annual, quarterly, monthly
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Invitation(Base):
    __tablename__ = 'invitations'
    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # only the hash is stored
    invited_by: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default='pending')  # pending, accepted, revoked
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkspaceAuditEvent(Base):
    """Who changed which record, and which fields. Values are not copied, so personal data is not duplicated."""
    __tablename__ = 'si_audit_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(12), nullable=False)  # create, update, delete, plus named actions
    entity_type: Mapped[str] = mapped_column(String(48), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class LeadState(TenantScoped, Base):
    """A workspace's own review of a shared public lead. One company dismissing a notice hides it only for that company."""
    __tablename__ = 'si_lead_states'
    __table_args__ = (UniqueConstraint('organisation_id', 'entity_type', 'entity_id', name='uq_si_lead_state'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # new, watching, investigating, dismissed
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(Integer)


__all__ = ['LOCAL_ORG_ID', 'TenantScoped', 'Organisation', 'User', 'Membership', 'Invitation', 'WorkspaceAuditEvent', 'LeadState', 'Text']
