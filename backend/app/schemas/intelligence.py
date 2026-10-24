from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.common import MisiSchema

BidRecommendation = Literal[
    "Pursue",
    "Pursue with executive sponsor",
    "Watch",
    "Qualify out",
    "No bid",
]
RiskLevel = Literal["Low", "Medium", "High", "Red", "Amber", "Green", "Unknown"]
OpportunityAIRiskRating = Literal["Green", "Amber", "Red"]
CompetitorThreat = Literal["Low", "Medium", "High"]
InternetIntelligenceType = Literal[
    "market_radar",
    "competitor_intelligence",
    "buyer_intelligence",
    "opportunity_intelligence",
    "tender_intelligence",
    "pipeline_forecast",
    "self_delivery",
]


class OpportunityAnalysisRequest(MisiSchema):
    name: str = Field(min_length=1, max_length=255)
    buyer_name: str = Field(min_length=1, max_length=255)
    sector: str | None = None
    region: str | None = None
    stage: str | None = None
    source_type: str | None = None
    estimated_annual_revenue: float = 0
    estimated_total_contract_value: float = 0
    estimated_gross_margin: float = 0
    margin_percentage: float = 0
    probability: float = 0
    submission_deadline: date | None = None
    forecast_start_month: str | None = None
    self_delivery_fit: str | None = None
    risk_rating: str | None = None
    strategic_fit_score: float = 0
    bid_no_bid_recommendation: str | None = None
    recommended_action: str | None = None
    context: str | None = Field(default=None, max_length=4000)


class OpportunityAnalysisResult(MisiSchema):
    opportunity_summary: str = Field(min_length=1)
    commercial_assessment: str = Field(min_length=1)
    risk_level: RiskLevel
    key_risks: list[str] = Field(default_factory=list, max_length=8)
    recommended_actions: list[str] = Field(default_factory=list, max_length=8)
    bid_no_bid_recommendation: BidRecommendation
    confidence_score: float = Field(ge=0, le=1)
    source_notes: list[str] = Field(default_factory=list, max_length=8)


class OpportunityAnalysisResponse(OpportunityAnalysisResult):
    model: str


class OpportunityAIAnalysisResult(MisiSchema):
    strategic_fit_score: float = Field(ge=0, le=100)
    win_probability: float = Field(ge=0, le=1)
    risk_rating: OpportunityAIRiskRating
    bid_no_bid_recommendation: BidRecommendation
    likely_buyer_drivers: list[str] = Field(default_factory=list, max_length=8)
    competitor_threat: CompetitorThreat
    margin_commentary: str = Field(min_length=1)
    mobilisation_risks: list[str] = Field(default_factory=list, max_length=8)
    commercial_risks: list[str] = Field(default_factory=list, max_length=8)
    self_delivery_assessment: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)


class ExecutiveSummaryResult(MisiSchema):
    headline: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    md_attention: list[str] = Field(default_factory=list, max_length=8)
    finance_attention: list[str] = Field(default_factory=list, max_length=8)
    sales_attention: list[str] = Field(default_factory=list, max_length=8)
    bid_team_attention: list[str] = Field(default_factory=list, max_length=8)
    risk_warnings: list[str] = Field(default_factory=list, max_length=8)
    next_best_actions: list[str] = Field(default_factory=list, max_length=8)


class InternetIntelligenceRequest(MisiSchema):
    intelligence_type: InternetIntelligenceType = "market_radar"
    query: str = Field(min_length=8, max_length=600)
    sector: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    buyer_name: str | None = Field(default=None, max_length=255)
    competitor_name: str | None = Field(default=None, max_length=255)
    opportunity_name: str | None = Field(default=None, max_length=255)


class InternetIntelligenceFinding(MisiSchema):
    title: str = Field(min_length=1)
    finding: str = Field(min_length=1)
    so_what: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)
    source_urls: list[str] = Field(default_factory=list, max_length=6)


class InternetIntelligenceResult(MisiSchema):
    intelligence_type: InternetIntelligenceType
    query: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    findings: list[InternetIntelligenceFinding] = Field(default_factory=list, max_length=8)
    source_urls: list[str] = Field(default_factory=list, max_length=12)
    risk_warnings: list[str] = Field(default_factory=list, max_length=8)
    next_best_actions: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8)
