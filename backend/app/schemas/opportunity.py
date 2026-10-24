from datetime import date, datetime

from pydantic import Field

from app.schemas.common import MisiSchema


class OpportunityLatestAIAnalysis(MisiSchema):
    strategic_fit_score: float
    win_probability: float
    risk_rating: str
    bid_no_bid_recommendation: str
    likely_buyer_drivers: list[str] = Field(default_factory=list)
    competitor_threat: str
    margin_commentary: str
    mobilisation_risks: list[str] = Field(default_factory=list)
    commercial_risks: list[str] = Field(default_factory=list)
    self_delivery_assessment: str
    recommended_action: str
    executive_summary: str
    created_at: datetime


class OpportunityBase(MisiSchema):
    name: str
    buyer_name: str
    sector: str
    region: str
    source_type: str
    stage: str
    owner: str
    estimated_annual_revenue: float = 0
    estimated_total_contract_value: float = 0
    estimated_gross_margin: float = 0
    margin_percentage: float = 0
    probability: float = 0
    weighted_value: float = 0
    submission_deadline: date | None = None
    forecast_start_month: str | None = None
    self_delivery_fit: str = "unknown"
    risk_rating: str = "unknown"
    strategic_fit_score: float = 0
    bid_no_bid_recommendation: str = "review_required"
    recommended_action: str = ""


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityRead(OpportunityBase):
    id: int
    created_at: datetime
    updated_at: datetime
    weighted_pipeline_value: float = 0
    strategic_must_win: bool = False
    calculated_risk_rating: str = "unknown"
    margin_warning: bool = False
    deadline_warning: bool = False
    self_delivery_capture: bool = False
    executive_escalation: bool = False
    calculated_bid_no_bid_recommendation: str = "Watch"
    priority_score: float = 0
    calculated_recommended_action: str = ""
    latest_ai_analysis: OpportunityLatestAIAnalysis | None = None
