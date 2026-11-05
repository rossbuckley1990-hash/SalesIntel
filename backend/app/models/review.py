"""Blind human review of discovered opportunities: reviewers' judgements, adjudicated disagreements, and the state of
each frozen review set in a workspace (open, locked, revealed).

The served review set and its public commitment are files under `reference_data/evaluation/`. The key that unblinds it
is never in the repository: an administrator supplies it only after the review is complete and locked, and it is
accepted only if it matches the commitment. Everything here is per workspace (row-level security on PostgreSQL)."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.tenancy import TenantScoped


class ReviewDecision(TenantScoped, Base):
    """One reviewer's judgement of one item. Reviewers in the app are users; reviewers using an offline pack get a stable
    negative id from their name, so the two can never collide."""
    __tablename__ = 'si_review_decisions'
    __table_args__ = (UniqueConstraint('organisation_id', 'set_key', 'item_id', 'reviewer', name='uq_si_review_decision'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    set_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(120), nullable=False, default='')
    channel: Mapped[str] = mapped_column(String(8), nullable=False, default='app')  # app or pack
    submission_sha256: Mapped[str | None] = mapped_column(String(64))  # the imported pack file, for the audit trail
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    minutes: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewAdjudication(TenantScoped, Base):
    """How a disagreement on a primary question was resolved: the final answer, by whom, how and why."""
    __tablename__ = 'si_review_adjudications'
    __table_args__ = (UniqueConstraint('organisation_id', 'set_key', 'item_id', 'question', name='uq_si_review_adjudication'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    set_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(16), nullable=False)
    question: Mapped[str] = mapped_column(String(16), nullable=False)
    answer: Mapped[str] = mapped_column(String(24), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)  # consensus or third_reviewer
    adjudicator: Mapped[str] = mapped_column(String(120), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewState(TenantScoped, Base):
    """open (reviews and adjudications accepted) -> locked (frozen, complete) -> revealed (key verified, results visible)."""
    __tablename__ = 'si_review_states'
    __table_args__ = (UniqueConstraint('organisation_id', 'set_key', name='uq_si_review_state'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    set_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default='open')
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[int | None] = mapped_column(Integer)
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revealed_by: Mapped[int | None] = mapped_column(Integer)
    key: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    key_sha256: Mapped[str | None] = mapped_column(String(64))
