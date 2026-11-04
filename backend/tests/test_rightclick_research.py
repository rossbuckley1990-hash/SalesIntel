import json
from types import SimpleNamespace

from app.config import Settings
from app.intelligence import rightclick_research
from app.intelligence.rightclick_x import RightClickError
from app.schemas.universal_research import UniversalResearchRequest
from app.intelligence.universal_research import research_universal


class FakeRightClick:
    def __init__(self, settings):
        pass
    def status(self):
        return {"available": True}
    def search(self, query):
        return {"items": [{"id":"approved", "title":"Planning Data England", "provider":"planning", "source":"https://www.planning.data.gov.uk/openapi.json"}]}
    def planning_query(self, q, dataset, limit):
        assert q == "10008315764" and dataset == "conservation-area" and limit == 5
        return {"entities":[{"entity":44016029, "name":"Regent's Canal", "dataset":"conservation-area", "start-date":"2007-01-01"},
            {"entity":"../../evil", "name":"Fake", "dataset":"conservation-area"},
            {"entity":9, "name":"Other dataset", "dataset":"other"}], "receipt":{"hash":"a" * 64}}


class FakeModel:
    def __init__(self): self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        task = kwargs["text"]["format"]["name"]
        if task == "misi_research_plan":
            return SimpleNamespace(output_text=json.dumps({"queries":["Example Trust estates planning signals"]}),output=[])
        if task == "misi_research_search":
            entries = [{"source_url":"https://a.example/one", "source_title":"Example Trust report", "published_date":"2026", "fact":"Example Trust reports estate changes."},
                       {"source_url":"https://b.example/two", "source_title":"Example Trust update", "published_date":"2026", "fact":"Example Trust describes work at its estate."}]
            action = {"type":"search", "queries":["Example Trust"], "sources":[{"url":x["source_url"]} for x in entries]}
            return SimpleNamespace(output_text=json.dumps({"observations":entries}),output=[{"type":"web_search_call", "action":action}])
        return SimpleNamespace(output_text=json.dumps({"opportunities":[],"limitations":[]}),output=[])


def test_opt_in_planning_lookup_is_attributed_and_used_as_unverified_model_context(monkeypatch):
    monkeypatch.setattr(rightclick_research, "RightClickClient", FakeRightClick)
    model = FakeModel()
    request = UniversalResearchRequest(brief="Investigate Example Trust fire maintenance", max_searches=1,
        include_rightclick=True, rightclick_identifier="10008315764", rightclick_dataset="conservation-area")
    result = research_universal(request, client=SimpleNamespace(responses=model), settings=Settings(_env_file=None))
    assert result.source_discovery["status"] == "searched"
    records = result.source_discovery["query"]["records"]
    assert len(records) == 1 and records[0]["source_url"] == "https://www.planning.data.gov.uk/entity/44016029"
    assert result.source_discovery["query"]["receipt"] == "a" * 64
    assert result.observations[-1].origin == "public_api"
    plan = json.loads(model.calls[0]["input"])
    assert plan["available_public_source_capabilities"][0]["title"] == "Planning Data England"
    synthesis = json.loads(next(c for c in model.calls if c["text"]["format"]["name"] == "misi_research_synthesis")["input"])
    assert synthesis["observations"][-1]["origin"] == "public_api"
    assert "not proof" in synthesis["observations"][-1]["fact"]


def test_rightclick_is_not_called_without_opt_in(monkeypatch):
    def forbidden(*args): raise AssertionError("RightClick must be explicitly requested")
    monkeypatch.setattr(rightclick_research, "RightClickClient", forbidden)
    model = FakeModel()
    result = research_universal(UniversalResearchRequest(brief="Investigate Example Trust fire maintenance", max_searches=1),
        client=SimpleNamespace(responses=model), settings=Settings(_env_file=None))
    assert result.source_discovery is None


def test_planning_context_does_not_count_as_corroboration_for_an_account(monkeypatch):
    class NamedRecord(FakeRightClick):
        def planning_query(self, q, dataset, limit):
            data = super().planning_query(q, dataset, limit)
            data["entities"][0]["name"] = "Example Trust Estate"
            return data
    monkeypatch.setattr(rightclick_research, "RightClickClient", NamedRecord)
    model = FakeModel()
    original = model.create
    def output(**kwargs):
        response = original(**kwargs)
        if kwargs["text"]["format"]["name"] == "misi_research_synthesis":
            response.output_text = json.dumps({"opportunities":[{"organisation":"Example Trust", "location":"York",
                "headline":"Check maintenance", "thesis":"Investigate the estate", "supporting_observation_ids":["O1","RC1"],
                "counter_observation_ids":[], "unknowns":[], "contact_name":"", "contact_role":"Estates lead",
                "contact_observation_ids":[], "engagement":"Ask", "verification_action":"Check"}], "limitations":[]})
        return response
    model.create = output
    request = UniversalResearchRequest(brief="Investigate Example Trust fire maintenance", max_searches=1,
        include_rightclick=True, rightclick_identifier="10008315764", rightclick_dataset="conservation-area")
    result = research_universal(request, client=SimpleNamespace(responses=model), settings=Settings(_env_file=None))
    assert result.opportunities == []
    assert any("omitted" in item for item in result.limitations)


def test_runtime_failure_is_visible_and_does_not_stop_research(monkeypatch):
    def unavailable(settings): raise RightClickError("do not expose raw network errors")
    monkeypatch.setattr(rightclick_research, "RightClickClient", unavailable)
    model = FakeModel()
    result = research_universal(UniversalResearchRequest(brief="Investigate Example Trust fire maintenance", max_searches=1, include_rightclick=True),
        client=SimpleNamespace(responses=model), settings=Settings(_env_file=None))
    assert result.source_discovery["status"] == "unavailable"
    assert len(result.searches) == 1 and "raw network errors" not in result.source_discovery["message"]


