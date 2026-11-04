from __future__ import annotations

import json
from datetime import date
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import Base, create_database_engine, get_db
from app.main import create_app
from app.models import (
    EnrichmentRun,
    ExecutiveAction,
    FieldIntelligence,
    FinanceForecast,
    Opportunity,
    OpportunityEnrichment,
)


class FakeSequentialResponses:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if not self.contents:
            raise AssertionError("No fake OpenAI response left for this request")
        return SimpleNamespace(output_text=self.contents.pop(0), output=[])


class FakeOpenAIClient:
    def __init__(self, contents: list[str]) -> None:
        self.responses = FakeSequentialResponses(contents)


def _client_with_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_client: FakeOpenAIClient | None = None,
) -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'research.db'}")
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    import app.intelligence.opportunity_research as opportunity_research
    import app.routers.intelligence as intelligence_router

    monkeypatch.setattr(
        intelligence_router,
        "get_settings",
        lambda: Settings(openai_api_key="test-key", openai_model="gpt-5.5"),
    )
    if fake_openai_client is not None:
        monkeypatch.setattr(
            opportunity_research,
            "get_openai_client",
            lambda settings: fake_openai_client,
        )

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session


def _internet_payload() -> dict[str, object]:
    return {
        "intelligence_type": "opportunity_intelligence",
        "query": "University of Leeds fire and security tender",
        "headline": "University estates show fire and security compliance demand.",
        "summary": "Public evidence indicates higher education estates require planned fire and security maintenance, but this sample does not prove a live tender.",
        "findings": [
            {
                "title": "University estates compliance signal",
                "finding": "A public estate notice references fire alarm and access-control maintenance requirements.",
                "so_what": "Mitie should qualify whether a framework or renewal route is active.",
                "recommended_action": "Check the buyer procurement portal and identify the estates decision owner.",
                "confidence_score": 0.76,
                "source_urls": ["https://example.invalid/university-estates-notice"],
            }
        ],
        "source_urls": ["https://example.invalid/university-estates-notice"],
        "risk_warnings": ["The evidence does not confirm live tender status."],
        "next_best_actions": ["Validate procurement route and tender timetable."],
        "limitations": ["Unit test fixture; no live web call was made."],
    }


def _text_field(
    value: str | None,
    value_type: str,
    confidence_score: float,
    rationale: str,
    source_urls: list[str] | None = None,
) -> dict[str, object]:
    return {
        "value": value,
        "value_type": value_type,
        "confidence_score": confidence_score,
        "rationale": rationale,
        "source_urls": source_urls or [],
    }


def _number_field(
    value: float | None,
    value_type: str,
    confidence_score: float,
    rationale: str,
    source_urls: list[str] | None = None,
) -> dict[str, object]:
    return {
        "value": value,
        "value_type": value_type,
        "confidence_score": confidence_score,
        "rationale": rationale,
        "source_urls": source_urls or [],
    }


