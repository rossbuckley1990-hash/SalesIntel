"""One row per contract, assembled from every published record of it.

A row describes what the sources say, not whether the contract is being delivered.
Links keep how each record joined the contract, and how sure that join is,
separately from any view of the commercial opportunity.
"""
from datetime import datetime
from typing import Any
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class MarketContract(Base):
    __tablename__ = 'market_contracts'
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    ocid: Mapped[str | None] = mapped_column(String(256), index=True)
    buyer: Mapped[str] = mapped_column(Text, nullable=False)
    supplier: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    fit: Mapped[str] = mapped_column(String(16), nullable=False)
    nation: Mapped[str] = mapped_column(String(32), nullable=False, default='Not stated', index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(32), index=True)
    end_date: Mapped[str | None] = mapped_column(String(10), index=True)
    end_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_evaluated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketContractLink(Base):
    __tablename__ = 'market_contract_links'
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey('market_contracts.id', ondelete='CASCADE'), nullable=False, index=True)
    member_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    source_key: Mapped[str] = mapped_column(String(80), nullable=False)
    ocid: Mapped[str | None] = mapped_column(String(256), index=True)
    lot: Mapped[str] = mapped_column(String(120), nullable=False, default='')
    method: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
