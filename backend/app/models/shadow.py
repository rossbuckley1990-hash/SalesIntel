"""Shadow Radar: hypotheses about unadvertised opportunities, and what each workspace learned from them.

Shared (public intelligence, read-only to workspaces): `shadow_hypotheses` and their immutable
`shadow_hypothesis_revisions`, inferred only from published observations in `market_observations`.

Private to a workspace: `si_dossiers` (deep investigations kept on the account) and
`si_lead_feedback` (whether a lead was relevant, and why not).
"""
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.tenancy import TenantScoped


class ShadowHypothesis(Base):
    __tablename__ = 'shadow_hypotheses'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    sensor: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    company_number: Mapped[str | None] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # indicated, corroborated, challenged, surfaced, closed
    first_published_on: Mapped[date] = mapped_column(Date, nullable=False)  # earliest publication among the supporting evidence
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # when SalesIntel first held that evidence
    formed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # when the radar first formed this hypothesis
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    current_revision_id: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_evaluated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ShadowHypothesisRevision(Base):
    """Every assessment the radar made, kept as made: later evidence adds a revision, never edits one."""
    __tablename__ = 'shadow_hypothesis_revisions'
    __table_args__ = (UniqueConstraint('hypothesis_id', 'fingerprint', name='uq_shadow_revision'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hypothesis_id: Mapped[int] = mapped_column(ForeignKey('shadow_hypotheses.id', ondelete='CASCADE'), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Dossier(TenantScoped, Base):
    """One deep investigation of an account, kept on the account. A new investigation adds a version."""
    __tablename__ = 'si_dossiers'
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    hypothesis_key: Mapped[str | None] = mapped_column(String(320))
    job_id: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    sections: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    challenge: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)  # strengthened, weakened, unresolved
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    rejected: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeadFeedback(TenantScoped, Base):
    """A salesperson's judgement of a lead. The radar is evaluated against these, never tuned silently."""
    __tablename__ = 'si_lead_feedback'
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    sensor: Mapped[str] = mapped_column(String(40), nullable=False, default='')
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # relevant, not_relevant, disproved
    reason: Mapped[str] = mapped_column(String(32), nullable=False, default='')
    note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = ['ShadowHypothesis', 'ShadowHypothesisRevision', 'Dossier', 'LeadFeedback', 'UniqueConstraint', 'String']
