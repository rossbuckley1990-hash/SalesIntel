import json
from datetime import date
from typing import Any

from openai import OpenAIError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from app.schemas import ExecutiveSummaryResult
from app.services.dashboard import build_dashboard_summary
from app.services.finance_summary import build_finance_forecast_summary
from app.services.opportunity_intelligence import calculate_for_opportunity


EXECUTIVE_SUMMARY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "headline",
        "summary",
        "md_attention",
        "finance_attention",
        "sales_attention",
        "bid_team_attention",
        "risk_warnings",
        "next_best_actions",
    ],
    "properties": {
        "headline": concise_string(180),
        "summary": concise_string(520),
        "md_attention": concise_string_array(max_items=5, max_length=180),
        "finance_attention": concise_string_array(max_items=5, max_length=180),
        "sales_attention": concise_string_array(max_items=5, max_length=180),
        "bid_team_attention": concise_string_array(max_items=5, max_length=180),
        "risk_warnings": concise_string_array(max_items=6, max_length=180),
        "next_best_actions": concise_string_array(max_items=6, max_length=180),
    },
}


def generate_executive_summary_with_openai(
    db: Session,
    *,
    client: Any | None = None,
    settings: Settings | None = None,
    today: date | None = None,
) -> ExecutiveSummaryResult:
    active_settings = settings or get_settings()
    openai_client = client or get_openai_client(active_settings)
    context = build_executive_summary_context(db, today=today)

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
                    "content": json.dumps(context, sort_keys=True),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "misi_executive_summary",
                    "schema": EXECUTIVE_SUMMARY_JSON_SCHEMA,
                    "strict": True,
                },
            },
            temperature=0.2,
        )
    except OpenAIError as exc:
        raise OpenAIRequestError("OpenAI executive summary request failed.") from exc

    content = _extract_message_content(response)
    try:
        payload = json.loads(content)
        return ExecutiveSummaryResult.model_validate(payload)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise InvalidOpenAIJSONError(
            "OpenAI returned invalid structured JSON for executive summary."
        ) from exc


