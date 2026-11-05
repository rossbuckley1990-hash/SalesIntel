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
from app.schemas.intelligence import (
    OpportunityAnalysisRequest,
    OpportunityAnalysisResponse,
    OpportunityAnalysisResult,
)


OPPORTUNITY_ANALYSIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "opportunity_summary",
        "commercial_assessment",
        "risk_level",
        "key_risks",
        "recommended_actions",
        "bid_no_bid_recommendation",
        "confidence_score",
        "source_notes",
    ],
    "properties": {
        "opportunity_summary": concise_string(360),
        "commercial_assessment": concise_string(420),
        "risk_level": {
            "type": "string",
            "enum": ["Low", "Medium", "High", "Red", "Amber", "Green", "Unknown"],
        },
        "key_risks": concise_string_array(max_items=6, max_length=180),
        "recommended_actions": concise_string_array(max_items=6, max_length=180),
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
        "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
        "source_notes": concise_string_array(max_items=6, max_length=180),
    },
}


def analyse_opportunity_with_openai(
    request: OpportunityAnalysisRequest,
    *,
    client: Any | None = None,
    settings: Settings | None = None,
) -> OpportunityAnalysisResponse:
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
                    "content": json.dumps(
                        request.model_dump(mode="json"),
                        sort_keys=True,
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "misi_opportunity_analysis",
                    "schema": OPPORTUNITY_ANALYSIS_JSON_SCHEMA,
                    "strict": True,
                },
            },
            temperature=0.2,
        )
    except OpenAIError as exc:
        raise OpenAIRequestError("OpenAI analysis request failed.") from exc

    content = _extract_message_content(response)
    try:
        raw_payload = json.loads(content)
        analysis = OpportunityAnalysisResult.model_validate(raw_payload)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise InvalidOpenAIJSONError(
            "OpenAI returned invalid structured JSON for opportunity analysis."
        ) from exc

    return OpportunityAnalysisResponse(
        **analysis.model_dump(),
        model=active_settings.openai_model,
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


def _system_prompt() -> str:
    return build_commercial_system_prompt(
        role=(
            "You are SalesIntel, a senior commercial intelligence analyst for Mitie "
            "Fire & Security."
        ),
        task=(
            "Assess the supplied opportunity fields for bid/no-bid decision "
            "support and executive action."
        ),
        output_contract="Return only structured JSON matching the provided schema.",
        extra_rules=[
            "Ground the analysis only in the supplied opportunity fields.",
            "Source notes must distinguish supplied facts from inferred or estimated judgement.",
            "Recommended actions must be specific next best actions, not generic follow-up.",
        ],
    )
