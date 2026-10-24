from datetime import date

from sqlalchemy.orm import sessionmaker

from app.db import Base, create_database_engine
from app.models import FinanceForecast, Opportunity
from app.services.finance_summary import (
    build_finance_forecast_summary,
    financial_year_for_date,
    financial_year_months,
)


def test_financial_year_runs_april_to_march() -> None:
    assert financial_year_for_date(date(2026, 3, 31)) == (2025, 2026)
    assert financial_year_for_date(date(2026, 4, 1)) == (2026, 2027)
    assert financial_year_months(2026) == [
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
        "2026-10",
        "2026-11",
        "2026-12",
        "2027-01",
        "2027-02",
        "2027-03",
    ]


def test_finance_summary_separates_secured_and_open_forecast_values() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine)

    with testing_session() as db:
        won_opportunity = Opportunity(
            name="Won fire risk assessment call-off",
            buyer_name="Dales County Council",
            sector="Local Authority",
            region="Yorkshire",
            source_type="pipeline_upload",
            stage="Won",
            owner="Amira Shah",
            estimated_annual_revenue=120_000,
            estimated_total_contract_value=360_000,
            estimated_gross_margin=90_000,
            margin_percentage=25,
            probability=1,
            weighted_value=360_000,
            submission_deadline=date(2026, 3, 15),
            forecast_start_month="2026-04",
            self_delivery_fit="High",
            risk_rating="Low",
            strategic_fit_score=70,
            bid_no_bid_recommendation="Pursue",
            recommended_action="Mobilise delivery.",
        )
        open_opportunity = Opportunity(
            name="Open CCTV upgrade",
            buyer_name="Metro Estates",
            sector="Transport",
            region="London",
            source_type="crm_pipeline",
            stage="Pricing",
            owner="Priya Nair",
            estimated_annual_revenue=100_000,
            estimated_total_contract_value=300_000,
            estimated_gross_margin=60_000,
            margin_percentage=20,
            probability=0.5,
            weighted_value=150_000,
            submission_deadline=date(2026, 7, 15),
            forecast_start_month="2026-05",
            self_delivery_fit="Moderate",
            risk_rating="Medium",
            strategic_fit_score=65,
            bid_no_bid_recommendation="Watch",
            recommended_action="Review pricing.",
        )
        lost_opportunity = Opportunity(
            name="Lost extinguisher framework",
            buyer_name="Example Retail",
            sector="Retail",
            region="South East",
            source_type="crm_pipeline",
            stage="Lost",
            owner="James O'Neill",
            estimated_annual_revenue=999_999,
            estimated_total_contract_value=999_999,
            estimated_gross_margin=999_999,
            margin_percentage=99,
            probability=0,
            weighted_value=0,
            submission_deadline=date(2026, 7, 1),
            forecast_start_month="2026-06",
            self_delivery_fit="Low",
            risk_rating="High",
            strategic_fit_score=10,
            bid_no_bid_recommendation="No bid",
            recommended_action="Do not pursue.",
        )
        db.add_all([won_opportunity, open_opportunity, lost_opportunity])
        db.flush()

        db.add_all(
            [
                FinanceForecast(
                    opportunity_id=won_opportunity.id,
                    forecast_category="Committed",
                    start_month="2026-04",
                    revenue_to_year_end=120_000,
                    estimated_margin=30_000,
                    margin_percentage=25,
                    probability_weighting=1,
                    risk_adjustment=0,
                    notes="Secured from April.",
                ),
                FinanceForecast(
                    opportunity_id=open_opportunity.id,
                    forecast_category="Likely",
                    start_month="2026-05",
                    revenue_to_year_end=100_000,
                    estimated_margin=20_000,
                    margin_percentage=20,
                    probability_weighting=0.5,
                    risk_adjustment=0.1,
                    notes="Open forecast from May.",
                ),
                FinanceForecast(
                    opportunity_id=lost_opportunity.id,
                    forecast_category="Excluded",
                    start_month="2026-06",
                    revenue_to_year_end=999_999,
                    estimated_margin=999_999,
                    margin_percentage=99,
                    probability_weighting=1,
                    risk_adjustment=0,
                    notes="Should not contribute.",
                ),
            ]
        )
        db.commit()

        summary = build_finance_forecast_summary(db, as_of=date(2026, 6, 29))

    assert summary.financial_year == "2026/27"
    assert summary.secured_revenue == 120_000
    assert summary.secured_gross_margin == 30_000
    assert summary.secured_margin_percentage == 25
    assert summary.open_weighted_revenue == 50_000
    assert summary.open_weighted_margin == 10_000
    assert summary.risk_adjusted_revenue == 45_000
    assert summary.risk_adjusted_margin == 9_000
    assert summary.forecast_to_financial_year_end == 165_000
    assert summary.forecast_margin_to_financial_year_end == 39_000

    assert len(summary.secured_work) == 1
    assert summary.secured_work[0].delivery_start_month == "2026-04"
    assert summary.secured_work[0].confidence == 1
    assert len(summary.open_opportunities) == 1
    assert summary.open_opportunities[0].forecast_category == "Likely"

    monthly_revenue = {point.month: point.value for point in summary.monthly_revenue}
    monthly_margin = {point.month: point.value for point in summary.monthly_margin}
    assert monthly_revenue["2026-04"] == 10_000
    assert monthly_revenue["2026-05"] == 14_090.91
    assert monthly_revenue["2027-03"] == 14_090.91
    assert monthly_margin["2026-04"] == 2_500
    assert monthly_margin["2026-05"] == 3_318.18

    assert len(summary.margin_warnings) == 1
    assert summary.margin_warnings[0].client == "Metro Estates"
    assert summary.finance_review_items[0].category == "Margin warning"
