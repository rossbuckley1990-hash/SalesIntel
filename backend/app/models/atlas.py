"""Contract Atlas: who delivers fire and security work, for whom, and on what evidence.

Shared public facts (no workspace): contractor identities built from published procurement records, the names they appear
under, their links to the Market Network's canonical contracts, and identity conflicts left for a person to review. They
reference the existing source records and contracts and never copy them.

Private research (one workspace each, row-level security): relationships reported in case studies, press releases and
announcements that a workspace chose to investigate. Which competitors a company researches is itself confidential.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.tenancy import TenantScoped


class AtlasContractor(Base):
    """One contractor as published records identify it: by Companies House number where a source gives one, otherwise
    by its exact legal name. Never by a similar name, and never merged into its parent group."""
    __tablename__ = 'atlas_contractors'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)  # coh:<number> or name:<normalised legal name>
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_number: Mapped[str | None] = mapped_column(String(16), index=True)
    identity_basis: Mapped[str] = mapped_column(String(32), nullable=False)  # published_company_number, name_only
    group: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # parent from a reviewed registry filing, if any
    disciplines: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # family -> contracts naming it
    nations: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    contract_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AtlasAlias(Base):
    """A name a contractor appears under in a source, with where it was seen."""
    __tablename__ = 'atlas_aliases'
    __table_args__ = (UniqueConstraint('contractor_id', 'normalised', name='uq_atlas_alias'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey('atlas_contractors.id', ondelete='CASCADE'), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalised: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # contract_supplier, award_supplier, registry
    source_revision_id: Mapped[int | None] = mapped_column(Integer)


class AtlasContractParty(Base):
    """A contractor named as the supplier on a published contract (a direct award by that buyer). It points at the Market
    Network's canonical contract, which keeps every source, date and value with its basis."""
    __tablename__ = 'atlas_contract_parties'
    __table_args__ = (UniqueConstraint('contractor_id', 'contract_id', name='uq_atlas_contract_party'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey('atlas_contractors.id', ondelete='CASCADE'), nullable=False, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey('market_contracts.id', ondelete='CASCADE'), nullable=False, index=True)
    supplier_name_seen: Mapped[str] = mapped_column(String(255), nullable=False)
    match_basis: Mapped[str] = mapped_column(String(32), nullable=False)  # company_number, identical_legal_name, name_only
    customer_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(48), nullable=False, default='')  # from the buyer's postcode area; approximate at borders
    disciplines: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)  # maintenance, installation, maintenance_and_installation, not_stated
    route: Mapped[str] = mapped_column(String(32), nullable=False)  # framework_appointment, call_off, direct_award


class AtlasIdentityConflict(Base):
    """One legal name published with more than one company number. Left apart until a person decides."""
    __tablename__ = 'atlas_identity_conflicts'
    id: Mapped[int] = mapped_column(primary_key=True)
    normalised: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    company_numbers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    contractor_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='unresolved')


class AtlasRelationship(TenantScoped, Base):
    """A relationship a public source reports: a supplier's case study, a press release, a customer's report, an FM
    announcement. It keeps the exact words and every check made on them. It never carries a value or an end date."""
    __tablename__ = 'atlas_relationships'
    __table_args__ = (UniqueConstraint('organisation_id', 'supplier_key', 'customer_key', 'source_url', name='uq_atlas_relationship'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)  # direct_customer, subcontract, fm_delivery, partnership
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contractor_id: Mapped[int | None] = mapped_column(Integer, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    intermediary: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    services: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sites_mentioned: Mapped[str] = mapped_column(Text, nullable=False, default='')
    published_on: Mapped[str] = mapped_column(String(10), nullable=False, default='')  # only when the source shows it
    duration_stated: Mapped[str] = mapped_column(String(160), nullable=False, default='')  # only words the source uses
    currency: Mapped[str] = mapped_column(String(16), nullable=False)  # stated_ongoing, historical, not_stated
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checks: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # reported, unsupported, confirmed, rejected
    unknowns: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    job_id: Mapped[int | None] = mapped_column(Integer)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
