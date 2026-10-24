from datetime import date, datetime

from app.schemas.common import MisiSchema
from app.schemas.dashboard import DashboardSummaryRead
from app.schemas.executive_action import ExecutiveActionRead
from app.schemas.finance_forecast import FinanceForecastSummaryRead
from app.schemas.intelligence import ExecutiveSummaryResult
from app.schemas.opportunity import OpportunityRead


class ReportAggregate(MisiSchema):
    label: str
    value: float
    count: int


class SelfDeliveryReportOpportunity(MisiSchema):
    opportunity_id: int
    name: str
    buyer_name: str
    discipline: str
    estimated_value: float
    weighted_value: float
    risk_rating: str
    recommended_action: str


class SelfDeliveryReportSummary(MisiSchema):
    opportunity_value: float
    value_captured: float
    value_at_risk: float
    accepted_count: int
    declined_count: int
    conversion_rate: float
    top_displaced_suppliers: list[ReportAggregate]
    disciplines_with_highest_opportunity: list[ReportAggregate]
    route_opportunities: list[SelfDeliveryReportOpportunity]
    leakage_risks: list[SelfDeliveryReportOpportunity]


class ReportRiskRecommendation(MisiSchema):
    priority: str
    category: str
    summary: str
    commercial_value: float | None = None
    owner: str | None = None
    recommended_action: str


class ExecutiveSummaryReportRead(MisiSchema):
    report_name: str
    generated_at: datetime
    reporting_date: date
    audience: list[str]
    data_note: str
    dashboard_kpis: DashboardSummaryRead
    leadership_summary: ExecutiveSummaryResult
    top_opportunities: list[OpportunityRead]
    finance_forecast: FinanceForecastSummaryRead
    self_delivery_summary: SelfDeliveryReportSummary
    executive_actions: list[ExecutiveActionRead]
    risks_and_recommendations: list[ReportRiskRecommendation]
