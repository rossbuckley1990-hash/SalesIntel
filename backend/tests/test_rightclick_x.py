import json
from functools import partial

import httpx
import pytest

from app.config import Settings
from app.intelligence import rightclick_x as rcx


def settings(url="http://127.0.0.1:8787/mcp", token=None):
    return Settings(_env_file=None, rightclick_x_url=url, rightclick_x_token=token)


def contract(**updates):
    capability = {"id": rcx.CAPABILITY, "provider": rcx.PROVIDER, "risk": "read",
        "invoke": {"kind": "http", "method": "GET", "url": rcx.OFFICIAL_OPERATION}, "inputs": []}
    execution = {"origins": [rcx.OFFICIAL_ORIGIN], "allowed": True, "declaredRisk": "read", "consequentialRisks": ["read"]}
    capability.update(updates)
    return {"capability": capability, "execution": execution}


@pytest.mark.parametrize("url", [None, "http://localhost:8787/mcp", "http://example.org:8787/mcp",
    "http://192.168.1.1:8787/mcp", "http://user:pass@127.0.0.1:8787/mcp",
    "http://127.0.0.1:8787/mcp?token=secret", "http://127.0.0.1:8787/api/run"])
def test_endpoint_is_a_fixed_loopback_mcp_endpoint(url):
    with pytest.raises(rcx.RightClickError):
        rcx.RightClickClient(settings(url))


