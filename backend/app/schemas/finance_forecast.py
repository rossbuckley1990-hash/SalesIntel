from app.schemas.common import MisiSchema


class FinanceForecastBase(MisiSchema):
    opportunity_id: int
    forecast_category: str
    start_month: str
    revenue_to_year_end: float = 0
    estimated_margin: float = 0
    margin_percentage: float = 0
    probability_weighting: float = 0
    risk_adjustment: float = 0
    notes: str = ""


class FinanceForecastCreate(FinanceForecastBase):
    pass


class FinanceForecastRead(FinanceForecastBase):
    id: int


class FinanceForecastPoint(MisiSchema):
    month: str
    value: float


class SecuredWorkItem(MisiSchema):
    opportunity_id: int
    opportunity_name: str
    client: str
    won_revenue: float
    won_gross_margin: float
    margin_percentage: float
    delivery_start_month: str
    business_unit: str | None = None
    discipline: str | None = None
    confidence: float


class OpenForecastItem(MisiSchema):
    opportunity_id: int
    opportunity_name: str
    client: str
    forecast_start_month: str
    revenue_to_financial_year_end: float
    estimated_margin: float
    margin_percentage: float
    probability_weighting: float
    risk_adjustment: float
    forecast_category: str
    weighted_revenue: float
    weighted_margin: float
    risk_adjusted_revenue: float
    risk_adjusted_margin: float


class FinanceWarning(MisiSchema):
    opportunity_id: int
    opportunity_name: str
    client: str
    margin_percentage: float
    threshold_percentage: float
    reason: str


class FinanceReviewItem(MisiSchema):
    opportunity_id: int
    opportunity_name: str
    client: str
    priority: str
    category: str
    reason: str
    recommended_action: str


class FinanceForecastSummaryRead(MisiSchema):
    financial_year: str
    financial_year_start: int
    financial_year_end: int
    financial_year_months: list[str]
    monthly_revenue: list[FinanceForecastPoint]
    monthly_margin: list[FinanceForecastPoint]
    secured_revenue: float
    secured_gross_margin: float
    secured_margin_percentage: float
    open_weighted_revenue: float
    open_weighted_margin: float
    risk_adjusted_revenue: float
    risk_adjusted_margin: float
    forecast_to_financial_year_end: float
    forecast_margin_to_financial_year_end: float
    secured_work: list[SecuredWorkItem]
    open_opportunities: list[OpenForecastItem]
    margin_warnings: list[FinanceWarning]
    finance_review_items: list[FinanceReviewItem]
