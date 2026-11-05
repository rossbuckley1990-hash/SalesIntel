"""Private-sector prospects found by web research, and the searches that found them."""
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base
from app.models.tenancy import TenantScoped


class ProspectSearch(TenantScoped, Base):
    __tablename__ = 'prospect_searches'
    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='running')
    error: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(80), nullable=False, default='')
    prospect_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    sources_reviewed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_prospect_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Prospect(TenantScoped, Base):
    __tablename__ = 'prospects'
    __table_args__ = (UniqueConstraint('organisation_id', 'dedup_key', name='uq_prospects_dedup'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dedup_key: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='new')
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    search_id: Mapped[int | None] = mapped_column(Integer)
    opportunity_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
