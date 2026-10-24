from datetime import date, datetime

from pydantic import Field

from app.schemas.common import MisiSchema
from app.schemas.enrichment import (
    EnrichmentRunRead,
    FieldIntelligenceRead,
    OpportunityEnrichmentRead,
)
from app.schemas.executive_action import ExecutiveActionRead
from app.schemas.finance_forecast import FinanceForecastRead
from app.schemas.opportunity import OpportunityRead


class MarketSignalBase(MisiSchema):
    title: str
    buyer_name: str
    sector: str
    region: str
    estimated_value: float | None = None
    expected_tender_date: date | None = None
    source_type: str
    source_url: str | None = None
    source_attribution: str = ""
    confidence_score: float = 0
    suggested_action: str = ""
    likely_mitie_fit: str = "Unknown"
    potential_disciplines: list[str] = Field(default_factory=list)
    ai_rationale: str = ""


class MarketSignalCreate(MarketSignalBase):
    pass


class MarketSignalRead(MarketSignalBase):
    id: int
    created_at: datetime


class MarketSignalConversionResponse(MisiSchema):
    market_signal: MarketSignalRead
    opportunity: OpportunityRead
    enrichment_run: EnrichmentRunRead
    field_intelligence: list[FieldIntelligenceRead]
    opportunity_enrichment: OpportunityEnrichmentRead
    executive_action: ExecutiveActionRead | None = None
    finance_forecast: FinanceForecastRead | None = None
    created_opportunity: bool
    fields_filled: int
    fields_still_unknown: int
    conversion_summary: str
