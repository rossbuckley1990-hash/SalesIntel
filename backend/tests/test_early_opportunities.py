import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openai import OpenAIError

from app.config import Settings
from app.intelligence.early_opportunities import research_early_opportunities
from app.intelligence.openai_client import InvalidOpenAIJSONError, OpenAIRequestError
from app.main import create_app
from app.schemas.early_opportunity import EarlyOpportunityRequest


class FakeResponses:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.kwargs = payload, error, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(output_text=json.dumps(self.payload), output=[])


def payload():
    return {
        "query": "Find estate expansion signals",
        "summary": "One potential early-stage lead for review.",
        "findings": [{
            "organisation": "Example Ltd",
            "signal": "The company announced a new site.",
            "signal_date": "2026-10-01",
            "signal_source_url": "https://example.com/news/site",
            "inferred_need": "A new site may require fire protection.",
            "fit_and_timing": "Explore requirements before opening.",
            "uncertainties": "Buying intent and current supplier are unknown.",
            "contact_name": "",
            "contact_role": "Estates director (suggested role)",
            "contact_source_url": "",
            "engagement_opener": "Ask about the recently announced site.",
            "discovery_question": "How are fire safety systems being planned?",
            "next_action": "Identify the relevant estates contact.",
        }],
        "limitations": ["The signal does not establish buying intent."],
    }


def call_research(response):
    return research_early_opportunities(
        EarlyOpportunityRequest(query="Find estate expansion signals"),
        client=SimpleNamespace(responses=response),
        settings=Settings(openai_api_key=None, openai_model="gpt-6.1-terra"),
    )


def test_early_research_sends_web_search_and_returns_separate_evidence_and_contact():
    fake = FakeResponses(payload())
    result = call_research(fake)
    assert result.findings[0].signal_source_url == "https://example.com/news/site"
    assert result.findings[0].contact_name == ""
    assert "unknown" in result.findings[0].uncertainties
    assert fake.kwargs["model"] == "gpt-6.1-terra"
    assert fake.kwargs["tools"][0]["type"] == "web_search"
    assert fake.kwargs["store"] is False
    assert fake.kwargs["text"]["format"]["strict"] is True
    assert "Never guess email addresses" in fake.kwargs["instructions"]
    assert "Do not imply the buyer intends to buy" in fake.kwargs["instructions"]
    assert "Prioritise servicing, planned and reactive maintenance" in fake.kwargs["instructions"]
    assert "A new building is a secondary signal" in fake.kwargs["instructions"]
    assert "Do not infer a renewal, supplier change, current contract or buying intent" in fake.kwargs["instructions"]
    assert "discovery question about the current maintenance model" in fake.kwargs["instructions"]


def test_empty_results_are_valid():
    data = payload()
    data["findings"] = []
    assert call_research(FakeResponses(data)).findings == []


@pytest.mark.parametrize("field,value", [("contact_name", "Jane Smith"), ("signal_source_url", "javascript:alert(1)")])
def test_rejects_unsourced_named_contact_and_non_http_links(field, value):
    data = payload()
    data["findings"][0][field] = value
    with pytest.raises(InvalidOpenAIJSONError):
        call_research(FakeResponses(data))


def test_wraps_api_failure():
    with pytest.raises(OpenAIRequestError):
        call_research(FakeResponses(error=OpenAIError("failed")))


def test_endpoint_requires_key_only_when_called(monkeypatch):
    import app.routers.intelligence as router
    monkeypatch.setattr(router, "get_settings", lambda: Settings(openai_api_key=None))
    response = TestClient(create_app()).post(
        "/api/intelligence/early-opportunities", json={"query": "Find estate expansion signals"}
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
