from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.intelligence.evidence_graph import _public_link, build_evidence_graph
from app.models.research_dossier import ResearchLead, SavedResearchRun
from app.routers.evidence_graph import router


def test_graph_shows_only_explicit_citations_and_preserves_counter_context():
    opportunity = {"organisation": "Example Ltd", "location": "Bristol", "headline": "A possible review",
                   "thesis": "A hypothesis, not proof", "contact_role": "Estates lead", "unknowns": ["Current supplier"],
                   "engagement": "Ask who owns the service", "verification_action": "Confirm the arrangement",
                   "supporting_observation_ids": ["a"], "counter_observation_ids": ["b"], "contact_observation_ids": []}
    observations = [
        {"id": "a", "fact": "A report describes a programme", "source_url": "https://example.org/report?year=2025#page2",
         "source_title": "Report", "published_date": "2025-01-01", "origin": "web_search"},
        {"id": "b", "fact": "A subsequent report describes existing cover", "source_url": "https://example.org/report?year=2025",
         "source_title": "Report", "published_date": "2025-02-01", "origin": "web_search"},
        {"id": "c", "fact": "Unrelated context", "source_url": "https://example.org/unrelated", "source_title": "Other"},
    ]
    graph = build_evidence_graph(7, opportunity, observations)
    assert graph["lead_id"] == 7
    assert {n["id"] for n in graph["nodes"] if n["type"] == "observation"} == {"observation:a", "observation:b"}
    sources = [n for n in graph["nodes"] if n["type"] == "source"]
    assert len(sources) == 1 and sources[0]["url"] == "https://example.org/report?year=2025"
    assert {(e["relation"], e["observation_id"]) for e in graph["edges"] if e["observation_id"]} >= {
        ("supports_hypothesis", "a"), ("counter_context", "b"), ("attributed_to", "a"), ("attributed_to", "b")}
    assert all(node["verification"] == "unverified" for node in graph["nodes"])
    assert all(edge["verification"] == "unverified" for edge in graph["edges"])
    assert graph["unknowns"] == ["Current supplier"]
    assert graph["missing_references"] == []
    assert not any(n.get("label") == "Unrelated context" for n in graph["nodes"])
    assert "not proof" in graph["limitations"][2]


def test_graph_never_guesses_missing_or_ambiguous_references_or_trusts_invalid_links():
    opportunity = {"supporting_observation_ids": ["duplicate", "absent", "unsafe"], "counter_observation_ids": [],
                   "contact_name": "A person", "contact_role": "Facilities lead"}
    observations = [
        {"id": "duplicate", "fact": "First", "source_url": "https://example.org/a"},
        {"id": "duplicate", "fact": "Second", "source_url": "https://example.org/b"},
        {"id": "unsafe", "fact": "Source claim", "source_url": "javascript:alert(1)"},
    ]
    graph = build_evidence_graph(4, opportunity, observations)
    assert graph["missing_references"] == [
        {"id": "duplicate", "relation": "supports_hypothesis", "reason": "ambiguous"},
        {"id": "absent", "relation": "supports_hypothesis", "reason": "missing"}]
    assert [n["id"] for n in graph["nodes"] if n["type"] == "observation"] == ["observation:unsafe"]
    assert not any(n["type"] == "source" for n in graph["nodes"])
    assert not any(n.get("label") == "A person" for n in graph["nodes"])
    assert any(n["type"] == "stakeholder_role" and n["label"] == "Facilities lead" for n in graph["nodes"])


def test_long_identifiers_and_urls_are_rejected_rather_than_silently_truncated():
    prefix = "x" * 120
    graph = build_evidence_graph(1, {"supporting_observation_ids": [prefix + "a", "safe-id"]}, [
        {"id": prefix + "b", "fact": "Wrong observation", "source_url": "https://example.org/other"},
        {"id": "safe-id", "fact": "Claim with long URL", "source_url": "https://example.org/" + "p" * 2048},
    ])
    assert not any(n.get("label") == "Wrong observation" for n in graph["nodes"])
    assert any(item["reason"] == "invalid" for item in graph["missing_references"])
    assert not any(n["type"] == "source" for n in graph["nodes"])


def test_private_host_links_are_not_presented_as_public_sources():
    for url in ("http://localhost/a", "http://127.0.0.1/a", "http://[::1]/a", "http://10.0.0.5/a",
                "https://service.internal/a", "https://user:pass@example.org/a"):
        assert _public_link(url) is None
    assert _public_link("https://example.org/report?a=1#section") == "https://example.org/report?a=1"


def test_endpoint_reads_a_single_saved_lead_without_creating_graph_records(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'graph.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(router)

    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    with sessions() as db:
        run = SavedResearchRun(job_id="job", brief="Find maintenance", model="model", completed_at=datetime.now(UTC),
                               result={"observations": [{"id": "a", "fact": "A public observation", "source_url": "https://example.org/a"},
                                                        {"id": "b", "fact": "Another account", "source_url": "https://example.org/b"}]})
        db.add(run)
        db.flush()
        lead = ResearchLead(run_id=run.id, position=0, organisation="Example", location="Bristol", headline="Review",
                            opportunity={"organisation": "Example", "location": "Bristol", "headline": "Review",
                                         "supporting_observation_ids": ["a"], "counter_observation_ids": []})
        db.add(lead)
        db.commit()
        lead_id = lead.id
    with TestClient(app) as client:
        assert client.get("/api/research-dossiers/leads/999/evidence-map").status_code == 404
        result = client.get(f"/api/research-dossiers/leads/{lead_id}/evidence-map")
        assert result.status_code == 200
        assert [n["observation_id"] for n in result.json()["nodes"] if n["type"] == "observation"] == ["a"]
        assert "Another account" not in result.text
    engine.dispose()
