import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openai import OpenAIError

from app.config import Settings
from app.intelligence.internet_research import research_internet_with_openai
from app.intelligence.openai_client import InvalidOpenAIJSONError, OpenAIRequestError
from app.main import create_app
from app.schemas import InternetIntelligenceRequest


class FakeResponses:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.content, output=[])


class FakeOpenAIClient:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.responses = FakeResponses(content=content, error=error)


def _internet_request() -> InternetIntelligenceRequest:
    return InternetIntelligenceRequest(
        intelligence_type="competitor_intelligence",
        query="UK fire and security competitor activity in healthcare fire dampers",
        sector="Healthcare",
        region="UK",
        competitor_name="Example Fire Compliance Ltd",
    )


def _internet_payload() -> dict[str, object]:
    return {
        "intelligence_type": "competitor_intelligence",
        "query": "UK fire and security competitor activity in healthcare fire dampers",
        "headline": "Healthcare estates are signalling fire damper compliance pressure.",
        "summary": "Public sources indicate continued compliance-driven demand, but source coverage is incomplete.",
        "findings": [
            {
                "title": "Fire damper compliance pressure",
                "finding": "Healthcare estate notices and supplier pages point to ongoing inspection and remediation demand.",
                "so_what": "Mitie should prioritise healthcare references and compliance evidence.",
                "recommended_action": "Build a source-backed target list for healthcare estates with damper risk.",
                "confidence_score": 0.72,
                "source_urls": ["https://example.invalid/source-a"],
            }
        ],
        "source_urls": ["https://example.invalid/source-a"],
        "risk_warnings": ["Public sources do not prove buyer intent without validation."],
        "next_best_actions": ["Validate target buyers against approved internal account data."],
        "limitations": ["Controlled unit test response; no live web call was made."],
    }


def test_internet_research_uses_responses_api_with_web_search() -> None:
    fake_client = FakeOpenAIClient(content=json.dumps(_internet_payload()))

    result = research_internet_with_openai(
        _internet_request(),
        client=fake_client,
        settings=Settings(openai_api_key=None, openai_model="gpt-5.5"),
    )

    assert result.headline.startswith("Healthcare estates")
    assert result.findings[0].recommended_action.startswith("Build a source-backed")
    assert fake_client.responses.kwargs is not None
    assert fake_client.responses.kwargs["model"] == "gpt-5.5"
    assert fake_client.responses.kwargs["tools"] == [
        {"type": "web_search", "search_context_size": "low"}
    ]
    assert fake_client.responses.kwargs["reasoning"] == {"effort": "low"}
    assert fake_client.responses.kwargs["store"] is False
    assert fake_client.responses.kwargs["timeout"] == 45
    assert fake_client.responses.kwargs["max_output_tokens"] == 4000
    text_format = fake_client.responses.kwargs["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert "competitor_name" in fake_client.responses.kwargs["input"]


def test_internet_research_rejects_invalid_ai_output() -> None:
    fake_client = FakeOpenAIClient(content="not-json")

    with pytest.raises(InvalidOpenAIJSONError, match="internet intelligence"):
        research_internet_with_openai(
            _internet_request(),
            client=fake_client,
            settings=Settings(openai_api_key=None, openai_model="gpt-5.5"),
        )


def test_internet_research_wraps_openai_errors() -> None:
    fake_client = FakeOpenAIClient(error=OpenAIError("boom"))

    with pytest.raises(OpenAIRequestError, match="internet intelligence"):
        research_internet_with_openai(
            _internet_request(),
            client=fake_client,
            settings=Settings(openai_api_key=None, openai_model="gpt-5.5"),
        )


def test_internet_research_endpoint_handles_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.routers.intelligence as intelligence_router

    monkeypatch.setattr(
        intelligence_router,
        "get_settings",
        lambda: Settings(openai_api_key=None, openai_model="gpt-5.5"),
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/intelligence/internet-research",
        json=_internet_request().model_dump(mode="json"),
    )

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
