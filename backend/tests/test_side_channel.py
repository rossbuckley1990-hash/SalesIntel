import json
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.intelligence.openai_client import InvalidOpenAIJSONError
from app.intelligence.side_channel import candidate_sites, synthesise_hypotheses


def record(id, category, *, site="Main Hospital", url=None, reference=None, statement=None):
    return SimpleNamespace(id=id, category=category, site=site,
        source_url=url or f"https://example.org/report/{id}", source_reference=reference or f"report-{id}",
        source_title=f"Publisher {id}",
        observed_statement=statement or "Fire alarm inspection and maintenance", published_at=None, observed_at=None)


def test_candidates_need_fire_context_distinct_sources_and_exact_known_site():
    a = record(1, "maintenance")
    b = record(2, "service_issue")
    sites = candidate_sites([a, b])
    assert sites[0].hypotheses[0].observation_ids == [2, 1]
    assert "do not establish" in sites[0].hypotheses[0].explanation or "may" in sites[0].hypotheses[0].explanation
    assert not candidate_sites([a, record(2, "service_issue", url="https://example.org/report/1?utm_source=test")])[0].hypotheses
    assert not candidate_sites([a, record(2, "service_issue", reference="report-1")])[0].hypotheses
    assert all(not site.hypotheses for site in candidate_sites([a, record(2, "service_issue", site="Other Hospital")]))
    assert not candidate_sites([record(1, "maintenance", site="Unspecified"), record(2, "service_issue", site="Unspecified")])
    generic = [record(1, "maintenance", statement="The roof needs repair"), record(2, "service_issue", statement="The lift is delayed")]
    assert not candidate_sites(generic)[0].hypotheses


def test_ai_output_citations_must_belong_to_supplied_evidence_and_is_opt_in():
    observations = [record(1, "maintenance", url="https://example.org/report/1?token=private"), record(2, "service_issue")]
    payload = {"hypotheses": [{"title": "Check service model", "explanation": "The records may indicate service pressure, but a different explanation is possible.", "supporting_observation_ids": [1, 2], "counter_observation_ids": [], "unknowns": ["The provider and cause are unknown"], "question": "How are faults managed?"}], "limitations": []}
    class Responses:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(output_text=json.dumps(payload))
    responses = Responses()
    client = SimpleNamespace(responses=responses)
    result = synthesise_hypotheses("nhs-ods:ABC", "Main Hospital", observations, client=client, settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert result.hypotheses[0].supporting_observation_ids == [1, 2]
    assert responses.kwargs["model"] == "test-model"
    assert responses.kwargs["store"] is False
    assert "unverified" in responses.kwargs["instructions"]
    submitted = json.loads(responses.kwargs["input"])
    assert submitted["observations"][0]["source_title"] == "Publisher 1"
    assert submitted["observations"][0]["source_url"] == "https://example.org/report/1"
    assert "token=private" not in responses.kwargs["input"]
    payload["hypotheses"][0]["counter_observation_ids"] = [1]
    mixed = synthesise_hypotheses("nhs-ods:ABC", "Main Hospital", observations, client=client, settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert mixed.hypotheses[0].counter_observation_ids == [1]
    payload["hypotheses"][0]["counter_observation_ids"] = [999]
    with pytest.raises(InvalidOpenAIJSONError, match="ungrounded"):
        synthesise_hypotheses("nhs-ods:ABC", "Main Hospital", observations, client=client, settings=Settings(openai_api_key=None, openai_model="test-model"))
    payload["hypotheses"][0]["counter_observation_ids"] = []
    payload["hypotheses"][0]["supporting_observation_ids"] = [1]
    with pytest.raises(InvalidOpenAIJSONError, match="ungrounded"):
        synthesise_hypotheses("nhs-ods:ABC", "Main Hospital", observations, client=client, settings=Settings(openai_api_key=None, openai_model="test-model"))