def _commercial_payload() -> dict[str, object]:
    source_url = "https://example.invalid/university-estates-notice"
    return {
        "opportunity": {
            "name": _text_field(
                "University of Leeds fire and security maintenance opportunity",
                "inferred",
                0.74,
                "Inferred from the query and public estate maintenance signal.",
                [source_url],
            ),
            "buyer_name": _text_field(
                "University of Leeds",
                "known",
                0.93,
                "Buyer was stated by the user and matches the public source context.",
            ),
            "sector": _text_field("Education", "known", 0.9, "Buyer is a university."),
            "region": _text_field(
                "Yorkshire and the Humber",
                "inferred",
                0.84,
                "Inferred from the buyer location.",
            ),
            "source_type": _text_field(
                "AI internet research",
                "known",
                0.95,
                "Record is generated from backend OpenAI web research.",
                [source_url],
            ),
            "stage": _text_field(
                "Market signal",
                "inferred",
                0.72,
                "No live tender deadline was evidenced.",
                [source_url],
            ),
            "estimated_annual_revenue": _number_field(
                350000,
                "estimated",
                0.57,
                "Estimated from comparable multi-site education estate maintenance scope.",
                [source_url],
            ),
            "estimated_total_contract_value": _number_field(
                1400000,
                "estimated",
                0.58,
                "Estimated from likely four-year maintenance scope and comparable estate contracts.",
                [source_url],
            ),
            "estimated_gross_margin": _number_field(
                420000,
                "estimated",
                0.52,
                "Estimated at 30 percent gross margin pending delivery validation.",
                [source_url],
            ),
            "margin_percentage": _number_field(
                30,
                "estimated",
                0.52,
                "Estimated margin using a self-delivery-led maintenance assumption.",
            ),
            "probability": _number_field(
                42,
                "estimated",
                0.61,
                "Percentage probability reflects a credible but unconfirmed market signal.",
                [source_url],
            ),
            "submission_deadline": _text_field(
                None,
                "unknown",
                0,
                "No submission deadline was evidenced in the available public sources.",
                [source_url],
            ),
            "forecast_start_month": _text_field(
                "2026-10",
                "estimated",
                0.44,
                "Indicative start month only; procurement timetable is unconfirmed.",
            ),
            "self_delivery_fit": _text_field(
                "High",
                "inferred",
                0.7,
                "Scope aligns to Mitie Fire & Security self-delivery disciplines.",
            ),
            "risk_rating": _text_field(
                "Amber",
                "inferred",
                0.73,
                "Procurement route and incumbent are not confirmed.",
            ),
            "strategic_fit_score": _number_field(
                78,
                "estimated",
                0.62,
                "Strategic fit is attractive but not yet a must-win.",
            ),
            "bid_no_bid_recommendation": _text_field(
                "Watch",
                "inferred",
                0.75,
                "No live tender supports bid commitment yet.",
            ),
            "recommended_action": _text_field(
                "Validate tender route and qualify estate scope before committing bid resources.",
                "inferred",
                0.82,
                "Next action follows from the unconfirmed tender status.",
                [source_url],
            ),
        },
        "intelligence": {
            "buyer_summary": "Large higher education estate with likely statutory compliance and asset uptime drivers.",
            "opportunity_summary": "Potential fire and security maintenance opportunity requiring procurement-route validation.",
            "likely_scope": [
                "Fire alarms",
                "Emergency lighting",
                "CCTV and access control",
            ],
            "likely_buyer_drivers": ["Compliance assurance", "Estate uptime", "Responsive maintenance"],
            "compliance_drivers": ["Fire safety compliance", "Duty of care across teaching and residential estate"],
            "competitor_assessment": "Incumbent is not confirmed; regional specialists may be competitive on price.",
            "mobilisation_assessment": "Mobilisation confidence depends on asset volumes, access constraints and regional engineering capacity.",
            "commercial_assessment": "Worth tracking, but should remain Watch until procurement route is confirmed.",
            "self_delivery_assessment": "Strong potential fit for Mitie Fire & Security if the estate scope is confirmed.",
            "finance_assessment": "Likely category only; finance should not treat this as committed pipeline.",
            "executive_recommendation": "Track and qualify before bid commitment.",
            "unknowns": ["Submission deadline", "Incumbent supplier", "Asset volumes"],
            "recommended_next_steps": [
                "Check the university procurement portal",
                "Identify incumbent supplier",
                "Confirm asset list and contract term",
            ],
            "overall_confidence": 0.68,
        },
        "executive_action": {
            "priority": "Medium",
            "category": "Opportunity Qualification",
            "owner": "Sales Director",
            "due_date": "2026-07-08",
            "commercial_value": 1400000,
            "reason": "Potential seven-figure education estate opportunity with unconfirmed procurement route.",
            "recommended_action": "Assign a sales lead to validate the route to market and incumbent position.",
        },
        "sources": [
            {
                "title": "University estates compliance signal",
                "url": source_url,
                "source_type": "Public web",
                "relevance": "Supports estate maintenance and compliance demand.",
            }
        ],
    }


