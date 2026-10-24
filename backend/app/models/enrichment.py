from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


FIELD_VALUE_TYPES = (
    "known",
    "inferred",
    "estimated",
    "unknown",
    "user_provided",
    "system_calculated",
)


class EnrichmentRun(Base):
    __tablename__ = "enrichment_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    user_query: Mapped[str] = mapped_column(Text, default="")
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    model_used: Mapped[str] = mapped_column(String(120), default="")
    search_performed: Mapped[bool] = mapped_column(Boolean, default=False)
    sources_checked: Mapped[list[object]] = mapped_column(JSON, default=list)
    records_created: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    opportunity: Mapped["Opportunity | None"] = relationship(
        back_populates="enrichment_runs",
    )
    opportunity_enrichments: Mapped[list["OpportunityEnrichment"]] = relationship(
        back_populates="enrichment_run",
        cascade="all, delete-orphan",
    )


class FieldIntelligence(Base):
    __tablename__ = "field_intelligence"
    __table_args__ = (
        CheckConstraint(
            "value_type IN "
            "('known', 'inferred', 'estimated', 'unknown', "
            "'user_provided', 'system_calculated')",
            name="ck_field_intelligence_value_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    field_name: Mapped[str] = mapped_column(String(120), index=True)
    field_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    value_type: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    source_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_titles: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommended_next_step: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
    )
    needs_user_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class OpportunityEnrichment(Base):
    __tablename__ = "opportunity_enrichments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"),
        index=True,
    )
    enrichment_run_id: Mapped[int] = mapped_column(
        ForeignKey("enrichment_runs.id"),
        index=True,
    )
    buyer_summary: Mapped[str] = mapped_column(Text, default="")
    opportunity_summary: Mapped[str] = mapped_column(Text, default="")
    likely_scope: Mapped[str] = mapped_column(Text, default="")
    estimated_contract_value_rationale: Mapped[str] = mapped_column(Text, default="")
    likely_buyer_drivers: Mapped[list[str]] = mapped_column(JSON, default=list)
    compliance_drivers: Mapped[list[str]] = mapped_column(JSON, default=list)
    competitor_assessment: Mapped[str] = mapped_column(Text, default="")
    commercial_assessment: Mapped[str] = mapped_column(Text, default="")
    mobilisation_assessment: Mapped[str] = mapped_column(Text, default="")
    self_delivery_assessment: Mapped[str] = mapped_column(Text, default="")
    finance_assessment: Mapped[str] = mapped_column(Text, default="")
    executive_recommendation: Mapped[str] = mapped_column(Text, default="")
    unknowns: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommended_next_steps: Mapped[list[str]] = mapped_column(JSON, default=list)
    overall_confidence: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    opportunity: Mapped["Opportunity"] = relationship(
        back_populates="opportunity_enrichments",
    )
    enrichment_run: Mapped["EnrichmentRun"] = relationship(
        back_populates="opportunity_enrichments",
    )
