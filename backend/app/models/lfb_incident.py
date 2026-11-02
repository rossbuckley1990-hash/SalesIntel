from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LfbImportRun(Base):
    __tablename__ = "lfb_import_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    acquisition_method: Mapped[str] = mapped_column(String(30), nullable=False, default="local_file", server_default="local_file")
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    rows_seen: Mapped[int] = mapped_column(Integer, nullable=False)
    records_imported: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_excluded: Mapped[int] = mapped_column(Integer, nullable=False)
    min_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class LfbIncident(Base):
    __tablename__ = "lfb_incidents"
    __table_args__ = (Index("ix_lfb_incidents_uprn_date", "uprn", "incident_date"),)

    incident_number: Mapped[str] = mapped_column(String(80), primary_key=True)
    incident_date: Mapped[date] = mapped_column(Date, nullable=False)
    incident_group: Mapped[str] = mapped_column(String(80), nullable=False)
    stop_code_description: Mapped[str] = mapped_column(String(100), nullable=False)
    property_category: Mapped[str] = mapped_column(String(100), nullable=False)
    property_type: Mapped[str] = mapped_column(String(255), nullable=False)
    address_qualifier: Mapped[str] = mapped_column(String(100), nullable=False)
    uprn: Mapped[str] = mapped_column(String(20), nullable=False)
    postcode_district: Mapped[str] = mapped_column(String(20), nullable=False)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("lfb_import_runs.id"), nullable=False)
