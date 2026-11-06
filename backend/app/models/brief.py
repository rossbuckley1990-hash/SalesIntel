"""When someone last reviewed an opportunity, so the brief can show what is new since then."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.tenancy import TenantScoped


class BriefReview(TenantScoped, Base):
    __tablename__ = 'si_brief_reviews'
    __table_args__ = (UniqueConstraint('organisation_id', 'key', 'user_id', name='uq_si_brief_review'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # pr:, mo:, sh:, mc: or acct:
    user_id: Mapped[int | None] = mapped_column(Integer)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