def build_executive_summary_context(
    db: Session,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    active_today = today or date.today()
    dashboard = build_dashboard_summary(db, today=active_today)
    finance = build_finance_forecast_summary(db, as_of=active_today)
    opportunities = list(db.scalars(select(Opportunity).order_by(Opportunity.id)))

    self_delivery_capture_opportunities = []
    red_risk_opportunities = []
    for opportunity in opportunities:
        if opportunity.stage in {"Won", "Lost", "Qualified out"}:
            continue
        intelligence = calculate_for_opportunity(opportunity, today=active_today)
        if intelligence.self_delivery_capture:
            self_delivery_capture_opportunities.append(
                {
                    "opportunity_id": opportunity.id,
                    "name": opportunity.name,
                    "buyer_name": opportunity.buyer_name,
                    "sector": opportunity.sector,
                    "value": opportunity.estimated_total_contract_value,
                    "self_delivery_fit": opportunity.self_delivery_fit,
                    "recommended_action": intelligence.recommended_next_action,
                }
            )
        if intelligence.risk_rating == "Red":
            red_risk_opportunities.append(
                {
                    "opportunity_id": opportunity.id,
                    "name": opportunity.name,
                    "buyer_name": opportunity.buyer_name,
                    "value": opportunity.estimated_total_contract_value,
                    "recommended_action": intelligence.recommended_next_action,
                }
            )

    self_delivery_value = sum(
        item["value"] for item in self_delivery_capture_opportunities
    )
    return {
        "source": "SalesIntel backend dashboard, finance forecast and opportunity records",
        "as_of": active_today.isoformat(),
        "instruction_coverage_required": [
            "pipeline position",
            "weighted pipeline",
            "margin position",
            "urgent deadlines",
            "strategic must-wins",
            "red risks",
            "finance attention items",
            "self-delivery capture opportunities",
            "recommended leadership actions this week",
        ],
        "dashboard": {
            "total_pipeline_value": dashboard.total_pipeline_value,
            "weighted_pipeline_value": dashboard.weighted_pipeline_value,
            "estimated_gross_margin": dashboard.estimated_gross_margin,
            "average_margin_percentage": dashboard.average_margin_percentage,
            "live_opportunity_count": dashboard.live_opportunity_count,
            "strategic_must_win_count": dashboard.strategic_must_win_count,
            "live_tender_count": dashboard.live_tender_count,
            "market_signal_count": dashboard.market_signal_count,
            "red_risk_count": dashboard.high_risk_count,
            "urgent_deadline_count": dashboard.urgent_deadline_count,
            "dashboard_summary_text": dashboard.executive_summary_text,
        },
        "top_opportunities": [
            {
                "opportunity_id": opportunity.id,
                "name": opportunity.name,
                "buyer_name": opportunity.buyer_name,
                "stage": opportunity.stage,
                "value": opportunity.estimated_total_contract_value,
                "weighted_pipeline_value": opportunity.weighted_pipeline_value,
                "margin_percentage": opportunity.margin_percentage,
                "risk_rating": opportunity.calculated_risk_rating,
                "priority_score": opportunity.priority_score,
                "recommended_action": opportunity.calculated_recommended_action,
            }
            for opportunity in dashboard.top_opportunities
        ],
        "executive_actions": [
            {
                "priority": action.priority,
                "category": action.category,
                "owner": action.owner,
                "due_date": action.due_date.isoformat() if action.due_date else None,
                "commercial_value": action.commercial_value,
                "reason": action.reason,
                "recommended_action": action.recommended_action,
                "status": action.status,
            }
            for action in dashboard.top_executive_actions
        ],
        "finance": {
            "financial_year": finance.financial_year,
            "secured_revenue": finance.secured_revenue,
            "secured_gross_margin": finance.secured_gross_margin,
            "secured_margin_percentage": finance.secured_margin_percentage,
            "open_weighted_revenue": finance.open_weighted_revenue,
            "open_weighted_margin": finance.open_weighted_margin,
            "risk_adjusted_revenue": finance.risk_adjusted_revenue,
            "risk_adjusted_margin": finance.risk_adjusted_margin,
            "forecast_to_financial_year_end": finance.forecast_to_financial_year_end,
            "forecast_margin_to_financial_year_end": (
                finance.forecast_margin_to_financial_year_end
            ),
            "finance_review_item_count": len(finance.finance_review_items),
            "margin_warning_count": len(finance.margin_warnings),
            "finance_attention_items": [
                {
                    "priority": item.priority,
                    "category": item.category,
                    "client": item.client,
                    "reason": item.reason,
                    "recommended_action": item.recommended_action,
                }
                for item in finance.finance_review_items[:6]
            ],
        },
        "risk": {
            "red_risk_count": len(red_risk_opportunities),
            "red_risk_opportunities": red_risk_opportunities[:6],
        },
        "self_delivery": {
            "capture_opportunity_count": len(self_delivery_capture_opportunities),
            "capture_opportunity_value": round(self_delivery_value, 2),
            "capture_opportunities": self_delivery_capture_opportunities[:6],
        },
    }


def _system_prompt() -> str:
    return build_commercial_system_prompt(
        role=(
            "You are SalesIntel, producing a concise board-level leadership briefing "
            "for Mitie Fire & Security."
        ),
        task=(
            "Turn the current dashboard, finance forecast and opportunity context "
            "into a leadership briefing for MD, FD and GSD review."
        ),
        output_contract="Return only JSON matching the schema.",
        extra_rules=[
            "Use crisp MD/FD/GSD language.",
            "The output must explicitly cover pipeline position, weighted pipeline, margin position, urgent deadlines, strategic must-wins, Red risks, finance attention items, self-delivery capture opportunities and leadership actions for this week.",
            "The headline must contain the commercial tension, not a generic status line.",
            "Each attention item must name the action, risk or owner group clearly.",
        ],
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
