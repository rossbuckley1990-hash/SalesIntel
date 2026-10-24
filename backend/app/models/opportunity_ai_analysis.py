from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class OpportunityAIAnalysis(Base):
    __tablename__ = "opportunity_ai_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"),
        index=True,
    )
    model: Mapped[str] = mapped_column(String(120), default="")
    strategic_fit_score: Mapped[float] = mapped_column(Float)
    win_probability: Mapped[float] = mapped_column(Float)
    risk_rating: Mapped[str] = mapped_column(String(20), index=True)
    bid_no_bid_recommendation: Mapped[str] = mapped_column(String(80), index=True)
    likely_buyer_drivers: Mapped[list[str]] = mapped_column(JSON, default=list)
    competitor_threat: Mapped[str] = mapped_column(String(20), index=True)
    margin_commentary: Mapped[str] = mapped_column(Text, default="")
    mobilisation_risks: Mapped[list[str]] = mapped_column(JSON, default=list)
    commercial_risks: Mapped[list[str]] = mapped_column(JSON, default=list)
    self_delivery_assessment: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    executive_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    opportunity: Mapped["Opportunity"] = relationship(back_populates="ai_analyses")
