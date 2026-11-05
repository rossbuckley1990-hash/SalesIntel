import json
from types import SimpleNamespace

import pytest
from openai import OpenAIError

from app.config import Settings
from app.intelligence.openai_client import OpenAIRequestError
from app.intelligence.universal_research import research_universal
from app.schemas.universal_research import UniversalResearchRequest


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        body = json.loads(kwargs["input"])
        name = kwargs["text"]["format"]["name"]
        if name == "misi_research_plan":
            result = {"queries":["Scotland estates safety observations", "Wales estate maintenance observations"]}
            return SimpleNamespace(output_text=json.dumps(result), output=[])
        if name == "misi_research_search":
            if body["planned_query"].startswith("Wales"):
                raise OpenAIError("source unavailable")
            result = {"observations":[
                {"source_url":"https://example.org/fact?utm_source=tool", "source_title":"Report", "published_date":"2026", "fact":"Example's site has changed."},
                {"source_url":"https://another.example.org/report", "source_title":"Other report", "published_date":"2026", "fact":"Example describes maintenance."},
                {"source_url":"https://fabricated.example.org/", "source_title":"Bad", "published_date":"", "fact":"Unsupported claim."},
            ]}
            action = SimpleNamespace(type="search", queries=["actual web query"], query=None, sources=[SimpleNamespace(url="https://example.org/fact"), SimpleNamespace(url="https://another.example.org/report")])
            return SimpleNamespace(output_text=json.dumps(result), output=[SimpleNamespace(type="web_search_call", action=action)])
        result = {"opportunities":[{"organisation":"Example", "location":"Scotland", "headline":"Check the service model", "thesis":"A change could affect maintenance scope.",
                 "supporting_observation_ids":["O1", "O2"], "counter_observation_ids":[], "unknowns":["Current provider"], "contact_name":"", "contact_role":"Estates lead",
                 "contact_observation_ids":[], "engagement":"Ask how changes affect maintenance.", "verification_action":"Check the source."}], "limitations":[]}
        return SimpleNamespace(output_text=json.dumps(result), output=[])


def test_research_preserves_brief_tracks_partial_failure_and_filters_invented_urls():
    responses = FakeResponses()
    brief = "Investigate fire maintenance in Scotland and Wales"
    progress = []
    result = research_universal(UniversalResearchRequest(brief=brief,max_searches=3),
        client=SimpleNamespace(responses=responses), settings=Settings(research_provider="openai", openai_api_key=None, openai_model="test-model"), progress_callback=progress.append)
    assert result.brief == brief and result.model == "test-model"
    assert [s.status for s in result.searches] == ["completed", "failed"]
    assert [s.stage for s in result.searches] == ["initial", "planned_fallback"]
    assert result.searches[0].web_queries == ["actual web query"]
    assert result.searches[0].web_sources == ["https://example.org/fact", "https://another.example.org/report"]
    assert len(result.observations) == 2 and result.observations[0].source_url == "https://example.org/fact"
    assert result.opportunities[0].supporting_observation_ids == ["O1", "O2"]
    assert any("partial" in limit for limit in result.limitations)
    assert all(json.loads(call["input"])["brief"] == brief for call in responses.calls)
    assert progress[-1] == {"phase":"completed", "planned":2, "completed":1, "failed":1}
    web = [call for call in responses.calls if call["text"]["format"]["name"] == "misi_research_search"][0]
    assert web["include"] == ["web_search_call.action.sources"] and web["store"] is False


