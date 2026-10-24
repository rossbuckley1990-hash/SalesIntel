import json
from typing import Any

from openai import OpenAIError
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.intelligence.openai_client import (
    InvalidOpenAIJSONError,
    OpenAIRequestError,
    get_openai_client,
)
from app.intelligence.prompt_contract import (
    build_commercial_system_prompt,
    concise_string,
    concise_string_array,
)
from app.models import Opportunity
from app.schemas import OpportunityAIAnalysisResult


OPPORTUNITY_AI_ANALYSIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "strategic_fit_score",
        "win_probability",
        "risk_rating",
        "bid_no_bid_recommendation",
        "likely_buyer_drivers",
        "competitor_threat",
        "margin_commentary",
        "mobilisation_risks",
        "commercial_risks",
        "self_delivery_assessment",
        "recommended_action",
        "executive_summary",
    ],
    "properties": {
        "strategic_fit_score": {"type": "number", "minimum": 0, "maximum": 100},
        "win_probability": {"type": "number", "minimum": 0, "maximum": 1},
        "risk_rating": {"type": "string", "enum": ["Green", "Amber", "Red"]},
        "bid_no_bid_recommendation": {
            "type": "string",
            "enum": [
                "Pursue",
                "Pursue with executive sponsor",
                "Watch",
                "Qualify out",
                "No bid",
            ],
        },
        "likely_buyer_drivers": concise_string_array(max_items=5, max_length=140),
        "competitor_threat": {"type": "string", "enum": ["Low", "Medium", "High"]},
        "margin_commentary": concise_string(280),
        "mobilisation_risks": concise_string_array(max_items=5, max_length=160),
        "commercial_risks": concise_string_array(max_items=5, max_length=160),
        "self_delivery_assessment": concise_string(320),
        "recommended_action": concise_string(260),
        "executive_summary": concise_string(420),
    },
}


def analyse_opportunity_record_with_openai(
    opportunity: Opportunity,
    *,
    client: Any | None = None,
    settings: Settings | None = None,
) -> OpportunityAIAnalysisResult:
    active_settings = settings or get_settings()
    openai_client = client or get_openai_client(active_settings)

    try:
        response = openai_client.chat.completions.create(
            model=active_settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": _system_prompt(),
                },
                {
                    "role": "user",
                    "content": _opportunity_prompt(opportunity),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "misi_opportunity_ai_analysis",
                    "schema": OPPORTUNITY_AI_ANALYSIS_JSON_SCHEMA,
                    "strict": True,
                },
            },
            temperature=0.2,
        )
    except OpenAIError as exc:
        raise OpenAIRequestError("OpenAI opportunity analysis request failed.") from exc

    content = _extract_message_content(response)
    try:
        payload = json.loads(content)
        return OpportunityAIAnalysisResult.model_validate(payload)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise InvalidOpenAIJSONError(
            "OpenAI returned invalid structured JSON for opportunity analysis."
        ) from exc


def _system_prompt() -> str:
    return build_commercial_system_prompt(
        role=(
            "You are MiSi, a senior commercial intelligence analyst for Mitie "
            "Fire & Security."
        ),
        task=(
            "Convert an existing opportunity record into a board-ready "
            "commercial intelligence assessment."
        ),
        output_contract="Return only JSON matching the requested schema.",
        extra_rules=[
            "Use senior commercial language, not generic AI prose.",
            "Margin commentary must say whether margin protection is required.",
            "Mobilisation risks must identify asset data risk, access risk or delivery capacity risk when evidenced.",
            "Recommended action must be a single next best action for Mitie.",
            "If buyer drivers, competitor threat or risks are not evidenced, state that clearly in the relevant field.",
        ],
    )


def _opportunity_prompt(opportunity: Opportunity) -> str:
    opportunity_payload = {
        "opportunity_id": opportunity.id,
        "name": opportunity.name,
        "buyer_name": opportunity.buyer_name,
        "sector": opportunity.sector,
        "region": opportunity.region,
        "source_type": opportunity.source_type,
        "stage": opportunity.stage,
        "owner": opportunity.owner,
        "estimated_annual_revenue": opportunity.estimated_annual_revenue,
        "estimated_total_contract_value": opportunity.estimated_total_contract_value,
        "estimated_gross_margin": opportunity.estimated_gross_margin,
        "margin_percentage": opportunity.margin_percentage,
        "probability": opportunity.probability,
        "weighted_value": opportunity.weighted_value,
        "submission_deadline": (
            opportunity.submission_deadline.isoformat()
            if opportunity.submission_deadline
            else None
        ),
        "forecast_start_month": opportunity.forecast_start_month,
        "self_delivery_fit": opportunity.self_delivery_fit,
        "current_risk_rating": opportunity.risk_rating,
        "current_strategic_fit_score": opportunity.strategic_fit_score,
        "current_bid_no_bid_recommendation": opportunity.bid_no_bid_recommendation,
        "current_recommended_action": opportunity.recommended_action,
    }
    return (
        "Analyse this MiSi opportunity and return the required structured JSON. "
        "Use only this supplied opportunity data. If buyer drivers, competitor threat, "
        "mobilisation risks or commercial risks are not evidenced, say what is unknown. "
        "The output should be board-ready, concise and action-oriented. Explicitly "
        "separate known facts from inferred or estimated judgement.\n\n"
        f"{json.dumps(opportunity_payload, sort_keys=True)}"
    )


def _extract_message_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise InvalidOpenAIJSONError(
            "OpenAI response did not contain a message payload."
        ) from exc

    if not isinstance(content, str) or not content.strip():
        raise InvalidOpenAIJSONError("OpenAI response content was empty.")
    return content
