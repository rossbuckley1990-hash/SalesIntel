from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    buyer_name: Mapped[str] = mapped_column(String(255), index=True)
    sector: Mapped[str] = mapped_column(String(120), index=True)
    region: Mapped[str] = mapped_column(String(120), index=True)
    source_type: Mapped[str] = mapped_column(String(80), index=True)
    stage: Mapped[str] = mapped_column(String(80), index=True)
    owner: Mapped[str] = mapped_column(String(120), index=True)
    estimated_annual_revenue: Mapped[float] = mapped_column(Float, default=0)
    estimated_total_contract_value: Mapped[float] = mapped_column(Float, default=0)
    estimated_gross_margin: Mapped[float] = mapped_column(Float, default=0)
    margin_percentage: Mapped[float] = mapped_column(Float, default=0)
    probability: Mapped[float] = mapped_column(Float, default=0)
    weighted_value: Mapped[float] = mapped_column(Float, default=0)
    submission_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    forecast_start_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    self_delivery_fit: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    risk_rating: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    strategic_fit_score: Mapped[float] = mapped_column(Float, default=0)
    bid_no_bid_recommendation: Mapped[str] = mapped_column(
        String(40),
        default="review_required",
        index=True,
    )
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    executive_actions: Mapped[list["ExecutiveAction"]] = relationship(
        back_populates="related_opportunity",
        cascade="all, delete-orphan",
    )
    finance_forecasts: Mapped[list["FinanceForecast"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
    )
    ai_analyses: Mapped[list["OpportunityAIAnalysis"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
    )
    enrichment_runs: Mapped[list["EnrichmentRun"]] = relationship(
        back_populates="opportunity",
    )
    opportunity_enrichments: Mapped[list["OpportunityEnrichment"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
    )