def test_generic_directory_discovery_uses_only_bounded_topics(monkeypatch):
    calls = []
    class Directory:
        def __init__(self, settings): pass
        def status(self): return {"available": True}
        def candidates(self, topic):
            calls.append(topic)
            return {"topic": topic, "candidates": [{"title": "Public estates register", "description": "Unreviewed suggestion", "directory": "public", "kind": "dataset"}], "directories": ["public"]}
    monkeypatch.setattr(rightclick_research, "RightClickClient", Directory)
    class TopicModel(FakeModel):
        def create(self, **kwargs):
            response = super().create(**kwargs)
            if kwargs["text"]["format"]["name"] == "misi_research_plan":
                response.output_text = json.dumps({"queries": ["Scottish hospital maintenance signals"], "source_topics": ["fire safety", "healthcare facilities"]})
            return response
    model = TopicModel()
    request = UniversalResearchRequest(brief="Investigate Secret Hospital in Scotland for fire maintenance", max_searches=1)
    result = research_universal(request, client=SimpleNamespace(responses=model), settings=Settings(_env_file=None, rightclick_x_url="http://127.0.0.1:8787/mcp"))
    assert sorted(calls) == ["fire safety", "healthcare facilities"]
    assert result.source_discovery["topics"] == ["fire safety", "healthcare facilities"]
    assert len(result.source_discovery["candidates"]) == 1
    search = json.loads(next(c for c in model.calls if c["text"]["format"]["name"] == "misi_research_search")["input"])
    assert search["unreviewed_directory_suggestions"][0]["title"] == "Public estates register"
    assert all(item.origin != "public_api" for item in result.observations)


def test_directory_discovery_failures_do_not_stop_web_research(monkeypatch):
    class FailingDirectory:
        def __init__(self, settings): pass
        def status(self): return {"available": True}
        def candidates(self, topic): raise RightClickError("network details")
    monkeypatch.setattr(rightclick_research, "RightClickClient", FailingDirectory)
    model = FakeModel()
    result = research_universal(UniversalResearchRequest(brief="Investigate fire maintenance", max_searches=1), client=SimpleNamespace(responses=model), settings=Settings(_env_file=None, rightclick_x_url="http://127.0.0.1:8787/mcp"))
    assert result.source_discovery["status"] == "unavailable"
    assert set(result.source_discovery["failed_topics"]) == {"fire safety", "facilities maintenance"}
    assert len(result.searches) == 1
    assert "network details" not in str(result.source_discovery)


def test_estate_lookup_is_opt_in_and_never_matches_guessed_postcodes(monkeypatch):
    from app.intelligence import public_estate_research
    calls = []
    def lookup(postcode, limit):
        calls.append((postcode, limit))
        return {"records": [{"id": 123, "name": "Example Trust", "business_type": "Hospital", "postcode": "SW1A 1AA", "address": "Somewhere", "source_url": "https://evil.invalid"}], "retrieved_at": "2026-10-28T10:00:00Z", "limitations": ["May be stale"], "source": {"title": "FSA", "url": "https://api.ratings.food.gov.uk/help"}, "scanned": 1}
    monkeypatch.setattr(public_estate_research, "search_establishments", lookup)
    settings = Settings(_env_file=None)
    model = FakeModel()
    result = research_universal(UniversalResearchRequest(brief="Look around SW1A 1AA", max_searches=1), client=SimpleNamespace(responses=model), settings=settings)
    assert calls == [] and result.estate_lookup is None
    missing = research_universal(UniversalResearchRequest(brief="Look around SW1A 1AA", max_searches=1, include_estate_lookup=True), client=SimpleNamespace(responses=FakeModel()), settings=settings)
    assert calls == [] and missing.estate_lookup["status"] == "missing_postcode"
    result = research_universal(UniversalResearchRequest(brief="Investigate Example Trust", max_searches=1, include_estate_lookup=True, estate_postcode="sw1a 1aa"), client=SimpleNamespace(responses=FakeModel()), settings=settings)
    assert calls == [("SW1A 1AA", 5)]
    assert result.estate_lookup["records"][0]["source_url"] == "https://ratings.food.gov.uk/business/123"
    assert result.observations[-1].origin == "public_api"
    assert "not evidence" in result.observations[-1].fact


def test_estate_context_cannot_corroborate_organisation(monkeypatch):
    from app.intelligence import public_estate_research
    monkeypatch.setattr(public_estate_research, "search_establishments", lambda postcode, limit: {"records": [{"id": 1, "name": "Example Trust", "business_type": "Hospital", "postcode": postcode}], "retrieved_at": "2026-10-28T10:00:00Z"})
    model = FakeModel()
    original = model.create
    def output(**kwargs):
        response = original(**kwargs)
        if kwargs["text"]["format"]["name"] == "misi_research_synthesis":
            response.output_text = json.dumps({"opportunities": [{"organisation": "Example Trust", "location": "London", "headline": "Check maintenance", "thesis": "Investigate", "supporting_observation_ids": ["O1", "FS1"], "counter_observation_ids": [], "unknowns": [], "contact_name": "", "contact_role": "Estates lead", "contact_observation_ids": [], "engagement": "Ask", "verification_action": "Check"}], "limitations": []})
        return response
    model.create = output
    result = research_universal(UniversalResearchRequest(brief="Investigate Example Trust", max_searches=1, include_estate_lookup=True, estate_postcode="SW1A 1AA"), client=SimpleNamespace(responses=model), settings=Settings(_env_file=None))
    assert result.opportunities == []
