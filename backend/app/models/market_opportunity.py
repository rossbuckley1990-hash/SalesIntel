"""Reviewable market hypotheses, with immutable generated versions."""
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class MarketOpportunity(Base):
    __tablename__ = 'market_opportunities'
    id: Mapped[int] = mapped_column(primary_key=True)
    dedup_key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default='suggested')
    review_state: Mapped[str] = mapped_column(String(32), nullable=False, default='unreviewed')
    current_revision_id: Mapped[int | None] = mapped_column(Integer)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_evaluated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    withdrawal_reason: Mapped[str | None] = mapped_column(Text)


class MarketOpportunityRevision(Base):
    __tablename__ = 'market_opportunity_revisions'
    __table_args__ = (UniqueConstraint('opportunity_id', 'fingerprint', name='uq_market_opportunity_fingerprint'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey('market_opportunities.id', ondelete='CASCADE'), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketOpportunityDossier(Base):
    """A saved deep-research snapshot for one opportunity; never rewritten, only superseded."""
    __tablename__ = 'market_opportunity_dossiers'
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey('market_opportunities.id', ondelete='CASCADE'), nullable=False, index=True)
    revision_id: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
