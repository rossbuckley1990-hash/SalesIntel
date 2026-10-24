from datetime import date

from app.intelligence import (
    BidRecommendation,
    OpportunityIntelligenceInput,
    calculate_opportunity_intelligence,
)
from app.models import Opportunity
from app.services.opportunity_intelligence import apply_intelligence_to_opportunity


def _opportunity_input(**overrides: object) -> OpportunityIntelligenceInput:
    values = {
        "estimated_total_contract_value": 300_000,
        "margin_percentage": 28,
        "probability": 0.5,
        "submission_deadline": None,
        "stage": "Pre-tender",
        "self_delivery_fit": "Moderate",
        "risk_rating": "Low",
        "strategic_fit_score": 70,
    }
    values.update(overrides)
    return OpportunityIntelligenceInput(**values)


def test_weighted_value_and_strategic_must_win() -> None:
    result = calculate_opportunity_intelligence(
        _opportunity_input(
            estimated_total_contract_value=1_200_000,
            probability=0.7,
        ),
        today=date(2026, 6, 29),
    )

    assert result.weighted_pipeline_value == 840_000
    assert result.strategic_must_win is True


def test_probability_can_be_supplied_as_percentage() -> None:
    result = calculate_opportunity_intelligence(
        _opportunity_input(
            estimated_total_contract_value=1_200_000,
            probability=70,
        ),
        today=date(2026, 6, 29),
    )

    assert result.weighted_pipeline_value == 840_000
    assert result.strategic_must_win is True


def test_deadline_warning_only_applies_to_live_bid_stages() -> None:
    today = date(2026, 6, 29)
    live_result = calculate_opportunity_intelligence(
        _opportunity_input(
            submission_deadline=date(2026, 7, 10),
            stage="ITT live",
        ),
        today=today,
    )
    early_stage_result = calculate_opportunity_intelligence(
        _opportunity_input(
            submission_deadline=date(2026, 7, 10),
            stage="Pre-tender",
        ),
        today=today,
    )

    assert live_result.deadline_warning is True
    assert early_stage_result.deadline_warning is False


def test_margin_warning_boundary() -> None:
    warning_result = calculate_opportunity_intelligence(
        _opportunity_input(margin_percentage=24.9),
        today=date(2026, 6, 29),
    )
    clear_result = calculate_opportunity_intelligence(
        _opportunity_input(margin_percentage=25),
        today=date(2026, 6, 29),
    )

    assert warning_result.margin_warning is True
    assert clear_result.margin_warning is False


def test_self_delivery_capture_flag() -> None:
    result = calculate_opportunity_intelligence(
        _opportunity_input(
            estimated_total_contract_value=300_000,
            self_delivery_fit="High",
        ),
        today=date(2026, 6, 29),
    )

    assert result.self_delivery_capture is True


def test_executive_escalation_for_red_risk_high_value() -> None:
    result = calculate_opportunity_intelligence(
        _opportunity_input(
            estimated_total_contract_value=600_000,
            risk_rating="Red",
        ),
        today=date(2026, 6, 29),
    )

    assert result.risk_rating == "Red"
    assert result.executive_escalation is True


def test_pursue_recommendation_for_strategic_fit_and_margin() -> None:
    result = calculate_opportunity_intelligence(
        _opportunity_input(
            strategic_fit_score=85,
            margin_percentage=31,
        ),
        today=date(2026, 6, 29),
    )

    assert result.bid_no_bid_recommendation == BidRecommendation.PURSUE


def test_qualify_out_and_no_bid_recommendations() -> None:
    qualify_out_result = calculate_opportunity_intelligence(
        _opportunity_input(
            strategic_fit_score=44,
            margin_percentage=20,
        ),
        today=date(2026, 6, 29),
    )
    no_bid_result = calculate_opportunity_intelligence(
        _opportunity_input(margin_percentage=14),
        today=date(2026, 6, 29),
    )

    assert qualify_out_result.bid_no_bid_recommendation == BidRecommendation.QUALIFY_OUT
    assert no_bid_result.bid_no_bid_recommendation == BidRecommendation.NO_BID


def test_high_value_high_risk_recommends_executive_sponsor() -> None:
    result = calculate_opportunity_intelligence(
        _opportunity_input(
            estimated_total_contract_value=750_000,
            margin_percentage=28,
            risk_rating="High",
        ),
        today=date(2026, 6, 29),
    )

    assert (
        result.bid_no_bid_recommendation
        == BidRecommendation.PURSUE_WITH_EXECUTIVE_SPONSOR
    )
    assert "executive sponsor" in result.recommended_next_action


def test_existing_opportunity_record_can_be_enriched_with_calculated_fields() -> None:
    opportunity = Opportunity(
        name="Strategic fire alarm renewal",
        buyer_name="Example Housing Trust",
        sector="Housing",
        region="London",
        source_type="pipeline_upload",
        stage="ITT live",
        owner="Amira Shah",
        estimated_annual_revenue=400_000,
        estimated_total_contract_value=1_200_000,
        estimated_gross_margin=300_000,
        margin_percentage=25,
        probability=0.7,
        weighted_value=0,
        submission_deadline=date(2026, 7, 8),
        forecast_start_month="2026-09",
        self_delivery_fit="High",
        risk_rating="High",
        strategic_fit_score=82,
        bid_no_bid_recommendation="review_required",
        recommended_action="",
    )

    result = apply_intelligence_to_opportunity(
        opportunity,
        today=date(2026, 6, 29),
    )

    assert result.executive_escalation is True
    assert opportunity.weighted_value == 840_000
    assert opportunity.risk_rating == "Red"
    assert opportunity.bid_no_bid_recommendation == "Pursue with executive sponsor"
    assert "executive sponsor" in opportunity.recommended_action
