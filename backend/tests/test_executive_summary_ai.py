from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import Base, create_database_engine, get_db
from app.main import create_app
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


def _executive_summary_payload() -> dict[str, object]:
    return {
        "headline": "Pipeline is strong but margin and Red-risk pursuits need leadership control.",
        "summary": (
            "SalesIntel shows a sizeable weighted pipeline with strategic must-wins, "
            "clear finance review items and self-delivery upside that should be governed this week."
        ),
        "md_attention": [
            "Sponsor the highest-value Red-risk pursuit before final commitment.",
        ],
        "finance_attention": [
            "Review margin warnings and confirm the risk-adjusted forecast position.",
        ],
        "sales_attention": [
            "Protect strategic must-wins and confirm next actions with opportunity owners.",
        ],
        "bid_team_attention": [
            "Prioritise live tenders with deadline or margin pressure.",
        ],
        "risk_warnings": [
            "Red-risk opportunities require clear executive ownership.",
        ],
        "next_best_actions": [
            "Run a weekly leadership review on Red risks, margin recovery and self-delivery capture.",
        ],
    }


def _client_with_seeded_database(tmp_path: Path) -> TestClient:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'executive-summary.db'}")
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
    return TestClient(app)


def test_generate_executive_summary_uses_dashboard_data_and_returns_structured_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.intelligence.executive_summary as executive_summary

    fake_client = FakeOpenAIClient(json.dumps(_executive_summary_payload()))
    monkeypatch.setattr(
        executive_summary,
        "get_openai_client",
        lambda settings: fake_client,
    )
    client = _client_with_seeded_database(tmp_path)

    response = client.post("/api/intelligence/generate-executive-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["headline"].startswith("Pipeline is strong")
    assert body["md_attention"]
    assert body["finance_attention"]
    assert body["sales_attention"]
    assert body["bid_team_attention"]
    assert body["risk_warnings"]
    assert body["next_best_actions"]

    assert fake_client.completions.kwargs is not None
    response_format = fake_client.completions.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True

    messages = fake_client.completions.kwargs["messages"]
    assert "commercially sensitive" in messages[0]["content"]
    context = json.loads(messages[1]["content"])
    assert context["dashboard"]["weighted_pipeline_value"] == 17438400
    assert context["dashboard"]["strategic_must_win_count"] == 5
    assert context["finance"]["finance_review_item_count"] > 0
    assert context["self_delivery"]["capture_opportunity_count"] > 0
    assert "recommended leadership actions this week" in (
        context["instruction_coverage_required"]
    )


def test_generate_executive_summary_rejects_invalid_ai_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.intelligence.executive_summary as executive_summary

    invalid_payload = {
        **_executive_summary_payload(),
        "finance_attention": "not a list",
    }
    fake_client = FakeOpenAIClient(json.dumps(invalid_payload))
    monkeypatch.setattr(
        executive_summary,
        "get_openai_client",
        lambda settings: fake_client,
    )
    client = _client_with_seeded_database(tmp_path)

    response = client.post("/api/intelligence/generate-executive-summary")

    assert response.status_code == 502
    assert "invalid structured JSON" in response.json()["detail"]


def test_generate_executive_summary_handles_missing_openai_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.routers.intelligence as intelligence_router

    monkeypatch.setattr(
        intelligence_router,
        "get_settings",
        lambda: Settings(openai_api_key=None, openai_model="test-model"),
    )
    client = _client_with_seeded_database(tmp_path)

    response = client.post("/api/intelligence/generate-executive-summary")

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
