from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, create_database_engine, get_db
from app.main import create_app
from app.services.seed import seed_sample_data


def test_executive_summary_report_endpoint_returns_report_ready_json(
    tmp_path: Path,
) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'report.db'}")
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

        response = client.get("/api/reports/executive-summary?as_of=2026-06-29")

        assert response.status_code == 200
        report = response.json()
        assert report["report_name"] == "MiSi Executive Summary"
        assert "Managing Director" in report["audience"]
        assert "commercially sensitive" in report["data_note"]
        assert report["dashboard_kpis"]["live_opportunity_count"] == 22
        assert report["dashboard_kpis"]["weighted_pipeline_value"] == 17438400
        assert "Weighted pipeline" in report["leadership_summary"]["summary"]
        assert report["top_opportunities"]
        assert report["finance_forecast"]["financial_year"] == "2026/27"
        assert report["finance_forecast"]["secured_work"]
        assert report["self_delivery_summary"]["opportunity_value"] > 0
        assert report["self_delivery_summary"]["route_opportunities"]
        assert report["executive_actions"]
        assert {
            "Pipeline risk",
            "Finance governance",
            "Self-delivery capture",
        }.issubset({item["category"] for item in report["risks_and_recommendations"]})
    finally:
        app.dependency_overrides.clear()
