from datetime import date

from app.schemas import (
    BuyerProfileCreate,
    CompetitorProfileCreate,
    ExecutiveActionCreate,
    FinanceForecastCreate,
    FieldIntelligenceCreate,
    MarketSignalCreate,
    OpportunityCreate,
    OpportunityEnrichmentCreate,
    EnrichmentRunCreate,
)


def test_core_schemas_accept_misi_payloads() -> None:
    opportunity = OpportunityCreate(
        name="Fire alarm maintenance renewal",
        buyer_name="Example Borough Council",
        sector="Local Government",
        region="London",
        source_type="pipeline_upload",
        stage="Qualified",
        owner="Sales Lead",
        estimated_annual_revenue=420000,
        estimated_total_contract_value=1260000,
        estimated_gross_margin=252000,
        margin_percentage=20,
        probability=0.62,
        weighted_value=781200,
        submission_deadline=date(2026, 7, 15),
        forecast_start_month="2026-09",
        self_delivery_fit="strong",
        risk_rating="medium",
        strategic_fit_score=82,
        bid_no_bid_recommendation="bid",
        recommended_action="Prepare bid/no-bid pack.",
    )
    market_signal = MarketSignalCreate(
        title="Fire safety servicing framework",
        buyer_name="Example Borough Council",
        sector="Local Government",
        region="London",
        estimated_value=600000,
        expected_tender_date=date(2026, 7, 1),
        source_type="synthetic_tender_signal",
        source_url="https://example.invalid/tenders/fire-safety-framework",
        confidence_score=0.78,
        suggested_action="Track tender publication.",
        likely_mitie_fit="High",
        potential_disciplines=["Fire Alarms", "Emergency Lighting"],
        ai_rationale="Strong fit for Mitie Fire & Security self-delivery.",
    )
    buyer = BuyerProfileCreate(
        buyer_name="Example Borough Council",
        sector="Local Government",
        region="London",
        estate_size="120 public buildings",
        procurement_drivers=["Compliance assurance"],
        pain_points=["Ageing fire systems"],
        decision_criteria=["Mobilisation confidence"],
        relationship_status="known_account",
        next_best_action="Confirm procurement timeline.",
    )
    competitor = CompetitorProfileCreate(
        name="Incumbent Fire Services Ltd",
        sectors=["Local Government"],
        strengths=["Existing relationship"],
        weaknesses=["Slow reporting"],
        pricing_behaviour="Defensive discounting.",
        threat_level="medium",
        counter_strategy="Lead with reporting and self-delivery coverage.",
    )
    action = ExecutiveActionCreate(
        priority="high",
        category="Bid Readiness",
        owner="Sales Director",
        due_date=date(2026, 7, 8),
        related_opportunity_id=1,
        commercial_value=1260000,
        reason="High-fit renewal opportunity.",
        recommended_action="Schedule bid/no-bid review.",
        status="open",
    )
    forecast = FinanceForecastCreate(
        opportunity_id=1,
        forecast_category="best_case",
        start_month="2026-09",
        revenue_to_year_end=140000,
        estimated_margin=28000,
        margin_percentage=20,
        probability_weighting=0.62,
        risk_adjustment=0.1,
        notes="Assumes September mobilisation.",
    )
    enrichment_run = EnrichmentRunCreate(
        run_type="opportunity_pack",
        status="completed",
        user_query="Fire alarm maintenance opportunity for Example Borough Council",
        opportunity_id=1,
        model_used="gpt-5.5",
        search_performed=True,
        sources_checked=[
            {
                "title": "Example tender notice",
                "url": "https://example.invalid/tenders/fire-safety-framework",
            }
        ],
        records_created=1,
        records_updated=2,
    )
    field_intelligence = FieldIntelligenceCreate(
        entity_type="opportunity",
        entity_id=1,
        field_name="estimated_total_contract_value",
        field_value=1260000,
        value_type="estimated",
        confidence_score=0.72,
        rationale="Estimated from estate size and comparable fire servicing contracts.",
        source_urls=["https://example.invalid/tenders/fire-safety-framework"],
        source_titles=["Example tender notice"],
        needs_user_confirmation=True,
    )
    opportunity_enrichment = OpportunityEnrichmentCreate(
        opportunity_id=1,
        enrichment_run_id=1,
        buyer_summary="Local authority buyer with compliance-led estate requirements.",
        opportunity_summary="Likely fire and security maintenance renewal.",
        likely_scope="Fire alarms, emergency lighting, CCTV and access control.",
        estimated_contract_value_rationale="Comparable local authority contracts indicate seven-figure TCV.",
        likely_buyer_drivers=["Compliance assurance", "Responsive maintenance"],
        compliance_drivers=["Fire Safety Order", "Estate statutory compliance"],
        competitor_assessment="Regional incumbent threat likely but not confirmed.",
        commercial_assessment="Attractive if self-delivery coverage is validated.",
        mobilisation_assessment="Mobilisation plan requires asset list confirmation.",
        self_delivery_assessment="Strong fit for Mitie Fire & Security.",
        finance_assessment="Needs margin confirmation before bid commitment.",
        executive_recommendation="Pursue with early executive qualification.",
        unknowns=["Incumbent supplier", "Current asset volumes"],
        recommended_next_steps=["Confirm procurement route", "Request asset schedule"],
        overall_confidence=0.74,
    )

    assert opportunity.bid_no_bid_recommendation == "bid"
    assert market_signal.confidence_score == 0.78
    assert buyer.procurement_drivers == ["Compliance assurance"]
    assert competitor.threat_level == "medium"
    assert action.status == "open"
    assert forecast.start_month == "2026-09"
    assert enrichment_run.search_performed is True
    assert field_intelligence.value_type == "estimated"
    assert field_intelligence.needs_user_confirmation is True
    assert opportunity_enrichment.unknowns == ["Incumbent supplier", "Current asset volumes"]
