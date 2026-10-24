from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, create_database_engine, get_db
from app.main import create_app
from app.models import EnrichmentRun, FieldIntelligence, Opportunity, OpportunityEnrichment


def _sample_opportunity() -> Opportunity:
    return Opportunity(
        name="AI-enriched fire and security opportunity",
        buyer_name="Example Metropolitan Borough Council",
        sector="Local Authority",
        region="North West",
        source_type="internet_research",
        stage="Market signal",
        owner="Commercial Intelligence",
        estimated_annual_revenue=350000,
        estimated_total_contract_value=1400000,
        estimated_gross_margin=420000,
        margin_percentage=30,
        probability=0.55,
        weighted_value=770000,
        self_delivery_fit="High",
        risk_rating="Amber",
        strategic_fit_score=78,
        bid_no_bid_recommendation="Watch",
        recommended_action="Confirm tender route and current incumbent.",
    )


def _client_with_enrichment_data(
    tmp_path: Path,
) -> tuple[TestClient, sessionmaker[Session], int, int]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'enrichment.db'}")
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with testing_session() as db:
        opportunity = _sample_opportunity()
        db.add(opportunity)
        db.flush()

        run = EnrichmentRun(
            run_type="opportunity_pack",
            status="completed",
            user_query="Local authority fire alarm and CCTV maintenance tender",
            opportunity_id=opportunity.id,
            model_used="gpt-5.5",
            search_performed=True,
            sources_checked=[
                {
                    "title": "Example notice",
                    "url": "https://example.invalid/find-tender/notice",
                }
            ],
            records_created=1,
            records_updated=3,
        )
        db.add(run)
        db.flush()

        db.add_all(
            [
                FieldIntelligence(
                    entity_type="opportunity",
                    entity_id=opportunity.id,
                    field_name="estimated_total_contract_value",
                    field_value=1400000,
                    value_type="estimated",
                    confidence_score=0.72,
                    rationale="Estimated from comparable council estate servicing values.",
                    source_urls=["https://example.invalid/find-tender/notice"],
                    source_titles=["Example notice"],
                    needs_user_confirmation=True,
                ),
                FieldIntelligence(
                    entity_type="opportunity",
                    entity_id=opportunity.id,
                    field_name="buyer_name",
                    field_value="Example Metropolitan Borough Council",
                    value_type="known",
                    confidence_score=0.95,
                    rationale="Buyer name came from the source notice.",
                    source_urls=["https://example.invalid/find-tender/notice"],
                    source_titles=["Example notice"],
                    needs_user_confirmation=False,
                ),
                OpportunityEnrichment(
                    opportunity_id=opportunity.id,
                    enrichment_run_id=run.id,
                    buyer_summary="Public-sector estate buyer with compliance-led drivers.",
                    opportunity_summary="Likely bundled fire and security maintenance opportunity.",
                    likely_scope="Fire alarms, emergency lighting, CCTV and access control.",
                    estimated_contract_value_rationale=(
                        "Estimate based on multi-site local authority estates and comparable notices."
                    ),
                    likely_buyer_drivers=[
                        "Statutory compliance assurance",
                        "Responsive maintenance performance",
                    ],
                    compliance_drivers=["Fire safety compliance", "Procurement transparency"],
                    competitor_assessment="Incumbent supplier not known from public sources.",
                    commercial_assessment="Attractive if margin and self-delivery assumptions hold.",
                    mobilisation_assessment="Needs asset list and incumbent demobilisation plan.",
                    self_delivery_assessment="Strong fit for Mitie Fire & Security self-delivery.",
                    finance_assessment="Requires confirmation of annual run-rate and mobilisation costs.",
                    executive_recommendation="Pursue discovery and prepare bid/no-bid pack.",
                    unknowns=["Incumbent supplier", "Asset volumes", "Precise tender date"],
                    recommended_next_steps=[
                        "Validate asset base",
                        "Identify procurement contact",
                    ],
                    overall_confidence=0.74,
                ),
            ]
        )
        db.commit()
        opportunity_id = opportunity.id
        run_id = run.id

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session, opportunity_id, run_id


def test_enrichment_records_link_to_existing_opportunity(tmp_path: Path) -> None:
    _client, testing_session, opportunity_id, run_id = _client_with_enrichment_data(
        tmp_path,
    )

    with testing_session() as db:
        opportunity = db.get(Opportunity, opportunity_id)
        run = db.get(EnrichmentRun, run_id)
        field_values = list(
            db.scalars(
                select(FieldIntelligence).where(
                    FieldIntelligence.entity_type == "opportunity",
                    FieldIntelligence.entity_id == opportunity_id,
                )
            )
        )

        assert opportunity is not None
        assert run is not None
        assert run.opportunity_id == opportunity.id
        assert run.opportunity == opportunity
        assert len(opportunity.opportunity_enrichments) == 1
        assert opportunity.opportunity_enrichments[0].enrichment_run == run
        assert {field.value_type for field in field_values} == {"estimated", "known"}
        assert field_values[0].source_urls


def test_enrichment_api_retrieves_runs_and_field_intelligence(tmp_path: Path) -> None:
    client, _testing_session, opportunity_id, run_id = _client_with_enrichment_data(
        tmp_path,
    )

    run_response = client.get(f"/api/enrichment/runs/{run_id}")
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["run_type"] == "opportunity_pack"
    assert run_body["status"] == "completed"
    assert run_body["search_performed"] is True
    assert run_body["sources_checked"][0]["title"] == "Example notice"

    runs_response = client.get(f"/api/enrichment/runs?opportunity_id={opportunity_id}")
    assert runs_response.status_code == 200
    assert len(runs_response.json()) == 1

    enrichment_response = client.get(f"/api/enrichment/opportunities/{opportunity_id}")
    assert enrichment_response.status_code == 200
    enrichment_body = enrichment_response.json()[0]
    assert enrichment_body["overall_confidence"] == 0.74
    assert "Incumbent supplier" in enrichment_body["unknowns"]
    assert enrichment_body["recommended_next_steps"] == [
        "Validate asset base",
        "Identify procurement contact",
    ]

    field_response = client.get(
        "/api/enrichment/field-intelligence",
        params={"entity_type": "opportunity", "entity_id": opportunity_id},
    )
    assert field_response.status_code == 200
    fields = field_response.json()
    assert {field["value_type"] for field in fields} == {"estimated", "known"}
    estimated_value = next(
        field
        for field in fields
        if field["field_name"] == "estimated_total_contract_value"
    )
    assert estimated_value["field_value"] == 1400000
    assert estimated_value["needs_user_confirmation"] is True
    assert estimated_value["confidence_score"] == 0.72


def test_field_intelligence_can_represent_unknown_values(tmp_path: Path) -> None:
    client, testing_session, opportunity_id, _run_id = _client_with_enrichment_data(
        tmp_path,
    )

    with testing_session() as db:
        db.add(
            FieldIntelligence(
                entity_type="opportunity",
                entity_id=opportunity_id,
                field_name="incumbent_supplier",
                field_value=None,
                value_type="unknown",
                confidence_score=0,
                rationale="No incumbent supplier was visible in public source material.",
                source_urls=[],
                source_titles=[],
                needs_user_confirmation=True,
            )
        )
        db.commit()

    response = client.get(
        "/api/enrichment/field-intelligence",
        params={
            "entity_type": "opportunity",
            "entity_id": opportunity_id,
            "field_name": "incumbent_supplier",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["value_type"] == "unknown"
    assert body[0]["field_value"] is None
    assert body[0]["needs_user_confirmation"] is True
    assert "No incumbent supplier" in body[0]["rationale"]
