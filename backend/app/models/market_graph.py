"""Source-backed market relationship assertions, including historic intervals."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class MarketRelationship(Base):
    __tablename__ = 'market_relationships'
    __table_args__ = (UniqueConstraint('subject_entity_id', 'object_entity_id', 'relation_type',
                                       'source_revision_id', 'effective_from', name='uq_market_relationship_assertion'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_entity_id: Mapped[int] = mapped_column(ForeignKey('market_entities.id'), nullable=False, index=True)
    object_entity_id: Mapped[int] = mapped_column(ForeignKey('market_entities.id'), nullable=False, index=True)
    source_revision_id: Mapped[int] = mapped_column(ForeignKey('market_source_revisions.id'), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assertion_status: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
