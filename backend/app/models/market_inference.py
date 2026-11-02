"""Public observations, the hypotheses drawn from them, and how each was decided.

An observation is what a named source published. A hypothesis is MiSi's inference
from observations and is never a fact about a customer or supplier. Every change
to a hypothesis keeps its earlier reasoning.
"""
from datetime import date, datetime
from typing import Any
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class MarketObservation(Base):
    __tablename__ = 'market_observations'
    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signal_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    buyer: Mapped[str | None] = mapped_column(Text)
    buyer_key: Mapped[str | None] = mapped_column(String(200), index=True)
    supplier: Mapped[str | None] = mapped_column(Text)
    supplier_key: Mapped[str | None] = mapped_column(String(200), index=True)
    company_number: Mapped[str | None] = mapped_column(String(16))
    families: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    available_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_group: Mapped[str] = mapped_column(String(32), nullable=False)
    reliability: Mapped[str] = mapped_column(String(24), nullable=False)
    attribution: Mapped[str] = mapped_column(String(16), nullable=False, default='none')
    capture: Mapped[str] = mapped_column(String(24), nullable=False, default='automatic')
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_revision_id: Mapped[int | None] = mapped_column(ForeignKey('market_source_revisions.id', ondelete='SET NULL'))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retracted_on: Mapped[date | None] = mapped_column(Date)


class MarketHypothesis(Base):
    __tablename__ = 'market_hypotheses'
    id: Mapped[int] = mapped_column(primary_key=True)
    dedup_key: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey('market_contracts.id', ondelete='SET NULL'), index=True)
    buyer: Mapped[str | None] = mapped_column(Text)
    supplier: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    evidence_state: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default='active', index=True)
    current_revision_id: Mapped[int | None] = mapped_column(Integer)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_evaluated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketHypothesisRevision(Base):
    __tablename__ = 'market_hypothesis_revisions'
    __table_args__ = (UniqueConstraint('hypothesis_id', 'fingerprint', name='uq_market_hypothesis_fingerprint'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hypothesis_id: Mapped[int] = mapped_column(ForeignKey('market_hypotheses.id', ondelete='CASCADE'), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
