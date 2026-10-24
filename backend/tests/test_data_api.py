from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, create_database_engine, get_db
from app.main import create_app
from app.services.seed import seed_sample_data


def test_api_can_retrieve_seeded_data(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'api-seed.db'}")
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session() as db:
        seed_sample_data(db)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        assert len(client.get("/api/opportunities").json()) == 25
        assert len(client.get("/api/market-signals").json()) == 15
        assert len(client.get("/api/buyers").json()) == 10
        assert len(client.get("/api/competitors").json()) == 8
        assert len(client.get("/api/executive-actions").json()) == 15

        forecasts = client.get("/api/finance-forecast").json()
        assert len(forecasts) == 12
        assert len({item["start_month"] for item in forecasts}) == 12

        first_opportunity = client.get("/api/opportunities?limit=1").json()[0]
        assert first_opportunity["buyer_name"] == "Northshire Retail Group"
        assert first_opportunity["estimated_total_contract_value"] == 1440000
        assert first_opportunity["weighted_pipeline_value"] == 1036800
        assert first_opportunity["strategic_must_win"] is True
        assert first_opportunity["margin_warning"] is True
        assert first_opportunity["self_delivery_capture"] is True
        assert first_opportunity["calculated_bid_no_bid_recommendation"] == "Pursue"
        assert first_opportunity["priority_score"] > 0

        assert client.get("/api/opportunities/1").json()["name"] == (
            "Multi-site fire alarm maintenance renewal"
        )
        assert client.get("/api/buyers/1").json()["buyer_name"] == "Northshire Retail Group"
        assert client.get("/api/opportunities/9999").status_code == 404
        assert client.get("/api/buyers/9999").status_code == 404

        retail_opportunities = client.get("/api/opportunities?sector=Retail").json()
        assert len(retail_opportunities) == 2
        assert {item["buyer_name"] for item in retail_opportunities} == {
            "Northshire Retail Group",
            "British Retail Parks Trust",
        }

        negotiation_opportunities = client.get("/api/opportunities?stage=Negotiation").json()
        assert len(negotiation_opportunities) == 2

        owner_opportunities = client.get("/api/opportunities?owner=Priya%20Nair").json()
        assert len(owner_opportunities) == 4

        red_risk_opportunities = client.get("/api/opportunities?risk_rating=Red").json()
        assert len(red_risk_opportunities) == 5
        assert {item["calculated_risk_rating"] for item in red_risk_opportunities} == {"Red"}

        search_results = client.get("/api/opportunities?search=airport").json()
        assert len(search_results) == 1
        assert search_results[0]["buyer_name"] == "Riverside Airport Operations"

        utility_signals = client.get("/api/market-signals?sector=Utilities").json()
        assert len(utility_signals) == 2
        assert utility_signals[0]["likely_mitie_fit"] in {"High", "Medium", "Low"}
        assert utility_signals[0]["potential_disciplines"]
        assert utility_signals[0]["ai_rationale"]

        healthcare_buyers = client.get("/api/buyers?search=NHS").json()
        assert len(healthcare_buyers) == 1
        assert healthcare_buyers[0]["buyer_name"] == "South Coast NHS Partnership"

        security_competitors = client.get("/api/competitors?search=security").json()
        assert security_competitors

        technical_actions = client.get("/api/executive-actions?owner=Technical%20Director").json()
        assert len(technical_actions) == 2

        first_forecast = client.get("/api/finance-forecast?start_month=2026-07").json()
        assert len(first_forecast) == 1
        assert first_forecast[0]["revenue_to_year_end"] == 180000

        finance_summary = client.get(
            "/api/finance-forecast/summary?as_of=2026-06-29"
        ).json()
        assert finance_summary["financial_year"] == "2026/27"
        assert finance_summary["financial_year_months"][0] == "2026-04"
        assert finance_summary["financial_year_months"][-1] == "2027-03"
        assert finance_summary["secured_revenue"] > 0
        assert finance_summary["open_weighted_revenue"] > 0
        assert finance_summary["risk_adjusted_revenue"] > 0
        assert finance_summary["forecast_to_financial_year_end"] == (
            finance_summary["secured_revenue"] + finance_summary["risk_adjusted_revenue"]
        )
        assert finance_summary["secured_work"]
        assert finance_summary["open_opportunities"]

        dashboard = client.get("/api/dashboard").json()
        assert dashboard["live_opportunity_count"] == 22
        assert dashboard["market_signal_count"] == 15
        assert len(dashboard["top_opportunities"]) == 5
        assert dashboard["top_opportunities"][0]["priority_score"] > 0
        assert dashboard["top_opportunities"][0]["executive_escalation"] is True

        red_dashboard = client.get("/api/dashboard?risk_rating=Red").json()
        assert red_dashboard["live_opportunity_count"] == 4
        assert red_dashboard["high_risk_count"] == 4
        assert {
            item["calculated_risk_rating"] for item in red_dashboard["top_opportunities"]
        } == {"Red"}

        conversion = client.post("/api/market-signals/1/convert")
        assert conversion.status_code == 200
        converted = conversion.json()
        assert converted["created_opportunity"] is True
        assert converted["market_signal"]["buyer_name"] == "Northshire Retail Group"
        assert converted["opportunity"]["buyer_name"] == "Northshire Retail Group"
        assert converted["opportunity"]["estimated_total_contract_value"] == 1600000
        assert converted["opportunity_enrichment"]["overall_confidence"] > 0
        assert converted["field_intelligence"]
        assert converted["fields_filled"] > 0
        assert converted["fields_still_unknown"] >= 1
        assert converted["executive_action"]["priority"] == "high"
        assert converted["finance_forecast"]["forecast_category"] in {
            "Likely",
            "Best case",
            "Stretch",
        }
    finally:
        app.dependency_overrides.clear()
