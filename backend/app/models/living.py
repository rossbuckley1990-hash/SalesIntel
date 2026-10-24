"""Additive living-workspace records. Original commercial tables stay intact."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Snapshot(Base):
    __tablename__ = "living_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(160))
    reviewer: Mapped[str] = mapped_column(String(120))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    payload: Mapped[dict] = mapped_column(JSON)


class Decision(Base):
    __tablename__ = "living_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), index=True
    )
    choice: Mapped[str] = mapped_column(String(40))
    rationale: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    qualification: Mapped[dict] = mapped_column(JSON)


class EvidenceReview(Base):
    __tablename__ = "living_evidence_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(
        ForeignKey("field_intelligence.id"), index=True
    )
    disposition: Mapped[str] = mapped_column(String(40))
    reviewer: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Scenario(Base):
    __tablename__ = "living_scenarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    owner: Mapped[str] = mapped_column(String(120))
    assumptions: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    expected_contribution: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Asset(Base):
    __tablename__ = "living_assets"
    __table_args__ = (
        UniqueConstraint("series_key", "version", name="uq_living_asset_version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    series_key: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    version: Mapped[int] = mapped_column()
    review_status: Mapped[str] = mapped_column(String(40), default="draft")
    reviewer: Mapped[str] = mapped_column(String(120), default="")
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Outcome(Base):
    __tablename__ = "living_outcomes"
    __table_args__ = (
        UniqueConstraint("opportunity_id", name="uq_living_outcome_opportunity"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), index=True
    )
    action_id: Mapped[int | None] = mapped_column(
        ForeignKey("executive_actions.id"), nullable=True
    )
    decision_id: Mapped[int | None] = mapped_column(
        ForeignKey("living_decisions.id"), nullable=True
    )
    stage: Mapped[str] = mapped_column(String(40), default="identified")
    expected_impact: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True
    )
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    owner: Mapped[str] = mapped_column(String(120))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), default="estimated")
    assumptions: Mapped[str] = mapped_column(Text, default="")
    completion_evidence: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Requirement(Base):
    __tablename__ = "living_requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"), index=True
    )
    requirement: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[str] = mapped_column(Text)
    compliance: Mapped[str] = mapped_column(String(40), default="unassessed")
    evidence: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(120), default="Unassigned")


class AuditEvent(Base):
    __tablename__ = "living_audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(120))
    actor: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text, default="")
    changes: Mapped[list] = mapped_column(JSON)
    undone: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ImportPreview(Base):
    __tablename__ = "living_import_previews"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    rows: Mapped[list] = mapped_column(JSON)
    errors: Mapped[list] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64))
    committed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ActionDetails(Base):
    __tablename__ = "living_action_details"
    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(
        ForeignKey("executive_actions.id"), unique=True
    )
    depends_on: Mapped[list] = mapped_column(JSON, default=list)
    completion_evidence: Mapped[str] = mapped_column(Text, default="")