def test_inbox_is_not_loaded_or_transmitted_without_explicit_opt_in(monkeypatch):
    import app.intelligence.universal_research as module
    def forbidden(*args, **kwargs):
        raise AssertionError("Inbox must not be accessed without opt-in")
    monkeypatch.setattr(module, "_matching_imports", forbidden)
    responses = FakeResponses()
    result = research_universal(UniversalResearchRequest(brief="Investigate public fire maintenance", max_searches=3),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert result.include_inbox is False
    assert all(item.origin == "web_search" for item in result.observations)


def test_model_cannot_create_uncited_opportunities():
    responses = FakeResponses()
    original = responses.create
    def fake(**kwargs):
        response = original(**kwargs)
        if kwargs["text"]["format"]["name"] == "misi_research_synthesis":
            payload = json.loads(response.output_text)
            payload["opportunities"][0]["supporting_observation_ids"] = ["O999"]
            response.output_text = json.dumps(payload)
        return response
    responses.create = fake
    result = research_universal(UniversalResearchRequest(brief="Find opportunities in Wales and Scotland"),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert not result.opportunities and len(result.observations) == 2
    assert any("omitted" in limit for limit in result.limitations)


def test_one_observation_can_support_and_qualify_a_hypothesis():
    responses = FakeResponses()
    original = responses.create
    def fake(**kwargs):
        response = original(**kwargs)
        if kwargs["text"]["format"]["name"] == "misi_research_synthesis":
            payload = json.loads(response.output_text)
            payload["opportunities"][0]["counter_observation_ids"] = ["O1"]
            response.output_text = json.dumps(payload)
        return response
    responses.create = fake
    result = research_universal(UniversalResearchRequest(brief="Find fire maintenance opportunities"),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert result.opportunities[0].supporting_observation_ids == ["O1", "O2"]
    assert result.opportunities[0].counter_observation_ids == ["O1"]


def test_invalid_model_output_preserves_actual_search_metadata():
    responses = FakeResponses()
    original = responses.create
    def fake(**kwargs):
        response = original(**kwargs)
        if kwargs["text"]["format"]["name"] == "misi_research_search":
            response.output_text = "not valid JSON"
        return response
    responses.create = fake
    result = research_universal(UniversalResearchRequest(brief="Find fire maintenance opportunities"),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert result.searches[0].status == "failed"
    assert result.searches[0].web_queries == ["actual web query"]
    assert result.searches[0].web_sources == ["https://example.org/fact", "https://another.example.org/report"]
    assert not result.observations


@pytest.mark.parametrize("failed_step", ["misi_research_followup_plan", "misi_research_synthesis"])
def test_provider_adapter_errors_preserve_completed_public_research(failed_step):
    responses = FakeResponses()
    original = responses.create

    def failing_step(**kwargs):
        if kwargs["text"]["format"]["name"] == failed_step:
            raise OpenAIRequestError("Provider unavailable")
        return original(**kwargs)

    responses.create = failing_step
    result = research_universal(UniversalResearchRequest(brief="Investigate public fire maintenance", max_searches=3),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_model="test-model"))
    assert len(result.observations) == 2
    assert len(result.searches) == 2
    if failed_step == "misi_research_followup_plan":
        assert result.searches[1].stage == "planned_fallback"
        assert any("follow-up planning failed" in item for item in result.limitations)
    else:
        assert result.opportunities == []
        assert any("Synthesis did not complete" in item for item in result.limitations)


def test_named_contact_must_appear_in_cited_evidence():
    responses = FakeResponses()
    original = responses.create
    def fake(**kwargs):
        response = original(**kwargs)
        if kwargs["text"]["format"]["name"] == "misi_research_synthesis":
            payload = json.loads(response.output_text)
            payload["opportunities"][0]["contact_name"] = "Invented Person"
            payload["opportunities"][0]["contact_observation_ids"] = ["O1"]
            response.output_text = json.dumps(payload)
        return response
    responses.create = fake
    result = research_universal(UniversalResearchRequest(brief="Find fire maintenance opportunities"),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert result.opportunities[0].contact_name == ""
    assert result.opportunities[0].contact_observation_ids == []
    assert any("named contacts were omitted" in item for item in result.limitations)


@pytest.mark.parametrize("published_role,keep", [("Estates lead", True), ("HR lead", False)])
def test_named_contact_and_role_must_appear_together_in_a_source_observation(published_role, keep):
    responses = FakeResponses()
    original = responses.create
    def fake(**kwargs):
        response = original(**kwargs)
        name = kwargs["text"]["format"]["name"]
        if name == "misi_research_search":
            payload = json.loads(response.output_text)
            payload["observations"][0]["fact"] = f"Example names Jane Smith as {published_role}."
            response.output_text = json.dumps(payload)
        if name == "misi_research_synthesis":
            payload = json.loads(response.output_text)
            payload["opportunities"][0]["contact_name"] = "Jane Smith"
            payload["opportunities"][0]["contact_role"] = "Estates lead"
            payload["opportunities"][0]["contact_observation_ids"] = ["O1"]
            response.output_text = json.dumps(payload)
        return response
    responses.create = fake
    result = research_universal(UniversalResearchRequest(brief="Find fire maintenance opportunities"),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert bool(result.opportunities[0].contact_name) is keep


def test_general_guidance_does_not_count_as_second_organisation_signal():
    responses = FakeResponses()
    original = responses.create
    def fake(**kwargs):
        response = original(**kwargs)
        if kwargs["text"]["format"]["name"] == "misi_research_search":
            payload = json.loads(response.output_text)
            payload["observations"][1]["fact"] = "Generic guidance explains general fire safety requirements."
            response.output_text = json.dumps(payload)
        return response
    responses.create = fake
    result = research_universal(UniversalResearchRequest(brief="Find fire maintenance opportunities"),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert len(result.observations) == 2 and not result.opportunities
    assert any("omitted" in item for item in result.limitations)


@pytest.mark.parametrize("location,first,second,expected", [
    ("Carlingwark House, Castle Douglas", "Example operates Carlingwark House.", "Carlingwark House plans to upgrade its estate.", True),
    ("Castle Douglas, Scotland", "Example operates in Castle Douglas.", "Another service in Castle Douglas plans upgrades.", False),
    ("Carlingwark House, Scotland", "Example runs a care business.", "Carlingwark House plans upgrades.", False),
    ("Care Home, Scotland", "Example operates a care home.", "A care home plans upgrades.", False),
])
def test_named_site_fallback_requires_two_sources_and_explicit_organisation_link(location, first, second, expected):
    responses = FakeResponses()
    original = responses.create
    def fake(**kwargs):
        response = original(**kwargs)
        name = kwargs["text"]["format"]["name"]
        if name == "misi_research_search":
            payload = json.loads(response.output_text)
            payload["observations"][0]["fact"] = first
            payload["observations"][1]["fact"] = second
            response.output_text = json.dumps(payload)
        if name == "misi_research_synthesis":
            payload = json.loads(response.output_text)
            payload["opportunities"][0]["location"] = location
            response.output_text = json.dumps(payload)
        return response
    responses.create = fake
    result = research_universal(UniversalResearchRequest(brief="Find fire maintenance opportunities"),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert bool(result.opportunities) is expected
    assert any("identity" in limit for limit in result.limitations)


def test_generated_phone_and_email_are_redacted_from_recommendation():
    responses = FakeResponses()
    original = responses.create
    def fake(**kwargs):
        response = original(**kwargs)
        if kwargs["text"]["format"]["name"] == "misi_research_synthesis":
            payload = json.loads(response.output_text)
            payload["opportunities"][0]["engagement"] = "Call 020 7123 4567 or email someone@example.org."
            response.output_text = json.dumps(payload)
        return response
    responses.create = fake
    result = research_universal(UniversalResearchRequest(brief="Find fire maintenance opportunities"),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_api_key=None, openai_model="test-model"))
    engagement = result.opportunities[0].engagement
    assert "020 7123 4567" not in engagement and "someone@example.org" not in engagement
    assert "verify via source" in engagement


def test_request_limits_research_breadth():
    with pytest.raises(ValueError):
        UniversalResearchRequest(brief="Find fire maintenance opportunities", max_searches=13)


def test_adaptive_followup_uses_observations_and_preserves_budget_and_failures():
    class AdaptiveResponses:
        def __init__(self):
            self.calls = []
        def create(self, **kwargs):
            self.calls.append(kwargs)
            data = json.loads(kwargs["input"])
            name = kwargs["text"]["format"]["name"]
            if name == "misi_research_plan":
                return SimpleNamespace(output_text=json.dumps({"queries":["Initial query one", "Initial query two", "Initial query three", "Initial query four"]}), output=[])
            if name == "misi_research_followup_plan":
                assert data["remaining_searches"] == 2
                assert data["observations"][0]["fact"] == "Example operates Carlingwark House."
                return SimpleNamespace(output_text=json.dumps({"queries":["Corroborate Carlingwark House", "Review Carlingwark House contacts"]}), output=[])
            if name == "misi_research_search":
                query = data["planned_query"]
                if query == "Review Carlingwark House contacts":
                    raise OpenAIError("unavailable")
                index = {"Initial query one":1, "Initial query two":2, "Corroborate Carlingwark House":3}[query]
                fact = {1:"Example operates Carlingwark House.", 2:"General sector context.", 3:"Carlingwark House reported a site change."}[index]
                if query.startswith("Corroborate"):
                    assert data["prior_observations"][0]["fact"] == "Example operates Carlingwark House."
                url = f"https://example{index}.org/source"
                action = SimpleNamespace(type="search", query=f"executed {index}", queries=None, sources=[SimpleNamespace(url=url)])
                return SimpleNamespace(output_text=json.dumps({"observations":[{"source_url":url, "source_title":"Source", "published_date":"", "fact":fact}]}),
                    output=[SimpleNamespace(type="web_search_call", action=action)])
            result = {"opportunities":[{"organisation":"Example", "location":"Carlingwark House, Scotland", "headline":"Discuss maintenance", "thesis":"The site change merits a question.",
                 "supporting_observation_ids":["O1","O3"], "counter_observation_ids":[], "unknowns":["Current status"], "contact_name":"", "contact_role":"Estates lead",
                 "contact_observation_ids":[], "engagement":"Ask how changes affect maintenance.", "verification_action":"Check sources."}], "limitations":[]}
            return SimpleNamespace(output_text=json.dumps(result), output=[])
    responses = AdaptiveResponses()
    brief = "Find Scottish care maintenance signals"
    progress = []
    result = research_universal(UniversalResearchRequest(brief=brief, max_searches=4),
        client=SimpleNamespace(responses=responses), settings=Settings(research_provider="openai", openai_api_key=None, openai_model="test-model"), progress_callback=progress.append)
    assert len(result.searches) == 4
    assert [item.stage for item in result.searches] == ["initial", "initial", "follow_up", "follow_up"]
    assert [item.status for item in result.searches] == ["completed", "completed", "completed", "failed"]
    assert result.searches[2].web_queries == ["executed 3"]
    assert len(result.opportunities) == 1 and result.opportunities[0].supporting_observation_ids == ["O1", "O3"]
    assert any("partial" in item for item in result.limitations)
    assert all(json.loads(call["input"])["brief"] == brief for call in responses.calls)
    assert len([call for call in responses.calls if call["text"]["format"]["name"] == "misi_research_search"]) == 4
    assert progress[-1]["planned"] == 4 and progress[-1]["completed"] == 3 and progress[-1]["failed"] == 1


def test_deep_research_adapts_again_after_new_followup_evidence():
    class IterativeResponses:
        def __init__(self):
            self.followup_inputs = []

        def create(self, **kwargs):
            body = json.loads(kwargs["input"])
            name = kwargs["text"]["format"]["name"]
            if name == "misi_research_plan":
                result = {"queries": [f"Original market search {index}" for index in range(1, 8)]}
            elif name == "misi_research_followup_plan":
                self.followup_inputs.append(body)
                if len(self.followup_inputs) == 1:
                    assert body["remaining_searches"] == 3
                    result = {"queries": ["Example targeted search one", "Example targeted search two", "Example targeted search three"]}
                else:
                    assert body["remaining_searches"] == 1
                    assert any("Newly discovered" in item["fact"] for item in body["observations"])
                    assert "Example targeted search one" in body["earlier_planned_queries"]
                    result = {"queries": ["Example final counter evidence"]}
            elif name == "misi_research_search":
                query = body["planned_query"]
                label = query.replace(" ", "-").lower()
                url = f"https://example.org/{label}"
                fact = ("Example: Newly discovered service context." if "targeted" in query
                        else f"Example observation from {query}.")
                action = SimpleNamespace(type="search", query=query, queries=None, sources=[SimpleNamespace(url=url)])
                return SimpleNamespace(output_text=json.dumps({"observations": [{"source_url": url, "source_title": "Source",
                    "published_date": "", "fact": fact}]}), output=[SimpleNamespace(type="web_search_call", action=action)])
            else:
                result = {"opportunities": [], "limitations": []}
            return SimpleNamespace(output_text=json.dumps(result), output=[])

    responses = IterativeResponses()
    progress = []
    result = research_universal(UniversalResearchRequest(brief="Investigate early maintenance opportunities", max_searches=7),
        client=SimpleNamespace(responses=responses), settings=Settings(openai_model="test-model"), progress_callback=progress.append)
    assert len(responses.followup_inputs) == 2
    assert len(result.searches) == 7
    assert [item.stage for item in result.searches] == ["initial"] * 3 + ["follow_up"] * 4
    assert result.searches[-1].query == "Example final counter evidence"
    assert progress[-1]["planned"] == 7 and progress[-1]["completed"] == 7
