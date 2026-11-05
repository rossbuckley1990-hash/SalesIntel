"""Durable research jobs, spending limits, idempotent writes and the suppression list."""
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.tenancy import TenantScoped


class ResearchJob(TenantScoped, Base):
    """Research that outlives the request, the browser tab and the server process."""
    __tablename__ = 'si_research_jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    requested_by: Mapped[int | None] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # contact_navigator, prospect_search
    account_id: Mapped[int | None] = mapped_column(Integer, index=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='queued', index=True)  # queued running succeeded partial failed cancelled
    stage: Mapped[str] = mapped_column(String(120), nullable=False, default='')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_token: Mapped[str | None] = mapped_column(String(40))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimated_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SpendBudget(TenantScoped, Base):
    """A day's AI allowance for a workspace (user_id 0) or one person, in US cents at list price."""
    __tablename__ = 'si_spend_budgets'
    __table_args__ = (UniqueConstraint('organisation_id', 'user_id', 'day', name='uq_si_spend_day'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    limit_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spent_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class IdempotencyRecord(TenantScoped, Base):
    """The first response to a write, replayed when the same request is retried."""
    __tablename__ = 'si_idempotency'
    __table_args__ = (UniqueConstraint('organisation_id', 'key', name='uq_si_idempotency_key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(160), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default='pending')  # pending, done
    status_code: Mapped[int | None] = mapped_column(Integer)
    response: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Suppression(TenantScoped, Base):
    """Someone asked not to be contacted. Only a hash of the address or number is kept."""
    __tablename__ = 'si_suppressions'
    __table_args__ = (UniqueConstraint('organisation_id', 'kind', 'value_hash', name='uq_si_suppression'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)  # email, phone, person
    value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False, default='')
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
