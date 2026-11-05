import csv
import io
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.ingestion import eric_site_references
from app.intelligence.site_research import SiteResearchResult, research_site
from app.intelligence.openai_client import InvalidOpenAIJSONError


def test_eric_exact_identifier_only_and_shared_identifiers_are_retained(monkeypatch):
    monkeypatch.setattr(eric_site_references, "validate_official_file", lambda data: None)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["", "", "", "", "", ""])
    writer.writerow(["Trust Code", "Trust Name", "EFM Site Id", "Site Name", "Post Code", "UPRN"])
    writer.writerow(["ABC", "Trust A", "1", "Site A", "SW1A 1AA", "123456789012"])
    writer.writerow(["DEF", "Trust B", "2", "Site B", "SW1A 1AA", "123456789012"])
    writer.writerow(["GHI", "Trust C", "3", "Site C", "", "1.23457E+11"])
    rows = eric_site_references.parse_site_references(stream.getvalue().encode("cp1252"))
    assert len(rows) == 2
    assert {row["organisation_id"] for row in rows} == {"nhs-ods:ABC", "nhs-ods:DEF"}
    assert {row["uprn"] for row in rows} == {"123456789012"}


def test_site_research_requires_identity_and_contact_sources():
    payload = dict(identity_status="candidate", organisation="Org", site_name="Site", identity_explanation="Possible match",
                   identity_sources=[], inferred_maintenance_need="Unknown", contact_name="A Name", contact_role="Facilities lead",
                   contact_sources=[], engagement="Ask who maintains systems.", limitations=[])
    with pytest.raises(ValidationError):
        SiteResearchResult.model_validate(payload)
    payload.update(identity_status="unknown", organisation="", site_name="", contact_name="")
    assert SiteResearchResult.model_validate(payload).identity_status == "unknown"


def test_research_uses_web_and_preserves_no_match():
    payload = {"identity_status":"unknown", "organisation":"", "site_name":"", "identity_explanation":"No reliable match",
               "identity_sources":[], "inferred_maintenance_need":"Unknown", "contact_name":"", "contact_role":"Estates lead once identified",
               "contact_sources":[], "engagement":"Verify site identity first.", "limitations":["The address is unknown."]}
    class Responses:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(output_text=json.dumps(payload), output=[{"type": "web_search_call", "action": {"type": "search", "queries": ["example"], "sources": []}}])
    responses = Responses()
    result = research_site({"uprn":"123"}, client=SimpleNamespace(responses=responses),
                           settings=Settings(openai_api_key=None, openai_model="test-model"))
    assert result.identity_status == "unknown"
    assert responses.kwargs["tools"][0]["type"] == "web_search"
    assert responses.kwargs["store"] is False
    assert responses.kwargs["include"] == ["web_search_call.action.sources"]
    assert "different building or block" in responses.kwargs["instructions"]
    assert "not proof" in responses.kwargs["instructions"]


def test_site_research_removes_identity_and_contact_when_urls_were_not_returned():
    payload = {"identity_status":"candidate", "organisation":"Example Trust", "site_name":"Example Hospital",
        "identity_explanation":"Possible match", "identity_sources":["https://invented.example/site"],
        "inferred_maintenance_need":"Investigate", "contact_name":"Alex Smith", "contact_role":"Estates lead",
        "contact_sources":["https://invented.example/contact"], "engagement":"Call Alex", "limitations":[]}
    class Responses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text=json.dumps(payload), output=[{"type": "web_search_call",
                "action": {"type": "search", "queries": ["example"], "sources": [{"url": "https://real.example/other"}]}}])
    result = research_site({"uprn": "123"}, client=SimpleNamespace(responses=Responses()), settings=Settings(_env_file=None))
    assert result.identity_status == "unknown"
    assert result.organisation == result.site_name == result.contact_name == ""
    assert result.identity_sources == result.contact_sources == []
    assert "Verify the site" in result.engagement


def test_site_research_removes_unreturned_contact_and_requires_actual_search():
    payload = {"identity_status":"candidate", "organisation":"Example Trust", "site_name":"Example Hospital",
        "identity_explanation":"Possible match", "identity_sources":["https://real.example/site"],
        "inferred_maintenance_need":"Investigate", "contact_name":"Alex Smith", "contact_role":"Estates lead",
        "contact_sources":["https://invented.example/contact"], "engagement":"Ask who owns it", "limitations":[]}
    class Responses:
        def __init__(self, searched): self.searched = searched
        def create(self, **kwargs):
            action = {"type": "search" if self.searched else "open_page", "sources": [{"url": "https://real.example/site"}]}
            return SimpleNamespace(output_text=json.dumps(payload), output=[{"type": "web_search_call", "action": action}])
    settings = Settings(_env_file=None, research_provider="anthropic", anthropic_model="example-model")
    result = research_site({"uprn":"123"}, client=SimpleNamespace(responses=Responses(True)), settings=settings)
    assert result.identity_status == "candidate"
    assert result.identity_sources == ["https://real.example/site"]
    assert result.contact_name == "" and result.contact_sources == []
    with pytest.raises(InvalidOpenAIJSONError):
        research_site({"uprn":"123"}, client=SimpleNamespace(responses=Responses(False)), settings=settings)


