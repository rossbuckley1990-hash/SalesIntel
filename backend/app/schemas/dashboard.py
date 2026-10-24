from app.schemas.common import MisiSchema
from app.schemas.executive_action import ExecutiveActionRead
from app.schemas.opportunity import OpportunityRead


class ForecastPoint(MisiSchema):
    month: str
    value: float


class DashboardSummaryRead(MisiSchema):
    total_pipeline_value: float
    weighted_pipeline_value: float
    estimated_gross_margin: float
    average_margin_percentage: float
    live_opportunity_count: int
    strategic_must_win_count: int
    live_tender_count: int
    market_signal_count: int
    high_risk_count: int
    urgent_deadline_count: int
    executive_summary_text: str
    monthly_revenue_forecast: list[ForecastPoint]
    monthly_margin_forecast: list[ForecastPoint]
    top_opportunities: list[OpportunityRead]
    top_executive_actions: list[ExecutiveActionRead]

