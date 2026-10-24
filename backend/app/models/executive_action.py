from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ExecutiveAction(Base):
    __tablename__ = "executive_actions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    priority: Mapped[str] = mapped_column(String(40), index=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    owner: Mapped[str] = mapped_column(String(120), index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    related_opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id"),
        nullable=True,
        index=True,
    )
    commercial_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)

    related_opportunity: Mapped["Opportunity | None"] = relationship(
        back_populates="executive_actions",
    )
