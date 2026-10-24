from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.common import MisiSchema
from app.schemas.enrichment import (
    EnrichmentRunRead,
    FieldIntelligenceRead,
    FieldValueType,
    OpportunityEnrichmentRead,
)
from app.schemas.executive_action import ExecutiveActionRead
from app.schemas.finance_forecast import FinanceForecastRead
from app.schemas.opportunity import OpportunityRead


class ResearchOpportunityRequest(MisiSchema):
    query: str = Field(min_length=4, max_length=600)
    sector_hint: str | None = Field(default=None, max_length=120)
    region_hint: str | None = Field(default=None, max_length=120)
    buyer_hint: str | None = Field(default=None, max_length=255)
    create_opportunity: bool = True


class ResearchOpportunitySource(MisiSchema):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    source_type: str = "Public web"
    relevance: str = ""


AIFieldValueType = Literal["known", "inferred", "estimated", "unknown"]


class ResearchOpportunityAIFieldBase(MisiSchema):
    value_type: AIFieldValueType
    confidence_score: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)
    source_urls: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unknown_values_have_zero_confidence(self):
        if self.value_type == "unknown" and self.confidence_score != 0:
            raise ValueError("Unknown AI enrichment fields must have confidence_score 0.")
        return self


class ResearchOpportunityAITextField(ResearchOpportunityAIFieldBase):
    value: str | None = None


class ResearchOpportunityAINumericField(ResearchOpportunityAIFieldBase):
    value: float | None = None


class ResearchOpportunityAIOpportunity(MisiSchema):
    name: ResearchOpportunityAITextField
    buyer_name: ResearchOpportunityAITextField
    sector: ResearchOpportunityAITextField
    region: ResearchOpportunityAITextField
    source_type: ResearchOpportunityAITextField
    stage: ResearchOpportunityAITextField
    estimated_annual_revenue: ResearchOpportunityAINumericField
    estimated_total_contract_value: ResearchOpportunityAINumericField
    estimated_gross_margin: ResearchOpportunityAINumericField
    margin_percentage: ResearchOpportunityAINumericField
    probability: ResearchOpportunityAINumericField
    submission_deadline: ResearchOpportunityAITextField
    forecast_start_month: ResearchOpportunityAITextField
    self_delivery_fit: ResearchOpportunityAITextField
    risk_rating: ResearchOpportunityAITextField
    strategic_fit_score: ResearchOpportunityAINumericField
    bid_no_bid_recommendation: ResearchOpportunityAITextField
    recommended_action: ResearchOpportunityAITextField


class ResearchOpportunityAIIntelligence(MisiSchema):
    buyer_summary: str = Field(min_length=1)
    opportunity_summary: str = Field(min_length=1)
    likely_scope: list[str] = Field(default_factory=list)
    likely_buyer_drivers: list[str] = Field(default_factory=list)
    compliance_drivers: list[str] = Field(default_factory=list)
    competitor_assessment: str = Field(min_length=1)
    commercial_assessment: str = Field(min_length=1)
    mobilisation_assessment: str = Field(min_length=1)
    self_delivery_assessment: str = Field(min_length=1)
    finance_assessment: str = Field(min_length=1)
    executive_recommendation: str = Field(min_length=1)
    unknowns: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0, le=1)


class ResearchOpportunityAIExecutiveAction(MisiSchema):
    priority: Literal["Low", "Medium", "High", "Critical"]
    category: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    due_date: str = Field(min_length=1)
    commercial_value: float = Field(ge=0)
    reason: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)


class ResearchOpportunityAIResult(MisiSchema):
    opportunity: ResearchOpportunityAIOpportunity
    intelligence: ResearchOpportunityAIIntelligence
    executive_action: ResearchOpportunityAIExecutiveAction
    sources: list[ResearchOpportunitySource] = Field(default_factory=list)


