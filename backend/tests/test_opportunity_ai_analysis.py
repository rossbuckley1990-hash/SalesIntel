from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import Base, create_database_engine, get_db
from app.main import create_app
from app.models import OpportunityAIAnalysis
from app.services.seed import seed_sample_data


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class FakeOpenAIClient:
    def __init__(self, content: str) -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def _analysis_payload() -> dict[str, object]:
    return {
        "strategic_fit_score": 88,
        "win_probability": 0.68,
        "risk_rating": "Amber",
        "bid_no_bid_recommendation": "Pursue with executive sponsor",
        "likely_buyer_drivers": [
            "Compliance assurance",
            "Store uptime",
            "Predictable mobilisation",
        ],
        "competitor_threat": "Medium",
        "margin_commentary": "Margin is below target, so leadership should confirm the walkaway position.",
        "mobilisation_risks": [
            "Unknown incumbent demobilisation plan",
            "Mobilisation resource assumptions need validation",
        ],
        "commercial_risks": [
            "Margin dilution if remedial assumptions are wrong",
            "Buyer service-level expectations are not fully evidenced",
        ],
        "self_delivery_assessment": "Strong fit for Mitie self-delivery if mobilisation resource is confirmed.",
        "recommended_action": "Assign an executive sponsor and run a final margin review before bid commitment.",
        "executive_summary": "Strategic retail renewal with strong fit, but margin and mobilisation need senior control.",
    }


def _client_with_seeded_database(tmp_path: Path) -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'analysis.db'}")
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
    return TestClient(app), testing_session


def test_analyse_opportunity_endpoint_stores_valid_ai_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.intelligence.opportunity_analysis as opportunity_analysis

    fake_client = FakeOpenAIClient(json.dumps(_analysis_payload()))
    monkeypatch.setattr(
        opportunity_analysis,
        "get_openai_client",
        lambda settings: fake_client,
    )
    client, testing_session = _client_with_seeded_database(tmp_path)

    response = client.post("/api/intelligence/analyse-opportunity/1")

    assert response.status_code == 200
    body = response.json()
    assert body["strategic_fit_score"] == 88
    assert body["win_probability"] == 0.68
    assert body["risk_rating"] == "Amber"
    assert body["bid_no_bid_recommendation"] == "Pursue with executive sponsor"
    assert body["competitor_threat"] == "Medium"
    assert body["recommended_action"].startswith("Assign an executive sponsor")

    assert fake_client.completions.kwargs is not None
    response_format = fake_client.completions.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    messages = fake_client.completions.kwargs["messages"]
    assert "commercially sensitive" in messages[0]["content"]
    assert "Northshire Retail Group" in messages[1]["content"]

    with testing_session() as db:
        stored = db.scalar(select(OpportunityAIAnalysis))
        assert stored is not None
        assert stored.opportunity_id == 1
        assert stored.strategic_fit_score == 88
        assert stored.likely_buyer_drivers == body["likely_buyer_drivers"]
        assert stored.executive_summary == body["executive_summary"]

    opportunity_response = client.get("/api/opportunities/1")
    assert opportunity_response.status_code == 200
    latest_analysis = opportunity_response.json()["latest_ai_analysis"]
    assert latest_analysis["strategic_fit_score"] == 88
    assert latest_analysis["risk_rating"] == "Amber"
    assert latest_analysis["executive_summary"] == body["executive_summary"]


def test_analyse_opportunity_endpoint_rejects_invalid_ai_output_without_storing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.intelligence.opportunity_analysis as opportunity_analysis

    invalid_payload = {
        **_analysis_payload(),
        "risk_rating": "Medium",
    }
    fake_client = FakeOpenAIClient(json.dumps(invalid_payload))
    monkeypatch.setattr(
        opportunity_analysis,
        "get_openai_client",
        lambda settings: fake_client,
    )
    client, testing_session = _client_with_seeded_database(tmp_path)

    response = client.post("/api/intelligence/analyse-opportunity/1")

    assert response.status_code == 502
    assert "invalid structured JSON" in response.json()["detail"]

    with testing_session() as db:
        assert db.scalar(select(func.count(OpportunityAIAnalysis.id))) == 0


def test_analyse_opportunity_endpoint_handles_missing_openai_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.routers.intelligence as intelligence_router

    monkeypatch.setattr(
        intelligence_router,
        "get_settings",
        lambda: Settings(openai_api_key=None, openai_model="test-model"),
    )
    client, _testing_session = _client_with_seeded_database(tmp_path)

    response = client.post("/api/intelligence/analyse-opportunity/1")

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_analyse_opportunity_endpoint_returns_404_before_openai_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.intelligence.opportunity_analysis as opportunity_analysis

    def fail_if_called(settings: Settings) -> FakeOpenAIClient:
        raise AssertionError("OpenAI client should not be requested for missing records")

    monkeypatch.setattr(opportunity_analysis, "get_openai_client", fail_if_called)
    client, _testing_session = _client_with_seeded_database(tmp_path)

    response = client.post("/api/intelligence/analyse-opportunity/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Opportunity not found"
