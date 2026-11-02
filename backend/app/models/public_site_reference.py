from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PublicSiteReference(Base):
    """A published location association, not a verified current occupier."""

    __tablename__ = "public_site_references"
    __table_args__ = (Index("ix_public_site_references_uprn", "uprn"),)

    source_record_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    uprn: Mapped[str] = mapped_column(String(32), nullable=False)
    organisation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    organisation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    site_name: Mapped[str] = mapped_column(String(255), nullable=False)
    postcode: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_period: Mapped[str] = mapped_column(String(40), nullable=False)
