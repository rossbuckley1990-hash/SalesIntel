from datetime import date

from sqlalchemy.orm import sessionmaker

from app.db import Base, create_database_engine
from app.services.dashboard import build_dashboard_summary
from app.services.seed import seed_sample_data


def test_dashboard_summary_calculates_seeded_pipeline_values() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine)

    with testing_session() as db:
        seed_sample_data(db)

        summary = build_dashboard_summary(db, today=date(2026, 6, 29))

    assert summary.total_pipeline_value == 33350000
    assert summary.weighted_pipeline_value == 17438400
    assert summary.estimated_gross_margin == 7205200
    assert summary.average_margin_percentage == 21.6
    assert summary.live_opportunity_count == 22
    assert summary.strategic_must_win_count == 5
    assert summary.live_tender_count == 18
    assert summary.market_signal_count == 15
    assert summary.high_risk_count == 4
    assert summary.urgent_deadline_count == 0
    assert len(summary.monthly_revenue_forecast) == 12
    assert len(summary.monthly_margin_forecast) == 12
    assert summary.monthly_revenue_forecast[0].month == "2026-07"
    assert summary.monthly_revenue_forecast[0].value == 180000
    assert summary.monthly_margin_forecast[-1].month == "2027-06"
    assert summary.monthly_margin_forecast[-1].value == 95000
    assert summary.top_opportunities[0].buyer_name == "Sovereign Cloud Hosting"
    assert (
        summary.top_opportunities[0].calculated_bid_no_bid_recommendation
        == "Pursue with executive sponsor"
    )
    assert summary.top_executive_actions[0].priority == "high"
    assert "Recommended next action" in summary.executive_summary_text


def test_dashboard_summary_respects_filters() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine)

    with testing_session() as db:
        seed_sample_data(db)

        summary = build_dashboard_summary(db, sector="Retail", today=date(2026, 6, 29))

    assert summary.total_pipeline_value == 2010000
    assert summary.weighted_pipeline_value == 1173600
    assert summary.estimated_gross_margin == 422100
    assert summary.average_margin_percentage == 21
    assert summary.live_opportunity_count == 2
    assert summary.strategic_must_win_count == 1
    assert summary.live_tender_count == 1
    assert summary.market_signal_count == 1
    assert summary.high_risk_count == 0
    assert summary.urgent_deadline_count == 0
    assert {item.buyer_name for item in summary.top_opportunities} == {
        "Northshire Retail Group",
        "British Retail Parks Trust",
    }
