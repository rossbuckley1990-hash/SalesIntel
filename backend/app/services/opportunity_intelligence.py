from datetime import date

from app.intelligence import OpportunityIntelligenceInput, OpportunityIntelligenceResult
from app.intelligence import calculate_opportunity_intelligence
from app.models import Opportunity
from app.schemas.opportunity import OpportunityLatestAIAnalysis, OpportunityRead


def to_intelligence_input(opportunity: Opportunity) -> OpportunityIntelligenceInput:
    return OpportunityIntelligenceInput(
        estimated_total_contract_value=opportunity.estimated_total_contract_value,
        margin_percentage=opportunity.margin_percentage,
        probability=opportunity.probability,
        submission_deadline=opportunity.submission_deadline,
        stage=opportunity.stage,
        self_delivery_fit=opportunity.self_delivery_fit,
        risk_rating=opportunity.risk_rating,
        strategic_fit_score=opportunity.strategic_fit_score,
    )


def calculate_for_opportunity(
    opportunity: Opportunity,
    *,
    today: date | None = None,
) -> OpportunityIntelligenceResult:
    return calculate_opportunity_intelligence(
        to_intelligence_input(opportunity),
        today=today,
    )


def enrich_opportunity(
    opportunity: Opportunity,
    *,
    today: date | None = None,
) -> OpportunityRead:
    intelligence = calculate_for_opportunity(opportunity, today=today)
    return OpportunityRead.model_validate(opportunity).model_copy(
        update={
            **_calculated_response_fields(intelligence),
            "latest_ai_analysis": _latest_ai_analysis(opportunity),
        },
    )


def enrich_opportunities(
    opportunities: list[Opportunity],
    *,
    today: date | None = None,
) -> list[OpportunityRead]:
    return [enrich_opportunity(opportunity, today=today) for opportunity in opportunities]


def apply_intelligence_to_opportunity(
    opportunity: Opportunity,
    *,
    today: date | None = None,
) -> OpportunityIntelligenceResult:
    intelligence = calculate_for_opportunity(opportunity, today=today)
    opportunity.weighted_value = intelligence.weighted_pipeline_value
    opportunity.risk_rating = intelligence.risk_rating
    opportunity.bid_no_bid_recommendation = intelligence.bid_no_bid_recommendation.value
    opportunity.recommended_action = intelligence.recommended_next_action
    return intelligence


def _calculated_response_fields(
    intelligence: OpportunityIntelligenceResult,
) -> dict[str, float | str | bool]:
    return {
        "weighted_pipeline_value": intelligence.weighted_pipeline_value,
        "strategic_must_win": intelligence.strategic_must_win,
        "calculated_risk_rating": intelligence.risk_rating,
        "margin_warning": intelligence.margin_warning,
        "deadline_warning": intelligence.deadline_warning,
        "self_delivery_capture": intelligence.self_delivery_capture,
        "executive_escalation": intelligence.executive_escalation,
        "calculated_bid_no_bid_recommendation": (
            intelligence.bid_no_bid_recommendation.value
        ),
        "priority_score": intelligence.priority_score,
        "calculated_recommended_action": intelligence.recommended_next_action,
    }


def _latest_ai_analysis(
    opportunity: Opportunity,
) -> OpportunityLatestAIAnalysis | None:
    if not opportunity.ai_analyses:
        return None

    latest = max(
        opportunity.ai_analyses,
        key=lambda analysis: (analysis.created_at, analysis.id),
    )
    return OpportunityLatestAIAnalysis.model_validate(latest)
