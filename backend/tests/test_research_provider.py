import json
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.intelligence import research_provider
from app.intelligence.openai_client import MissingOpenAIKeyError, OpenAIRequestError
from app.intelligence.public_contacts import research_public_contacts
from app.schemas.public_contacts import PublicContactRequest
from app.intelligence.universal_research import _web_provenance


SCHEMA = {"type": "object", "properties": {"observations": {"type": "array", "maxItems": 6, "items": {
    "type": "object", "properties": {"source_url": {"type": "string", "maxLength": 2048}},
    "required": ["source_url"], "additionalProperties": False}}}, "required": ["observations"], "additionalProperties": False}


def arguments(web=False):
    args = {"model": "claude-test", "instructions": "Find source observations.", "input": "{}",
            "text": {"format": {"schema": SCHEMA}}, "timeout": 45, "max_output_tokens": 500}
    if web:
        args["tools"] = [{"type": "web_search"}]
    return args


def response(body, status=200):
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_openai_is_default_and_missing_anthropic_key_is_not_silently_fallback(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(research_provider, "get_openai_client", lambda settings: sentinel)
    assert research_provider.get_research_client(Settings(_env_file=None)) is sentinel
    with pytest.raises(MissingOpenAIKeyError):
        research_provider.get_research_client(Settings(_env_file=None, research_provider="anthropic"))
    with pytest.raises(ValueError):
        Settings(_env_file=None, research_provider="unknown")


def test_anthropic_two_turn_web_research_keeps_real_tool_provenance(monkeypatch):
    sent = []
    def post(url, *, json, headers, timeout, follow_redirects):
        sent.append(json)
        assert headers["x-api-key"] == "test-key"
        assert follow_redirects is False
        if len(sent) == 1:
            return response({"stop_reason": "end_turn", "content": [
                {"type": "server_tool_use", "name": "web_search", "id": "s1", "input": {"query": "example"}},
                {"type": "web_search_tool_result", "tool_use_id": "s1", "content": [{"type": "web_search_result", "url": "https://example.org/source", "title": "Source"}]},
                {"type": "text", "text": "An example source.", "citations": [{"url": "https://example.org/source", "cited_text": "Example"}]},
            ]})
        return response({"stop_reason": "end_turn", "content": [{"type": "text", "text": '{"observations":[{"source_url":"https://example.org/source"}]}'}]})
    monkeypatch.setattr(research_provider.httpx, "post", post)
    result = research_provider.AnthropicResearchClient("test-key").responses.create(**arguments(web=True))
    performed, queries, sources = _web_provenance(result)
    assert performed and queries == ["example"] and "https://example.org/source" in sources
    assert json.loads(result.output_text)["observations"][0]["source_url"] == "https://example.org/source"
    assert "output_config" not in sent[0] and "tools" in sent[0]
    assert "tools" not in sent[1] and "output_config" in sent[1]
    assert "maxItems" not in json.dumps(sent[1]["output_config"])
    assert "maxLength" not in json.dumps(sent[1]["output_config"])


def test_anthropic_does_not_invent_search_provenance(monkeypatch):
    sent = []
    def post(*args, **kwargs):
        sent.append(kwargs["json"])
        return response({"stop_reason": "end_turn", "content": [{"type": "text", "text": "No search happened."}]})
    monkeypatch.setattr(research_provider.httpx, "post", post)
    result = research_provider.AnthropicResearchClient("test-key").create(**arguments(web=True))
    assert not _web_provenance(result)[0]
    assert json.loads(result.output_text) == {"observations": []}
    assert len(sent) == 1


def test_anthropic_rejects_incomplete_tool_turn_and_provider_error(monkeypatch):
    monkeypatch.setattr(research_provider.httpx, "post", lambda *args, **kwargs: response({"stop_reason": "pause_turn", "content": []}))
    with pytest.raises(OpenAIRequestError):
        research_provider.AnthropicResearchClient("test-key").create(**arguments())
    monkeypatch.setattr(research_provider.httpx, "post", lambda *args, **kwargs: response({"error": "bad key"}, 401))
    with pytest.raises(OpenAIRequestError):
        research_provider.AnthropicResearchClient("test-key").create(**arguments())


def test_contact_research_uses_anthropic_and_its_web_tool(monkeypatch):
    calls = []
    def post(*args, **kwargs):
        payload = kwargs["json"]
        calls.append(payload)
        if "tools" in payload:
            return response({"stop_reason": "end_turn", "content": [
                {"type": "server_tool_use", "name": "web_search", "id": "s1", "input": {"query": "Example contact"}},
                {"type": "web_search_tool_result", "tool_use_id": "s1", "content": [{"type": "web_search_result", "url": "https://example.org/contact", "title": "Contact"}]},
                {"type": "text", "text": "Example enquiries: hello@example.org", "citations": [{"url": "https://example.org/contact", "cited_text": "hello@example.org"}]},
            ]})
        contact = {"name": "", "role": "", "kind": "email", "value": "hello@example.org", "source_url": "https://example.org/contact", "source_title": "Contact", "source_date": "", "evidence_quote": "Example enquiries: hello@example.org"}
        return response({"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps({"contacts": [contact]})}]})
    monkeypatch.setattr(research_provider.httpx, "post", post)
    settings = Settings(_env_file=None, research_provider="anthropic", anthropic_api_key="test", anthropic_model="claude-test")
    result = research_public_contacts(PublicContactRequest(organisation="Example"), settings)
    assert result.contacts[0].value == "hello@example.org"
    assert all(call["model"] == "claude-test" for call in calls)


def test_credentials_are_hidden_from_settings_repr():
    settings = Settings(_env_file=None, openai_api_key="secret-one", anthropic_api_key="secret-two")
    assert "secret-one" not in repr(settings) and "secret-two" not in repr(settings)
