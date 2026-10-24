from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MarketSignal(Base):
    __tablename__ = "market_signals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    buyer_name: Mapped[str] = mapped_column(String(255), index=True)
    sector: Mapped[str] = mapped_column(String(120), index=True)
    region: Mapped[str] = mapped_column(String(120), index=True)
    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_tender_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_type: Mapped[str] = mapped_column(String(80), index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_attribution: Mapped[str] = mapped_column(Text, default="", server_default="")
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    suggested_action: Mapped[str] = mapped_column(Text, default="")
    likely_mitie_fit: Mapped[str] = mapped_column(String(40), default="Unknown", server_default="Unknown")
    potential_disciplines: Mapped[list[str]] = mapped_column(JSON, default=list)
    ai_rationale: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
