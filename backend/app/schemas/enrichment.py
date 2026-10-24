from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import MisiSchema

FieldValueType = Literal[
    "known",
    "inferred",
    "estimated",
    "unknown",
    "user_provided",
    "system_calculated",
]


class EnrichmentRunBase(MisiSchema):
    run_type: str = Field(min_length=1, max_length=80)
    status: str = Field(min_length=1, max_length=40)
    user_query: str = ""
    opportunity_id: int | None = None
    finished_at: datetime | None = None
    model_used: str = ""
    search_performed: bool = False
    sources_checked: list[Any] = Field(default_factory=list)
    records_created: int = Field(default=0, ge=0)
    records_updated: int = Field(default=0, ge=0)
    error_message: str | None = None


class EnrichmentRunCreate(EnrichmentRunBase):
    pass


class EnrichmentRunRead(EnrichmentRunBase):
    id: int
    started_at: datetime


class FieldIntelligenceBase(MisiSchema):
    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: int = Field(ge=1)
    field_name: str = Field(min_length=1, max_length=120)
    field_value: Any | None = None
    value_type: FieldValueType
    confidence_score: float = Field(default=0, ge=0, le=1)
    rationale: str = ""
    source_urls: list[str] = Field(default_factory=list)
    source_titles: list[str] = Field(default_factory=list)
    recommended_next_step: str = ""
    needs_user_confirmation: bool = False


class FieldIntelligenceCreate(FieldIntelligenceBase):
    pass


class FieldIntelligenceRead(FieldIntelligenceBase):
    id: int
    created_at: datetime
    updated_at: datetime


class OpportunityEnrichmentBase(MisiSchema):
    opportunity_id: int = Field(ge=1)
    enrichment_run_id: int = Field(ge=1)
    buyer_summary: str = ""
    opportunity_summary: str = ""
    likely_scope: str = ""
    estimated_contract_value_rationale: str = ""
    likely_buyer_drivers: list[str] = Field(default_factory=list)
    compliance_drivers: list[str] = Field(default_factory=list)
    competitor_assessment: str = ""
    commercial_assessment: str = ""
    mobilisation_assessment: str = ""
    self_delivery_assessment: str = ""
    finance_assessment: str = ""
    executive_recommendation: str = ""
    unknowns: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(default=0, ge=0, le=1)


class OpportunityEnrichmentCreate(OpportunityEnrichmentBase):
    pass


class OpportunityEnrichmentRead(OpportunityEnrichmentBase):
    id: int
    created_at: datetime