def test_research_opportunity_creates_rich_commercial_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeOpenAIClient(
        [
            json.dumps(_internet_payload()),
            json.dumps(_commercial_payload()),
        ]
    )
    client, testing_session = _client_with_database(
        tmp_path,
        monkeypatch,
        fake_client,
    )

    response = client.post(
        "/api/intelligence/research-opportunity",
        json={
            "query": "University of Leeds fire and security tender",
            "sector_hint": "Education",
            "region_hint": "Yorkshire",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_opportunity"] is True
    assert body["opportunity"]["buyer_name"] == "University of Leeds"
    assert body["opportunity"]["estimated_total_contract_value"] == 1400000
    assert body["opportunity"]["probability"] == 0.42
    assert body["opportunity"]["weighted_value"] == 588000
    assert body["opportunity_enrichment"]["overall_confidence"] == 0.68
    assert body["finance_forecast"]["forecast_category"] == "Best case"
    assert body["executive_action"]["category"] == "Opportunity Qualification"
    assert body["sources"][0]["url"] == "https://example.invalid/university-estates-notice"
    assert body["sources"][0]["source_type"] == "Public web"

    field_names = {field["field_name"] for field in body["field_intelligence"]}
    assert "estimated_total_contract_value" in field_names
    assert "forecast_start_month" in field_names
    assert "submission_deadline" in field_names
    assert "weighted_value" in field_names
    assert len(field_names) == 19

    estimated_value = next(
        field
        for field in body["field_intelligence"]
        if field["field_name"] == "estimated_total_contract_value"
    )
    assert estimated_value["value_type"] == "estimated"
    assert estimated_value["confidence_score"] == 0.58
    assert estimated_value["needs_user_confirmation"] is True
    assert "Validate" in estimated_value["recommended_next_step"]

    weighted_value = next(
        field
        for field in body["field_intelligence"]
        if field["field_name"] == "weighted_value"
    )
    assert weighted_value["value_type"] == "system_calculated"
    assert weighted_value["field_value"] == 588000

    assert len(fake_client.responses.calls) == 2
    assert fake_client.responses.calls[0]["tools"] == [
        {"type": "web_search", "search_context_size": "low"}
    ]
    text_format = fake_client.responses.calls[1]["text"]["format"]
    assert text_format["name"] == "misi_standing_start_opportunity"
    assert text_format["strict"] is True
    assert "University of Leeds fire and security tender" in fake_client.responses.calls[1]["input"]

    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 1
        assert db.scalar(select(func.count(FieldIntelligence.id))) == 19
        assert db.scalar(select(func.count(OpportunityEnrichment.id))) == 1
        assert db.scalar(select(func.count(FinanceForecast.id))) == 1
        assert db.scalar(select(func.count(ExecutiveAction.id))) == 1

        run = db.scalar(select(EnrichmentRun))
        assert run is not None
        assert run.status == "completed"
        assert run.search_performed is True
        assert run.records_created == 23
        assert run.sources_checked[0]["url"] == "https://example.invalid/university-estates-notice"


def test_research_opportunity_preview_mode_does_not_create_opportunity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeOpenAIClient(
        [
            json.dumps(_internet_payload()),
            json.dumps(_commercial_payload()),
        ]
    )
    client, testing_session = _client_with_database(
        tmp_path,
        monkeypatch,
        fake_client,
    )

    response = client.post(
        "/api/intelligence/research-opportunity",
        json={
            "query": "University of Leeds fire and security tender",
            "create_opportunity": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_opportunity"] is False
    assert body["opportunity"] is None
    assert body["field_intelligence"] == []
    assert body["draft_opportunity"]["buyer_name"] == "University of Leeds"
    assert len(body["draft_field_intelligence"]) == 19

    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 0
        run = db.scalar(select(EnrichmentRun))
        assert run is not None
        assert run.status == "completed"
        assert run.records_created == 0


def test_chatgpt_assist_prompt_contains_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _client_with_database(tmp_path, monkeypatch)

    response = client.post(
        "/api/intelligence/chatgpt-assist/prompt",
        json={
            "query": "University of Leeds fire and security tender",
            "sector_hint": "Education",
            "create_opportunity": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "Copy this prompt into ChatGPT Plus" in body["copy_steps"][0]
    assert "Return valid JSON only" in body["prompt"]
    assert "estimated_total_contract_value" in body["prompt"]
    assert body["expected_output_schema"]["required"] == [
        "opportunity",
        "intelligence",
        "executive_action",
        "sources",
    ]


def test_chatgpt_assist_import_creates_opportunity_without_openai(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = _client_with_database(tmp_path, monkeypatch)

    response = client.post(
        "/api/intelligence/chatgpt-assist/import",
        json={
            "query": "University of Leeds fire and security tender",
            "sector_hint": "Education",
            "create_opportunity": True,
            "result_json": json.dumps(_commercial_payload()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_opportunity"] is True
    assert body["opportunity"]["buyer_name"] == "University of Leeds"
    assert body["enrichment_run"]["run_type"] == "manual_chatgpt_assist"
    assert len(body["draft_field_intelligence"]) == 19

    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 1
        assert db.scalar(select(func.count(FieldIntelligence.id))) == 19
        run = db.scalar(select(EnrichmentRun))
        assert run is not None
        assert run.status == "completed"
        assert run.model_used == "chatgpt_plus_manual"


def test_chatgpt_assist_import_rejects_invalid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, testing_session = _client_with_database(tmp_path, monkeypatch)

    response = client.post(
        "/api/intelligence/chatgpt-assist/import",
        json={
            "query": "University of Leeds fire and security tender",
            "create_opportunity": True,
            "result_json": "not valid json",
        },
    )

    assert response.status_code == 422
    assert "not valid SalesIntel structured JSON" in response.json()["detail"]

    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 0
        run = db.scalar(select(EnrichmentRun))
        assert run is not None
        assert run.status == "failed"


def test_research_opportunity_rejects_invalid_conversion_without_creating_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeOpenAIClient(
        [
            json.dumps(_internet_payload()),
            json.dumps({"not": "valid"}),
        ]
    )
    client, testing_session = _client_with_database(
        tmp_path,
        monkeypatch,
        fake_client,
    )

    response = client.post(
        "/api/intelligence/research-opportunity",
        json={"query": "University of Leeds fire and security tender"},
    )

    assert response.status_code == 502
    assert "standing-start opportunity research" in response.json()["detail"]

    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 0
        run = db.scalar(select(EnrichmentRun))
        assert run is not None
        assert run.status == "failed"
        assert "invalid structured JSON" in run.error_message


def test_research_opportunity_rejects_unknown_field_with_confidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_payload = _commercial_payload()
    invalid_payload["opportunity"]["forecast_start_month"] = _text_field(
        None,
        "unknown",
        0.4,
        "No start month is evidenced, but this incorrectly carries confidence.",
    )
    fake_client = FakeOpenAIClient(
        [
            json.dumps(_internet_payload()),
            json.dumps(invalid_payload),
        ]
    )
    client, testing_session = _client_with_database(
        tmp_path,
        monkeypatch,
        fake_client,
    )

    response = client.post(
        "/api/intelligence/research-opportunity",
        json={"query": "University of Leeds fire and security tender"},
    )

    assert response.status_code == 502
    assert "standing-start opportunity research" in response.json()["detail"]

    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 0
        run = db.scalar(select(EnrichmentRun))
        assert run is not None
        assert run.status == "failed"
        assert "invalid structured JSON" in run.error_message


def test_autofill_opportunities_enriches_incomplete_records_without_overwriting_user_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeOpenAIClient(
        [
            json.dumps(_internet_payload()),
            json.dumps(_commercial_payload()),
        ]
    )
    client, testing_session = _client_with_database(
        tmp_path,
        monkeypatch,
        fake_client,
    )

    with testing_session() as db:
        db.add_all(
            [
                Opportunity(
                    name="West Yorkshire Police estate maintenance signal",
                    buyer_name="West Yorkshire Police",
                    sector="Police",
                    region="Yorkshire and the Humber",
                    source_type="",
                    stage="Market signal",
                    owner="Sales Director",
                    estimated_annual_revenue=0,
                    estimated_total_contract_value=0,
                    estimated_gross_margin=0,
                    margin_percentage=0,
                    probability=0,
                    weighted_value=0,
                    forecast_start_month=None,
                    self_delivery_fit="unknown",
                    risk_rating="unknown",
                    strategic_fit_score=0,
                    bid_no_bid_recommendation="review_required",
                    recommended_action="",
                ),
                Opportunity(
                    name="Protected complete opportunity",
                    buyer_name="Existing Buyer",
                    sector="Healthcare",
                    region="North West",
                    source_type="CRM",
                    stage="Pricing",
                    owner="Commercial Manager",
                    estimated_annual_revenue=250000,
                    estimated_total_contract_value=1000000,
                    estimated_gross_margin=300000,
                    margin_percentage=30,
                    probability=0.55,
                    weighted_value=550000,
                    submission_deadline=date(2026, 9, 1),
                    forecast_start_month="2026-10",
                    self_delivery_fit="High",
                    risk_rating="Amber",
                    strategic_fit_score=76,
                    bid_no_bid_recommendation="Pursue",
                    recommended_action="Protect user-provided values.",
                ),
            ]
        )
        db.commit()

    response = client.post(
        "/api/intelligence/autofill-opportunities",
        json={"only_incomplete": True, "limit": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["records_scanned"] == 1
    assert body["records_enriched"] == 1
    assert body["records_skipped"] == 1
    assert body["records_failed"] == 0
    assert body["fields_filled"] > 0
    assert body["fields_still_unknown"] >= 1
    assert body["results"][0]["status"] == "enriched"

    with testing_session() as db:
        opportunity = db.scalar(
            select(Opportunity).where(
                Opportunity.name == "West Yorkshire Police estate maintenance signal",
            )
        )
        assert opportunity is not None
        assert opportunity.buyer_name == "West Yorkshire Police"
        assert opportunity.estimated_total_contract_value == 1400000
        assert opportunity.probability == 0.42
        assert opportunity.weighted_value == 588000

        buyer_field = db.scalar(
            select(FieldIntelligence).where(
                FieldIntelligence.entity_id == opportunity.id,
                FieldIntelligence.field_name == "buyer_name",
            )
        )
        assert buyer_field is not None
        assert buyer_field.value_type == "user_provided"
        assert buyer_field.field_value == "West Yorkshire Police"

        value_field = db.scalar(
            select(FieldIntelligence).where(
                FieldIntelligence.entity_id == opportunity.id,
                FieldIntelligence.field_name == "estimated_total_contract_value",
            )
        )
        assert value_field is not None
        assert value_field.value_type == "estimated"
        assert value_field.field_value == 1400000

        deadline_field = db.scalar(
            select(FieldIntelligence).where(
                FieldIntelligence.entity_id == opportunity.id,
                FieldIntelligence.field_name == "submission_deadline",
            )
        )
        assert deadline_field is not None
        assert deadline_field.value_type == "unknown"
        assert "Confirm" in deadline_field.recommended_next_step

        run = db.scalar(select(EnrichmentRun))
        assert run is not None
        assert run.run_type == "bulk_opportunity_autofill"
        assert run.status == "completed"
        assert db.scalar(select(func.count(OpportunityEnrichment.id))) == 1


def test_autofill_opportunities_continues_when_one_record_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeOpenAIClient(
        [
            json.dumps(_internet_payload()),
            json.dumps(_commercial_payload()),
        ]
    )
    client, testing_session = _client_with_database(
        tmp_path,
        monkeypatch,
        fake_client,
    )

    with testing_session() as db:
        for index in range(2):
            db.add(
                Opportunity(
                    name=f"Incomplete opportunity {index + 1}",
                    buyer_name=f"Buyer {index + 1}",
                    sector="unknown",
                    region="unknown",
                    source_type="",
                    stage="Market signal",
                    owner="Sales Director",
                    estimated_annual_revenue=0,
                    estimated_total_contract_value=0,
                    estimated_gross_margin=0,
                    margin_percentage=0,
                    probability=0,
                    weighted_value=0,
                    forecast_start_month=None,
                    self_delivery_fit="unknown",
                    risk_rating="unknown",
                    strategic_fit_score=0,
                    bid_no_bid_recommendation="review_required",
                    recommended_action="",
                )
            )
        db.commit()

    response = client.post(
        "/api/intelligence/autofill-opportunities",
        json={"only_incomplete": True, "limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["records_scanned"] == 2
    assert body["records_enriched"] == 1
    assert body["records_failed"] == 1
    assert body["results"][0]["status"] == "enriched"
    assert body["results"][1]["status"] == "failed"
    assert "preserved" in body["results"][1]["confidence_warnings"][0]

    with testing_session() as db:
        statuses = [run.status for run in db.scalars(select(EnrichmentRun).order_by(EnrichmentRun.id))]
        assert statuses == ["completed", "failed"]
