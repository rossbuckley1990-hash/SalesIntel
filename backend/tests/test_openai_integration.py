import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openai import OpenAIError

from app.config import Settings
from app.intelligence.openai_client import MissingOpenAIKeyError, OpenAIRequestError
from app.intelligence.openai_client import get_openai_client
from app.intelligence.openai_client import InvalidOpenAIJSONError
from app.intelligence.structured_analysis import analyse_opportunity_with_openai
from app.main import create_app
from app.schemas import OpportunityAnalysisRequest


class FakeCompletions:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class FakeOpenAIClient:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.completions = FakeCompletions(content=content, error=error)
        self.chat = SimpleNamespace(completions=self.completions)


def _analysis_request() -> OpportunityAnalysisRequest:
    return OpportunityAnalysisRequest(
        name="Multi-site fire alarm maintenance renewal",
        buyer_name="Northshire Retail Group",
        sector="Retail",
        region="North West",
        stage="Negotiation",
        estimated_total_contract_value=1_440_000,
        margin_percentage=21,
        probability=0.72,
        self_delivery_fit="High",
        risk_rating="Medium",
        strategic_fit_score=86,
        context="Synthetic test data only.",
    )


def _analysis_payload() -> dict[str, object]:
    return {
        "opportunity_summary": "High-value retail renewal with strong self-delivery fit.",
        "commercial_assessment": "Attractive strategic position, but margin needs review.",
        "risk_level": "Amber",
        "key_risks": ["Margin below target", "Mobilisation assumptions need validation"],
        "recommended_actions": [
            "Confirm final price walkaway.",
            "Validate mobilisation plan with operations.",
        ],
        "bid_no_bid_recommendation": "Pursue",
        "confidence_score": 0.82,
        "source_notes": ["Based only on supplied opportunity fields."],
    }


def test_openai_client_requires_backend_api_key_when_requested() -> None:
    settings = Settings(openai_api_key=None)

    with pytest.raises(MissingOpenAIKeyError, match="OPENAI_API_KEY"):
        get_openai_client(settings)


def test_structured_analysis_can_use_mocked_openai_response() -> None:
    fake_client = FakeOpenAIClient(content=json.dumps(_analysis_payload()))

    result = analyse_opportunity_with_openai(
        _analysis_request(),
        client=fake_client,
        settings=Settings(openai_api_key=None, openai_model="test-model"),
    )

    assert result.model == "test-model"
    assert result.bid_no_bid_recommendation == "Pursue"
    assert result.confidence_score == 0.82
    assert fake_client.completions.kwargs is not None
    assert fake_client.completions.kwargs["model"] == "test-model"
    response_format = fake_client.completions.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True


def test_structured_analysis_rejects_invalid_json() -> None:
    fake_client = FakeOpenAIClient(content="not json")

    with pytest.raises(InvalidOpenAIJSONError, match="invalid structured JSON"):
        analyse_opportunity_with_openai(
            _analysis_request(),
            client=fake_client,
            settings=Settings(openai_api_key=None, openai_model="test-model"),
        )


def test_structured_analysis_wraps_openai_sdk_errors() -> None:
    fake_client = FakeOpenAIClient(error=OpenAIError("boom"))

    with pytest.raises(OpenAIRequestError, match="request failed"):
        analyse_opportunity_with_openai(
            _analysis_request(),
            client=fake_client,
            settings=Settings(openai_api_key=None, openai_model="test-model"),
        )


def test_analysis_endpoint_reports_missing_key_only_when_called(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.intelligence.structured_analysis as structured_analysis

    monkeypatch.setattr(
        structured_analysis,
        "get_settings",
        lambda: Settings(openai_api_key=None, openai_model="test-model"),
    )
    client = TestClient(create_app())

    assert client.get("/health").status_code == 200

    response = client.post(
        "/api/intelligence/opportunity-analysis",
        json=_analysis_request().model_dump(mode="json"),
    )

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
