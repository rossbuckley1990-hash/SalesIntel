"""Research on demand: a missing piece of account intelligence turned into a scoped, persistent research request.

Each request asks one question (who is the Facilities Director, who holds the contract, when does it end...) and
records exactly what was found, with quotes and sources, or that it was not found. A "not found" is never turned
into a guess. Private to the workspace (row-level security on PostgreSQL)."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.tenancy import TenantScoped


class GapRequest(TenantScoped, Base):
    __tablename__ = 'si_gap_requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    gap: Mapped[str] = mapped_column(String(32), nullable=False)  # find_role, verify_contact, incumbent, contract_end, site_operator, award_document, evaluation_criteria, site_status
    subject: Mapped[str] = mapped_column(String(160), nullable=False, default='')  # e.g. the role sought, or the contact id
    question: Mapped[str] = mapped_column(Text, nullable=False)
    lead_key: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # queued, running, resolved, partial, conflicting, not_found, provider_unavailable, needs_human, failed
    summary: Mapped[str] = mapped_column(Text, nullable=False, default='')
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    rejected: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    job_id: Mapped[int | None] = mapped_column(Integer)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
