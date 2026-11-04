from datetime import UTC, date, datetime
from types import SimpleNamespace
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.intelligence.universal_research import _matching_imports, _synthesise, research_universal
from app.models.evidence_observation import EvidenceObservation
from app.schemas.universal_research import ResearchObservation, UniversalResearchRequest


def _db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'research-inbox.db'}")
    EvidenceObservation.__table__.create(engine)
    return sessionmaker(engine)


def _add(db, number, name, site="Unknown", url="https://official.example.org/notice"):
    item = EvidenceObservation(fingerprint=str(number).zfill(64), organisation_id=f"test:{number}",
        organisation_name=name, site=site, category="maintenance", observed_statement="A historical maintenance award was reported.",
        source_title="Public notice", source_reference=f"notice {number}", source_url=url,
        published_at=date(2025, 1, 1), observed_at=date(2025, 1, 1), retrieved_at=datetime.now(UTC))
    db.add(item)
    return item


def _web(fact):
    return ResearchObservation(id="O1", source_url="https://web.example.org/news", source_title="News", published_date="2026", fact=fact)


def test_only_exact_mentioned_account_and_public_looking_sources_are_sent(tmp_path):
    sessions = _db(tmp_path)
    with sessions() as db:
        _add(db, 1, "Example Ltd", site="Example House")
        _add(db, 2, "Example Ltd West")
        _add(db, 3, "Example Ltd", url="http://127.0.0.1/private")
        _add(db, 4, "Other Ltd")
        db.commit()
    matched, notes = _matching_imports([_web("Example Ltd has an estate change.")], sessions)
    assert len(matched) == 1
    item = matched[0]
    assert item.organisation_name == "Example Ltd" and item.site == "Example House"
    assert item.origin == "evidence_inbox" and item.organisation_id == "test:1"
    assert item.source_reference == "notice 1" and item.observed_date == "2025-01-01"
    assert item.retrieved_at and item.source_url == "https://official.example.org/notice"
    matched, _ = _matching_imports([_web("Example Ltd West has an estate change.")], sessions)
    assert [item.organisation_name for item in matched] == ["Example Ltd West"]


def test_inbox_signal_reaches_synthesis_and_is_cited_as_unverified(tmp_path):
    sessions = _db(tmp_path)
    with sessions() as db:
        _add(db, 1, "Example Ltd", url="https://official.example.org/notice?token=private")
        db.commit()
    calls = []
    class Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            name = kwargs["text"]["format"]["name"]
            if name == "misi_research_plan":
                return SimpleNamespace(output_text=json.dumps({"queries": ["Example Ltd estates change", "Example Ltd maintenance context"]}), output=[])
            if name == "misi_research_followup_plan":
                prior = json.loads(kwargs["input"])["observations"]
                assert any(item["origin"] == "evidence_inbox" for item in prior)
                return SimpleNamespace(output_text=json.dumps({"queries": ["Example Ltd verify maintenance"]}), output=[])
            if name == "misi_research_search":
                action = SimpleNamespace(type="search", query="Example Ltd", sources=[SimpleNamespace(url="https://web.example.org/news")])
                fact = {"source_url":"https://web.example.org/news", "source_title":"News", "published_date":"2026", "fact":"Example Ltd described an estate change."}
                return SimpleNamespace(output_text=json.dumps({"observations": [fact]}), output=[SimpleNamespace(type="web_search_call",action=action)])
            data = json.loads(kwargs["input"])
            local = next(item for item in data["observations"] if item["origin"] == "evidence_inbox")
            assert local["source_reference"] == "notice 1" and local["site"] == "Unknown"
            assert local["source_url"] == "https://official.example.org/notice"
            opportunity = {"organisation":"Example Ltd", "location":"Yorkshire", "headline":"Ask about maintenance", "thesis":"A change could affect services.",
                "supporting_observation_ids":["O1",local["id"]], "counter_observation_ids":[local["id"]], "unknowns":["Current provider"],
                "contact_name":"", "contact_role":"Estates lead", "contact_observation_ids":[], "engagement":"Ask about their service.",
                "verification_action":"Confirm current scope.", "potential_solution":"Discuss a possible review of maintenance arrangements."}
            return SimpleNamespace(output_text=json.dumps({"opportunities":[opportunity],"limitations":[]}), output=[])
    result = research_universal(UniversalResearchRequest(brief="Find maintenance signals for Example Ltd", max_searches=2, include_inbox=True),
        client=SimpleNamespace(responses=Responses()), settings=Settings(openai_api_key=None, openai_model="test-model"), evidence_session_factory=sessions)
    assert len(result.opportunities) == 1
    assert result.include_inbox is True
    assert result.opportunities[0].counter_observation_ids == ["I1"]
    assert "possible review" in result.opportunities[0].potential_solution
    assert any("exact organisation-name" in note for note in result.limitations)
    assert result.observations[1].origin == "evidence_inbox"
    assert result.observations[1].source_url.endswith("?token=private")
    assert all("token=private" not in call["input"] for call in calls)
    assert any(call["text"]["format"]["name"] == "misi_research_followup_plan" for call in calls)


def test_imported_account_or_site_cannot_be_misattributed():
    class Responses:
        def __init__(self, organisation, location):
            self.organisation, self.location = organisation, location
        def create(self, **kwargs):
            opportunity = {"organisation":self.organisation, "location":self.location, "headline":"Ask about maintenance", "thesis":"A possible conversation.",
                "supporting_observation_ids":["O1","I1"], "counter_observation_ids":[], "unknowns":[], "contact_name":"", "contact_role":"Estates lead",
                "contact_observation_ids":[], "engagement":"Ask who owns the service.", "verification_action":"Confirm the site.", "potential_solution":"Explore maintenance options."}
            return SimpleNamespace(output_text=json.dumps({"opportunities":[opportunity], "limitations":[]}), output=[])
    local = ResearchObservation(id="I1", source_url="https://example.org/report", source_title="Report", published_date="2025",
        fact="Example Ltd reported maintenance.", origin="evidence_inbox", organisation_name="Example Ltd", site="Unknown")
    sources = [_web("Example Ltd operates Example House."), local]
    request = UniversalResearchRequest(brief="Find maintenance opportunities for Example Ltd")
    settings = Settings(openai_api_key=None, openai_model="test-model")
    mismatch = _synthesise(request, sources, [], SimpleNamespace(responses=Responses("Example Ltd West", "Yorkshire")), settings)
    named_site = _synthesise(request, sources, [], SimpleNamespace(responses=Responses("Example Ltd", "Example House, Yorkshire")), settings)
    assert not mismatch.opportunities and not named_site.opportunities
    local.site = "Example House"
    correct = _synthesise(request, sources, [], SimpleNamespace(responses=Responses("Example Ltd", "Example House, Yorkshire")), settings)
    assert len(correct.opportunities) == 1
