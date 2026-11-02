"""Candidate links between public LFB visits and historical NHS site references."""
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class LfbInspectionMatch(Base):
    __tablename__ = "lfb_inspection_matches"
    __table_args__ = (Index("ix_lfb_inspection_matches_uprn", "uprn"),)
    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    uprn: Mapped[str] = mapped_column(String(32), nullable=False)
    organisation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    site_name: Mapped[str] = mapped_column(String(255), nullable=False)
    site_reference_url: Mapped[str] = mapped_column(Text, nullable=False)
    site_reference_period: Mapped[str] = mapped_column(String(40), nullable=False)
    postcode: Mapped[str] = mapped_column(String(32), nullable=False)
    inspection_address: Mapped[str] = mapped_column(Text, nullable=False)
    property_use: Mapped[str] = mapped_column(String(255), nullable=False)
    reason_or_outcome: Mapped[str] = mapped_column(String(255), nullable=False)
    completed_on: Mapped[date] = mapped_column(Date, nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
