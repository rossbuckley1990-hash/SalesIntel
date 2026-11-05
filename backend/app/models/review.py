"""Blind human review of discovered opportunities: one reviewer's recorded judgement of one item in a frozen review set.

The review set itself (blinded items) and its sealed key (which arm produced each item) are files under
`reference_data/evaluation/`. Only decisions are stored here, per workspace (row-level security on PostgreSQL), so each
reviewer's answers are kept separately and disagreements stay visible."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.tenancy import TenantScoped


class ReviewDecision(TenantScoped, Base):
    __tablename__ = 'si_review_decisions'
    __table_args__ = (UniqueConstraint('organisation_id', 'set_key', 'item_id', 'reviewer', name='uq_si_review_decision'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    set_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer: Mapped[int] = mapped_column(Integer, nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    minutes: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