def test_transport_calls_mcp_without_redirects_and_hides_token(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.headers["authorization"] == "Bearer example-private-token"
        assert json.loads(request.content)["params"]["name"] == "context_runtime"
        return httpx.Response(200, json={"jsonrpc":"2.0", "id":1, "result":{"isError":False,
            "structuredContent":{"product":"RightClick X", "version":"0.1.0", "graph":{"capabilities":4}}}})
    actual_client = httpx.Client
    monkeypatch.setattr(rcx.httpx, "Client", partial(actual_client, transport=httpx.MockTransport(handler)))
    config = settings(token="example-private-token")
    assert "example-private-token" not in repr(config)
    result = rcx.RightClickClient(config).status()
    assert result["available"] is True and result["capabilities"] == 4
    assert len(seen) == 1


def test_search_filters_to_reviewed_capability_and_never_sends_user_query(monkeypatch):
    client = rcx.RightClickClient(settings())
    seen = []
    def call(name, args):
        seen.append((name, args))
        return {"result": [{"id": rcx.CAPABILITY, "provider": rcx.PROVIDER},
            {"id": "platform:node:delete", "provider": "platform:node"}]}
    monkeypatch.setattr(client, "_call", call)
    result = client.search("private account question")
    assert len(result["items"]) == 1 and result["items"][0]["id"] == rcx.CAPABILITY
    assert seen == [("context_graph", {"op":"search", "query":"planning", "limit":30})]


@pytest.mark.parametrize("change", [{"risk":"write"}, {"provider":"other"},
    {"invoke":{"kind":"http", "method":"POST", "url":rcx.OFFICIAL_OPERATION}},
    {"invoke":{"kind":"http", "method":"GET", "url":"https://other.example/entity.{extension}"}}])
def test_execution_refuses_changed_contract(monkeypatch, change):
    client = rcx.RightClickClient(settings())
    calls = []
    def call(name, args):
        calls.append(name)
        return contract(**change)
    monkeypatch.setattr(client, "_call", call)
    with pytest.raises(rcx.RightClickError):
        client.planning_query("SW1A 1AA", "brownfield-land")
    assert calls == ["context_explain"]


def test_execution_binds_only_safe_arguments_and_preserves_receipt(monkeypatch):
    client = rcx.RightClickClient(settings())
    calls = []
    def call(name, args):
        calls.append((name,args))
        if name == "context_explain": return contract()
        return {"status":"completed", "responseStatus":200, "capability":rcx.CAPABILITY,
                "provider":rcx.PROVIDER, "output":{"entities":[{"entity":1}], "links":{}}, "receipt":{"hash":"abc"}}
    monkeypatch.setattr(client, "_call", call)
    result = client.planning_query("SW1A 1AA", "brownfield-land", 2)
    assert result["entities"] == [{"entity":1}]
    assert result["receipt"] == {"hash":"abc"} and result["verification"] == "unverified"
    assert calls[-1][1]["args"] == {"extension":"json", "q":"SW1A 1AA", "dataset":"brownfield-land", "limit":"2", "offset":"0", "exclude_field":"geometry"}
    for q in ["unknown trust", "https://localhost", "SW1A 1AA&limit=500", ""]:
        with pytest.raises(rcx.RightClickError): client.planning_query(q, "brownfield-land")
    with pytest.raises(rcx.RightClickError): client.planning_query("SW1A 1AA", "unapproved")
    with pytest.raises(rcx.RightClickError): client.planning_query("SW1A 1AA", "brownfield-land", 11)


def test_untrusted_runtime_error_is_not_exposed_to_client(monkeypatch):
    actual_client = httpx.Client
    def handler(request):
        return httpx.Response(500, text="private server data")
    monkeypatch.setattr(rcx.httpx, "Client", partial(actual_client, transport=httpx.MockTransport(handler)))
    with pytest.raises(rcx.RightClickError) as error:
        rcx.RightClickClient(settings()).status()
    assert "private server data" not in str(error.value)


def test_status_offline_and_planning_endpoint_validates_requests(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import rightclick_x
    app = FastAPI()
    app.include_router(rightclick_x.router)
    monkeypatch.setattr(rightclick_x, "get_settings", lambda: settings(None))
    with TestClient(app) as client:
        status = client.get("/api/rightclick/status")
        assert status.json()["configured"] is False and status.json()["available"] is False
        response = client.post("/api/rightclick/planning-query", json={"identifier":"SW1A 1AA", "dataset":"unknown", "limit":5})
        assert response.status_code == 422
        response = client.post("/api/rightclick/planning-query", json={"identifier":"SW1A 1AA", "dataset":"brownfield-land", "limit":11})
        assert response.status_code == 422
        response = client.post("/api/rightclick/planning-query", json={"identifier":"https://localhost", "dataset":"brownfield-land", "limit":5})
        assert response.status_code == 422
        response = client.post("/api/rightclick/planning-query", json={"identifier":"SW1A 1AA", "dataset":"brownfield-land", "limit":5, "tool":"context_forget"})
        assert response.status_code == 422
        assert client.get("/api/rightclick/candidates", params={"topic": "planning; run secret"}).status_code == 422


def test_directory_candidates_are_bounded_unreviewed_and_never_learned(monkeypatch):
    client = rcx.RightClickClient(settings())
    calls = []
    def call(name, args):
        calls.append((name, args))
        if name == "context_runtime":
            return {"product": "RightClick X", "name": rcx.DEDICATED_RUNTIME_NAME}
        return {"directories": [{"id":"apis.guru", "reachable":True, "candidates":[
            {"directory":"apis.guru", "title":"Fire\x00 data", "description":"Public safety feed\nwith controls", "kind":"openapi", "source":"http://127.0.0.1/private"},
            {"directory":"apis.guru", "title":"Fire " + "X" * 1000, "description":"Safety " + "Z" * 1000, "kind":"openapi"}]},
            {"id":"mcp-registry", "reachable":False, "error":"secret", "candidates": []},
            {"id":"untrusted", "reachable":True, "candidates":[{"title":"Ignored"}]}],
            "environment":{"credentialedOrigins":["secret"]}}
    monkeypatch.setattr(client, "_call", call)
    result = client.candidates("fire safety")
    assert calls == [("context_runtime", {}), ("context_research", {"topic":"fire safety", "limit":5, "learn":0})]
    assert result["candidates"][0] == {"title":"Fire data", "description":"Public safety feed with controls", "directory":"apis.guru", "kind":"openapi"}
    assert len(result["candidates"][1]["title"]) == 160
    assert "source" not in result["candidates"][0] and "secret" not in str(result)
    assert "Unreviewed" in result["message"]
    assert "not a comprehensive search" in result["message"]
    with pytest.raises(rcx.RightClickError):
        client.candidates("planning; learn arbitrary")


def test_directory_discovery_refuses_other_runtime_and_unsafe_arguments(monkeypatch):
    client = rcx.RightClickClient(settings())
    calls = []
    def call(name, args):
        calls.append(name)
        return {"product":"RightClick X", "name":"other-instance"}
    monkeypatch.setattr(client, "_call", call)
    with pytest.raises(rcx.RightClickError):
        client.candidates("planning")
    assert calls == ["context_runtime"]
    with pytest.raises(rcx.RightClickError):
        rcx.RightClickClient(settings())._call("context_research", {"topic":"planning", "limit":5, "learn":1})


@pytest.mark.parametrize("topic,title,description,expected", [
    ("fire safety", "CallFire", "Cloud telephony marketing", False),
    ("fire safety", "Fire Financial", "Payment services", False),
    ("fire safety", "FireCMS", "Content management system", False),
    ("fire safety", "Fire alarm inspections", "Public data", True),
    ("fire safety", "Fire and rescue service", "Incident records", True),
    ("building", "Build API", "Software compilation", False),
    ("building", "Building permit register", "Construction permits", True),
    ("procurement", "Smart contract library", "Blockchain code", False),
    ("procurement", "Public Contracts Finder", "Government contracts", True),
    ("planning", "Meal planning", "Food menus", False),
    ("planning", "Planning Data", "Land and property development", True),
])
def test_candidate_relevance_screen_is_conservative(topic, title, description, expected):
    assert rcx._topically_relevant(topic, title, description) is expected


def test_brief_only_yields_static_broad_topics_without_private_detail():
    brief = "Find fire and security maintenance at hospitals for Acme Confidential, SW1A 1AA; alice@example.com"
    topics = rcx.topics_from_brief(brief)
    assert topics == ["fire safety", "security systems", "healthcare facilities"]
    assert all(topic in rcx.DISCOVERY_TOPICS for topic in topics)
    assert not any(private in str(topics).lower() for private in ("acme", "sw1a", "alice"))
    assert rcx.topics_from_brief("A confidential novel topic") == []


def test_directory_supports_broader_topics_but_never_forwards_arbitrary_briefs(monkeypatch):
    client = rcx.RightClickClient(settings())
    calls = []
    def call(name, args):
        calls.append((name, args))
        if name == "context_runtime":
            return {"product": "RightClick X", "name": rcx.DEDICATED_RUNTIME_NAME}
        return {"directories": [{"id": "apis.guru", "reachable": True, "candidates": [
            {"directory": "apis.guru", "title": "Hospital data", "description": "Estates", "kind": "openapi"},
            {"directory": "apis.guru", "title": "Travel data", "description": "Directions", "kind": "openapi"},
        ]}]}
    monkeypatch.setattr(client, "_call", call)
    result = client.candidates("healthcare facilities")
    assert len(result["candidates"]) == 1
    assert calls[-1] == ("context_research", {"topic": "healthcare facilities", "limit": 5, "learn": 0})
    with pytest.raises(rcx.RightClickError):
        client.candidates("healthcare facilities for Acme")
    assert len(calls) == 2