def test_site_research_uses_the_configured_anthropic_adapter(monkeypatch):
    import httpx
    from app.intelligence import research_provider
    requests = []
    payload = {"identity_status":"candidate", "organisation":"Example Trust", "site_name":"Example Hospital",
        "identity_explanation":"Public source identifies the organisation and site.", "identity_sources":["https://example.org/site"],
        "inferred_maintenance_need":"Investigate", "contact_name":"", "contact_role":"Estates lead",
        "contact_sources":[], "engagement":"Ask who owns it", "limitations":[]}
    def post(url, **kwargs):
        body = kwargs["json"]
        requests.append(body)
        if "tools" in body:
            data = {"stop_reason":"end_turn", "content":[
                {"type":"server_tool_use", "name":"web_search", "id":"search-1", "input":{"query":"Example Hospital"}},
                {"type":"web_search_tool_result", "tool_use_id":"search-1", "content":[{"type":"web_search_result", "url":"https://example.org/site", "title":"Example"}]},
                {"type":"text", "text":"Example Trust identifies Example Hospital."}]}
        else:
            data = {"stop_reason":"end_turn", "content":[{"type":"text", "text":json.dumps(payload)}]}
        return httpx.Response(200, json=data, request=httpx.Request("POST", url))
    monkeypatch.setattr(research_provider.httpx, "post", post)
    settings = Settings(_env_file=None, research_provider="anthropic", anthropic_api_key="test", anthropic_model="claude-test")
    result = research_site({"uprn": "123"}, settings=settings)
    assert result.identity_status == "candidate"
    assert result.identity_sources == ["https://example.org/site"]
    assert len(requests) == 2 and all(request["model"] == "claude-test" for request in requests)


def test_research_endpoint_uses_database_signal_and_preserves_all_site_matches(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from app.db import Base, create_database_engine, get_db
    from app.main import create_app
    from app.models.public_site_reference import PublicSiteReference
    from app.models.lfb_inspection_match import LfbInspectionMatch
    from datetime import date
    from app.routers import site_research, virtual_sensor

    engine = create_database_engine(f"sqlite:///{tmp_path / 'site.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        for number, name in [("1", "Hospital"), ("2", "Other location")]:
            db.add(PublicSiteReference(source_record_id=f"test:{number}", uprn="123", organisation_id="nhs-ods:ABC",
                organisation_name="Example Trust", site_name=name, postcode="NW1", source_url="https://example.org/data", source_period="2025/26"))
        db.add(LfbInspectionMatch(fingerprint="a" * 64, uprn="123", organisation_name="Example Trust", site_name="Hospital",
            site_reference_url="https://example.org/data", site_reference_period="2025/26", postcode="NW1 1AA",
            inspection_address="Hospital, Block A", property_use="Hospital", reason_or_outcome="Audit",
            completed_on=date(2025, 1, 1), source_file="inspections.xlsx", source_sha256="b" * 64))
    def get_db_override():
        with factory() as db:
            yield db
    monkeypatch.setattr(virtual_sensor, "get_site_detail", lambda db, uprn, property_type: {
        "site": {"uprn": uprn, "property_type": property_type, "attendances": 3},
        "incidents": [{"incident_number": "excluded-from-model"}], "period_start": "2025-10-01"})
    captured = {}
    def fake_research(context):
        captured.update(context)
        return SiteResearchResult(identity_status="unknown", organisation="", site_name="", identity_explanation="Ambiguous",
            identity_sources=[], inferred_maintenance_need="Unknown", contact_name="", contact_role="Estates lead after identification",
            contact_sources=[], engagement="Check the site.", limitations=["Shared identifier"])
    monkeypatch.setattr(site_research, "research_site", fake_research)
    app = create_app()
    app.dependency_overrides[get_db] = get_db_override
    with TestClient(app) as client:
        result = client.post("/api/virtual-sensors/false-alarms/123/research", json={"property_type":"Hospital"})
    assert result.status_code == 200
    assert result.json()["research"]["identity_status"] == "unknown"
    assert len(result.json()["site_references"]) == 2
    assert captured["site"]["site"]["attendances"] == 3
    assert "incidents" not in captured["site"]
    assert captured["candidate_inspection_context"]["matches"][0]["inspection_address"] == "Hospital, Block A"
    assert "different building or block" in captured["candidate_inspection_context"]["limitations"][0]
    engine.dispose()
