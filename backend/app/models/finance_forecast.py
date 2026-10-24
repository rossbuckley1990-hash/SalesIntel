from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class FinanceForecast(Base):
    __tablename__ = "finance_forecasts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id"),
        index=True,
    )
    forecast_category: Mapped[str] = mapped_column(String(80), index=True)
    start_month: Mapped[str] = mapped_column(String(7), index=True)
    revenue_to_year_end: Mapped[float] = mapped_column(Float, default=0)
    estimated_margin: Mapped[float] = mapped_column(Float, default=0)
    margin_percentage: Mapped[float] = mapped_column(Float, default=0)
    probability_weighting: Mapped[float] = mapped_column(Float, default=0)
    risk_adjustment: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")

    opportunity: Mapped["Opportunity"] = relationship(back_populates="finance_forecasts")