class ResearchOpportunityFieldIntelligence(MisiSchema):
    field_name: str = Field(min_length=1, max_length=120)
    field_value: Any | None = None
    value_type: FieldValueType
    confidence_score: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)
    source_urls: list[str] = Field(default_factory=list)
    source_titles: list[str] = Field(default_factory=list)
    recommended_next_step: str = Field(min_length=1)
    needs_user_confirmation: bool


class ResearchOpportunityDraft(MisiSchema):
    name: str | None = None
    buyer_name: str | None = None
    sector: str | None = None
    region: str | None = None
    source_type: str | None = None
    stage: str | None = None
    estimated_annual_revenue: float | None = None
    estimated_total_contract_value: float | None = None
    estimated_gross_margin: float | None = None
    margin_percentage: float | None = None
    probability: float | None = None
    weighted_value: float | None = None
    submission_deadline: str | None = None
    forecast_start_month: str | None = None
    self_delivery_fit: str | None = None
    risk_rating: str | None = None
    strategic_fit_score: float | None = None
    bid_no_bid_recommendation: str | None = None
    recommended_action: str | None = None
    finance_forecast_category: str | None = None
    executive_action: str | None = None


class ResearchOpportunityEnrichmentPack(MisiSchema):
    buyer_summary: str
    opportunity_summary: str
    likely_scope: list[str] = Field(default_factory=list)
    estimated_contract_value_rationale: str
    likely_buyer_drivers: list[str] = Field(default_factory=list)
    compliance_drivers: list[str] = Field(default_factory=list)
    competitor_threat: str = "Unknown"
    competitor_assessment: str
    mobilisation_risks: list[str] = Field(default_factory=list)
    mobilisation_assessment: str
    commercial_risks: list[str] = Field(default_factory=list)
    commercial_assessment: str
    self_delivery_assessment: str
    finance_assessment: str
    executive_recommendation: str
    unknowns: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0, le=1)


class ResearchOpportunityResponse(MisiSchema):
    enrichment_run: EnrichmentRunRead
    created_opportunity: bool
    opportunity: OpportunityRead | None = None
    draft_opportunity: ResearchOpportunityDraft
    field_intelligence: list[FieldIntelligenceRead] = Field(default_factory=list)
    draft_field_intelligence: list[ResearchOpportunityFieldIntelligence] = Field(
        default_factory=list,
    )
    opportunity_enrichment: OpportunityEnrichmentRead | None = None
    draft_enrichment: ResearchOpportunityEnrichmentPack
    executive_action: ExecutiveActionRead | None = None
    finance_forecast: FinanceForecastRead | None = None
    sources: list[ResearchOpportunitySource] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0, le=1)


class ChatGPTAssistPromptRequest(ResearchOpportunityRequest):
    pass


class ChatGPTAssistPromptResponse(MisiSchema):
    prompt: str
    expected_output_schema: dict[str, Any]
    copy_steps: list[str]
    safety_note: str


class ChatGPTAssistImportRequest(ResearchOpportunityRequest):
    result_json: str = Field(min_length=2, max_length=160_000)


class AutofillOpportunitiesRequest(MisiSchema):
    only_incomplete: bool = True
    limit: int = Field(default=10, ge=1, le=50)
    allow_overwrite: bool = False
    overwrite_confidence_threshold: float = Field(default=0.9, ge=0.5, le=1)


class AutofillOpportunityResult(MisiSchema):
    opportunity_id: int
    opportunity_name: str
    status: Literal["enriched", "skipped", "failed"]
    enrichment_run_id: int | None = None
    fields_filled: int = Field(default=0, ge=0)
    fields_preserved: int = Field(default=0, ge=0)
    fields_still_unknown: int = Field(default=0, ge=0)
    confidence_warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None


class AutofillOpportunitiesResponse(MisiSchema):
    records_scanned: int = Field(ge=0)
    records_enriched: int = Field(ge=0)
    records_skipped: int = Field(ge=0)
    records_failed: int = Field(ge=0)
    fields_filled: int = Field(ge=0)
    fields_still_unknown: int = Field(ge=0)
    confidence_warnings: list[str] = Field(default_factory=list)
    results: list[AutofillOpportunityResult] = Field(default_factory=list)
