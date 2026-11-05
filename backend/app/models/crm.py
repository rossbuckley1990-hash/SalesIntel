"""SalesIntel's canonical commercial memory: accounts, their sites and contacts, what was
done with them, what is due next, and the deals they turn into.

Research engines (the radar, prospects, AI research) keep their own records. Accounts link
to those records with a stated basis instead of copying them, so evidence stays where it
was found and nothing is merged on a guess.
"""
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.tenancy import TenantScoped


class Account(TenantScoped, Base):
    __tablename__ = 'si_accounts'
    __table_args__ = (UniqueConstraint('organisation_id', 'company_number', name='uq_si_account_company'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default='unknown')  # public_body, private, unknown
    company_number: Mapped[str | None] = mapped_column(String(16))  # unique per workspace (uq_si_account_company)
    website: Mapped[str | None] = mapped_column(String(512))
    sector: Mapped[str | None] = mapped_column(String(160))
    region: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='prospect')
    watched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    watched_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default='')
    owner_user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AccountLink(TenantScoped, Base):
    """Why a research or pipeline record belongs to an account."""
    __tablename__ = 'si_account_links'
    __table_args__ = (UniqueConstraint('organisation_id', 'entity_type', 'entity_id', name='uq_si_account_link_entity'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # market_opportunity, prospect, opportunity, market_contract
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name_seen: Mapped[str] = mapped_column(String(255), nullable=False)
    basis: Mapped[str] = mapped_column(String(32), nullable=False)  # company_number, same_name, user_confirmed, created_from
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Site(TenantScoped, Base):
    __tablename__ = 'si_sites'
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False, default='')
    postcode: Mapped[str | None] = mapped_column(String(12))
    uprn: Mapped[str | None] = mapped_column(String(20))
    basis: Mapped[str] = mapped_column(String(24), nullable=False)  # published, user_entered, inferred
    source_url: Mapped[str | None] = mapped_column(Text)
    systems: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Contact(TenantScoped, Base):
    __tablename__ = 'si_contacts'
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(180))  # a role-only route has no name
    role: Mapped[str] = mapped_column(String(240), nullable=False, default='')
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(160), nullable=False, default='')
    basis: Mapped[str] = mapped_column(String(24), nullable=False)  # published, user_entered
    source_url: Mapped[str | None] = mapped_column(Text)
    source_quote: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='unverified')  # unverified, verified, do_not_contact
    influence: Mapped[str] = mapped_column(String(24), nullable=False, default='')
    # Contact Navigator evidence. quality: public_source, provider_verified, unverified, role_only.
    role_category: Mapped[str] = mapped_column(String(16), nullable=False, default='')  # procurement, commercial, technical, security, executive
    route_kind: Mapped[str] = mapped_column(String(24), nullable=False, default='')  # direct_email, phone, departmental_email, switchboard, web_form, procurement_notice, none
    quality: Mapped[str] = mapped_column(String(20), nullable=False, default='')
    verification_method: Mapped[str] = mapped_column(Text, nullable=False, default='')
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_date: Mapped[str | None] = mapped_column(String(10))
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default='')
    flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)  # stale, conflict, may_have_moved
    use_restriction: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Draft(TenantScoped, Base):
    """A message prepared in SalesIntel. A draft is never sent by SalesIntel."""
    __tablename__ = 'si_drafts'
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(Integer)
    contact_id: Mapped[int | None] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default='email')  # email, call
    subject: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    body: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='draft')  # draft, approved, logged
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Activity(TenantScoped, Base):
    """Something the salesperson did or learned, recorded by them."""
    __tablename__ = 'si_activities'
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(Integer, index=True)
    contact_id: Mapped[int | None] = mapped_column(Integer)
    draft_id: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # call, email, meeting, site_visit, note
    direction: Mapped[str] = mapped_column(String(12), nullable=False, default='outbound')
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default='')
    requirements: Mapped[str] = mapped_column(Text, nullable=False, default='')
    objections: Mapped[str] = mapped_column(Text, nullable=False, default='')
    commitments: Mapped[str] = mapped_column(Text, nullable=False, default='')
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Task(TenantScoped, Base):
    __tablename__ = 'si_tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    deal_id: Mapped[int | None] = mapped_column(Integer)
    activity_id: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default='open')  # open, done, cancelled
    assignee_user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DealRecord(TenantScoped, Base):
    """SalesIntel's view of a pipeline opportunity: where it came from and how it is progressing."""
    __tablename__ = 'si_deals'
    id: Mapped[int] = mapped_column(primary_key=True)
    # The legacy single-user pipeline record. Hosted workspaces do not use it, so it is optional.
    opportunity_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(24), nullable=False, default='qualify')
    origin_type: Mapped[str | None] = mapped_column(String(32))
    origin_id: Mapped[int | None] = mapped_column(Integer)
    origin: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # evidence frozen at conversion
    services: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    work_type: Mapped[str] = mapped_column(String(32), nullable=False, default='')
    qualification: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    value_annual: Mapped[float | None] = mapped_column(Float)
    value_total: Mapped[float | None] = mapped_column(Float)
    value_basis: Mapped[str] = mapped_column(String(24), nullable=False, default='unknown')  # published, user_estimate, unknown
    next_step: Mapped[str] = mapped_column(Text, nullable=False, default='')
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    quote: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    handover: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    outcome_reason: Mapped[str] = mapped_column(Text, nullable=False, default='')
    owner_user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    seller_confidence: Mapped[str | None] = mapped_column(String(12))  # the seller's own view: low, medium, high
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SavedView(TenantScoped, Base):
    __tablename__ = 'si_saved_views'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Preference(TenantScoped, Base):
    __tablename__ = 'si_preferences'
    organisation_id: Mapped[int] = mapped_column(ForeignKey('organisations.id', ondelete='CASCADE'), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)


class FunnelEvent(TenantScoped, Base):
    """The acquisition-to-revenue record: what happened, when, on which account, and which discovery the account
    came from. No people or message content. `origin` is fixed when the event is written, so re-linking an account
    later never rewrites how earlier work was attributed. Earlier events (before attribution) carry only name and day."""
    __tablename__ = 'si_funnel_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    event: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    account_id: Mapped[int | None] = mapped_column(Integer, index=True)
    deal_id: Mapped[int | None] = mapped_column(Integer)
    ref: Mapped[str | None] = mapped_column(String(48))  # the lead, contact or job the event concerns
    origin: Mapped[str | None] = mapped_column(String(48))  # the discovery record the account came from, e.g. sh:12
    source_type: Mapped[str | None] = mapped_column(String(16))  # shadow, public, private, manual
    amount: Mapped[float | None] = mapped_column(Float)  # only on a won deal: the recorded value, with its basis
    amount_basis: Mapped[str | None] = mapped_column(String(32))
