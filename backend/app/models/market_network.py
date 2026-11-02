"""Public market memory: immutable source revisions and conservative identity links."""
from datetime import datetime
from typing import Any
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class MarketSourceState(Base):
    __tablename__ = 'market_source_states'
    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_new_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(64))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cursor: Mapped[str | None] = mapped_column(Text)
    watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')


class SourceRevision(Base):
    __tablename__ = 'market_source_revisions'
    __table_args__ = (Index('uq_market_source_current', 'source_key', 'record_key', unique=True,
                            sqlite_where=text('superseded_at IS NULL'),
                            postgresql_where=text('superseded_at IS NULL')), )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    record_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    ocid: Mapped[str | None] = mapped_column(String(256), index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketEntity(Base):
    __tablename__ = 'market_entities'
    __table_args__ = (UniqueConstraint('identifier_scheme','identifier_value',name='uq_market_entity_identifier'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    identifier_scheme: Mapped[str] = mapped_column(String(128), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(256), nullable=False)
    identity_status: Mapped[str] = mapped_column(String(48), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketAward(Base):
    __tablename__ = 'market_awards'
    id: Mapped[int] = mapped_column(primary_key=True)
    source_revision_id: Mapped[int] = mapped_column(ForeignKey('market_source_revisions.id', ondelete='CASCADE'), nullable=False, index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey('market_entities.id'), index=True)
    award_id: Mapped[str | None] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    buyer: Mapped[str | None] = mapped_column(Text)
    supplier: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(64))
    award_date: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(16))
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default='unknown', server_default='unknown')


class MarketEntityEvidence(Base):
    __tablename__ = 'market_entity_evidence'
    __table_args__ = (UniqueConstraint('entity_id', 'source_revision_id', name='uq_market_entity_evidence'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey('market_entities.id'), nullable=False, index=True)
    source_revision_id: Mapped[int] = mapped_column(ForeignKey('market_source_revisions.id', ondelete='CASCADE'), nullable=False, index=True)
    assertion: Mapped[str] = mapped_column(String(64), nullable=False)
