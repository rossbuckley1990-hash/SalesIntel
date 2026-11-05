import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

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
from app.schemas import InternetIntelligenceRequest, InternetIntelligenceResult


INTERNET_INTELLIGENCE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "intelligence_type",
        "query",
        "headline",
        "summary",
        "findings",
        "source_urls",
        "risk_warnings",
        "next_best_actions",
        "limitations",
    ],
    "properties": {
        "intelligence_type": {
            "type": "string",
            "enum": [
                "market_radar",
                "competitor_intelligence",
                "buyer_intelligence",
                "opportunity_intelligence",
                "tender_intelligence",
                "pipeline_forecast",
                "self_delivery",
            ],
        },
        "query": {"type": "string"},
        "headline": concise_string(180),
        "summary": concise_string(420),
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "title",
                    "finding",
                    "so_what",
                    "recommended_action",
                    "confidence_score",
                    "source_urls",
                ],
                "properties": {
                    "title": concise_string(140),
                    "finding": concise_string(260),
                    "so_what": concise_string(220),
                    "recommended_action": concise_string(200),
                    "confidence_score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "source_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "source_urls": {"type": "array", "items": {"type": "string"}},
        "risk_warnings": concise_string_array(max_items=6, max_length=180),
        "next_best_actions": concise_string_array(max_items=6, max_length=180),
        "limitations": concise_string_array(max_items=6, max_length=180),
    },
}


def research_internet_with_openai(
    request: InternetIntelligenceRequest,
    *,
    client: Any | None = None,
    settings: Settings | None = None,
) -> InternetIntelligenceResult:
    active_settings = settings or get_settings()
    openai_client = client or get_openai_client(active_settings)

    try:
        response = openai_client.responses.create(
            model=active_settings.openai_model,
            instructions=_system_prompt(),
            input=json.dumps(request.model_dump(exclude_none=True), sort_keys=True),
            tools=[{"type": "web_search", "search_context_size": "low"}],
            reasoning={"effort": "low"},
            text={
                "format": {
                    "type": "json_schema",
                    "name": "misi_internet_intelligence",
                    "schema": INTERNET_INTELLIGENCE_JSON_SCHEMA,
                    "strict": True,
                }
            },
            store=False,
            max_output_tokens=4000,
            timeout=active_settings.openai_request_timeout_seconds,
        )
    except OpenAIError as exc:
        raise OpenAIRequestError("OpenAI internet intelligence request failed.") from exc

    content = _extract_response_text(response)
    try:
        raw_payload = json.loads(content)
        result = InternetIntelligenceResult.model_validate(raw_payload)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise InvalidOpenAIJSONError(
            "OpenAI returned invalid structured JSON for internet intelligence."
        ) from exc

    discovered_urls = _extract_annotation_urls(response)
    if discovered_urls:
        result = result.model_copy(
            update={
                "source_urls": _merge_unique_urls(result.source_urls, discovered_urls),
            }
        )
    return result


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            text = getattr(content_item, "text", None)
            if isinstance(text, str) and text.strip():
                return text
    raise InvalidOpenAIJSONError("OpenAI response content was empty.")


def _extract_annotation_urls(response: Any) -> list[str]:
    urls: list[str] = []
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            for annotation in getattr(content_item, "annotations", []) or []:
                url = getattr(annotation, "url", None)
                if isinstance(url, str) and url.strip():
                    urls.append(url)
    return urls


def _merge_unique_urls(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for url in [*primary, *secondary]:
        normalised = url.strip()
        if normalised and normalised not in seen:
            seen.add(normalised)
            merged.append(normalised)
    return merged[:12]


def _system_prompt() -> str:
    today = datetime.now(ZoneInfo("Europe/London")).date().isoformat()
    return build_commercial_system_prompt(
        role=(
            "You are SalesIntel, an internet intelligence researcher for Mitie Fire "
            "& Security."
        ),
        task=(
            "Use web search to find current, source-attributed public information "
            "relevant to UK Fire & Security sales."
        ),
        output_contract="Return only JSON matching the schema.",
        extra_rules=[
            f"The current UK date is {today}. Compare deadlines with this date.",
            "Do not claim to have searched private systems.",
            "Every finding must include the commercial implication and the next action.",
            "Return up to three concise findings. Return an empty findings array if no relevant, adequately evidenced findings are found; explain the limitation and next search action.",
            "For tender and opportunity discovery, use a primary procurement notice where available and check its latest linked notices or amendments. Include a source URL for each finding.",
            "State the buyer, procurement status and submission deadline where evidenced. Distinguish open tenders, preliminary engagement, future pipeline, awarded contracts and closed or expired notices. Never describe an award, payment or expired notice as an open bid.",
            "If the current status or deadline cannot be verified, state that it is unknown and recommend checking it; do not present the opportunity as open.",
            "Report contract value only when the source supports it, describing the amount as a total, annual value or framework ceiling as appropriate. Do not invent revenue, margin, win probability or available bid value; mark these unknown when unsupported.",
            "Keep each finding, so_what and recommended_action field under 40 words.",
            "Use no more than six total source URLs.",
            "Focus on market radar, tender intelligence, buyer intelligence, competitor intelligence, opportunity intelligence, self-delivery routing and pipeline forecast implications.",
            "If the web evidence does not prove buyer intent, say so as a limitation and recommend source confirmation.",
        ],
    )
