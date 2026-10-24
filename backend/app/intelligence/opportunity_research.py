from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from openai import OpenAIError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.intelligence.internet_research import research_internet_with_openai
from app.intelligence.openai_client import (
    InvalidOpenAIJSONError,
    MissingOpenAIKeyError,
    OpenAIRequestError,
    get_openai_client,
)
from app.intelligence.prompt_contract import (
    build_commercial_system_prompt,
    concise_string,
    concise_string_array,
)
from app.models import (
    EnrichmentRun,
    ExecutiveAction,
    FieldIntelligence,
    FinanceForecast,
    Opportunity,
    OpportunityEnrichment,
)
from app.schemas import (
    AutofillOpportunitiesRequest,
    AutofillOpportunitiesResponse,
    AutofillOpportunityResult,
    ChatGPTAssistImportRequest,
    ChatGPTAssistPromptRequest,
    ChatGPTAssistPromptResponse,
    EnrichmentRunRead,
    ExecutiveActionRead,
    FieldIntelligenceRead,
    FinanceForecastRead,
    InternetIntelligenceRequest,
    InternetIntelligenceResult,
    OpportunityEnrichmentRead,
    ResearchOpportunityAIFieldBase,
    ResearchOpportunityAIResult,
    ResearchOpportunityDraft,
    ResearchOpportunityEnrichmentPack,
    ResearchOpportunityFieldIntelligence,
    ResearchOpportunityRequest,
    ResearchOpportunityResponse,
    ResearchOpportunitySource,
)
from app.services.opportunity_intelligence import enrich_opportunity


logger = logging.getLogger(__name__)


KEY_FIELD_NAMES = [
    "name",
    "buyer_name",
    "sector",
    "region",
    "source_type",
    "stage",
    "estimated_annual_revenue",
    "estimated_total_contract_value",
    "estimated_gross_margin",
    "margin_percentage",
    "probability",
    "weighted_value",
    "submission_deadline",
    "forecast_start_month",
    "self_delivery_fit",
    "risk_rating",
    "strategic_fit_score",
    "bid_no_bid_recommendation",
    "recommended_action",
]

AI_FIELD_VALUE_TYPES = [
    "known",
    "inferred",
    "estimated",
    "unknown",
]

BID_RECOMMENDATIONS = [
    "Pursue",
    "Pursue with executive sponsor",
    "Watch",
    "Qualify out",
    "No bid",
]

RISK_RATINGS = ["Green", "Amber", "Red"]
SELF_DELIVERY_FITS = ["High", "Medium", "Low", "Unknown"]
FINANCE_CATEGORIES = ["Committed", "Best case", "Likely", "Stretch", "At risk", "Excluded"]


def _ai_field_schema(value_json_type: str) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "value",
            "value_type",
            "confidence_score",
            "rationale",
            "source_urls",
        ],
        "properties": {
            "value": {"type": [value_json_type, "null"], "maxLength": 260}
            if value_json_type == "string"
            else {"type": [value_json_type, "null"]},
            "value_type": {"type": "string", "enum": AI_FIELD_VALUE_TYPES},
            "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": concise_string(260),
            "source_urls": {
                "type": "array",
                "maxItems": 6,
                "items": {"type": "string", "maxLength": 1200},
            },
        },
    }


AI_TEXT_FIELD_SCHEMA = _ai_field_schema("string")
AI_NUMERIC_FIELD_SCHEMA = _ai_field_schema("number")

AI_OPPORTUNITY_FIELD_SCHEMAS: dict[str, dict[str, Any]] = {
    "name": AI_TEXT_FIELD_SCHEMA,
    "buyer_name": AI_TEXT_FIELD_SCHEMA,
    "sector": AI_TEXT_FIELD_SCHEMA,
    "region": AI_TEXT_FIELD_SCHEMA,
    "source_type": AI_TEXT_FIELD_SCHEMA,
    "stage": AI_TEXT_FIELD_SCHEMA,
    "estimated_annual_revenue": AI_NUMERIC_FIELD_SCHEMA,
    "estimated_total_contract_value": AI_NUMERIC_FIELD_SCHEMA,
    "estimated_gross_margin": AI_NUMERIC_FIELD_SCHEMA,
    "margin_percentage": AI_NUMERIC_FIELD_SCHEMA,
    "probability": AI_NUMERIC_FIELD_SCHEMA,
    "submission_deadline": AI_TEXT_FIELD_SCHEMA,
    "forecast_start_month": AI_TEXT_FIELD_SCHEMA,
    "self_delivery_fit": AI_TEXT_FIELD_SCHEMA,
    "risk_rating": AI_TEXT_FIELD_SCHEMA,
    "strategic_fit_score": AI_NUMERIC_FIELD_SCHEMA,
    "bid_no_bid_recommendation": AI_TEXT_FIELD_SCHEMA,
    "recommended_action": AI_TEXT_FIELD_SCHEMA,
}

AI_OPPORTUNITY_FIELD_NAMES = list(AI_OPPORTUNITY_FIELD_SCHEMAS)

RESEARCH_OPPORTUNITY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["opportunity", "intelligence", "executive_action", "sources"],
    "properties": {
        "opportunity": {
            "type": "object",
            "additionalProperties": False,
            "required": AI_OPPORTUNITY_FIELD_NAMES,
            "properties": AI_OPPORTUNITY_FIELD_SCHEMAS,
        },
        "intelligence": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "buyer_summary",
                "opportunity_summary",
                "likely_scope",
                "likely_buyer_drivers",
                "compliance_drivers",
                "competitor_assessment",
                "commercial_assessment",
                "mobilisation_assessment",
                "self_delivery_assessment",
                "finance_assessment",
                "executive_recommendation",
                "unknowns",
                "recommended_next_steps",
                "overall_confidence",
            ],
            "properties": {
                "buyer_summary": concise_string(320),
                "opportunity_summary": concise_string(360),
                "likely_scope": concise_string_array(max_items=6, max_length=120),
                "likely_buyer_drivers": concise_string_array(max_items=5, max_length=140),
                "compliance_drivers": concise_string_array(max_items=5, max_length=140),
                "competitor_assessment": concise_string(360),
                "commercial_assessment": concise_string(380),
                "mobilisation_assessment": concise_string(360),
                "self_delivery_assessment": concise_string(360),
                "finance_assessment": concise_string(360),
                "executive_recommendation": concise_string(260),
                "unknowns": concise_string_array(max_items=6, max_length=160),
                "recommended_next_steps": concise_string_array(max_items=6, max_length=180),
                "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "executive_action": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "priority",
                "category",
                "owner",
                "due_date",
                "commercial_value",
                "reason",
                "recommended_action",
            ],
            "properties": {
                "priority": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High", "Critical"],
                },
                "category": concise_string(120),
                "owner": concise_string(120),
                "due_date": concise_string(40),
                "commercial_value": {"type": "number", "minimum": 0},
                "reason": concise_string(260),
                "recommended_action": concise_string(220),
            },
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "url", "source_type", "relevance"],
                "properties": {
                    "title": concise_string(180),
                    "url": concise_string(1200),
                    "source_type": concise_string(80),
                    "relevance": concise_string(240),
                },
            },
        },
    },
}


def research_opportunity_with_openai(
    request: ResearchOpportunityRequest,
    *,
    db: Session,
    client: Any | None = None,
    settings: Settings | None = None,
) -> ResearchOpportunityResponse:
    active_settings = settings or get_settings()
    run = EnrichmentRun(
        run_type="standing_start_opportunity_research",
        status="running",
        user_query=request.query,
        model_used=active_settings.openai_model,
        search_performed=False,
        sources_checked=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        openai_client = client or get_openai_client(active_settings)
        search_result = research_internet_with_openai(
            _internet_research_request(request),
            client=openai_client,
            settings=active_settings,
        )
        sources = _sources_from_search(search_result)
        run.search_performed = True
        run.sources_checked = [source.model_dump() for source in sources]
        db.commit()

        structured = _convert_search_to_record(
            request=request,
            search_result=search_result,
            client=openai_client,
            settings=active_settings,
        )
        sources = _merge_sources(sources, structured.sources)
        run.sources_checked = [source.model_dump() for source in sources]
        db.commit()

        draft_opportunity = _draft_from_ai_result(structured, request=request)
        draft_enrichment = _enrichment_from_ai_result(structured)
        draft_fields = _field_intelligence_from_ai_result(
            structured,
            sources=sources,
        )

        opportunity: Opportunity | None = None
        field_records: list[FieldIntelligence] = []
        enrichment_record: OpportunityEnrichment | None = None
        executive_action: ExecutiveAction | None = None
        finance_forecast: FinanceForecast | None = None
        created_opportunity = False
        records_created = 0
        records_updated = 0

        if request.create_opportunity:
            opportunity, created_opportunity = _create_or_update_opportunity(
                db,
                request=request,
                draft=draft_opportunity,
            )
            db.flush()
            records_created += 1 if created_opportunity else 0
            records_updated += 0 if created_opportunity else 1

            run.opportunity_id = opportunity.id
            field_records = _persist_field_intelligence(
                db,
                opportunity_id=opportunity.id,
                fields=draft_fields,
            )
            records_created += len(field_records)

            enrichment_record = _persist_opportunity_enrichment(
                db,
                opportunity_id=opportunity.id,
                run_id=run.id,
                enrichment=draft_enrichment,
            )
            records_created += 1

            finance_forecast = _persist_finance_forecast(
                db,
                opportunity_id=opportunity.id,
                draft=draft_opportunity,
                payload=_finance_forecast_payload_from_ai(structured, draft_opportunity),
            )
            if finance_forecast is not None:
                records_created += 1

            executive_action = _persist_executive_action(
                db,
                opportunity_id=opportunity.id,
                draft=draft_opportunity,
                payload=structured.executive_action.model_dump(),
            )
            if executive_action is not None:
                records_created += 1

        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.records_created = records_created
        run.records_updated = records_updated
        db.commit()
        db.refresh(run)

        if opportunity is not None:
            db.refresh(opportunity)
        for record in [*field_records, enrichment_record, executive_action, finance_forecast]:
            if record is not None:
                db.refresh(record)

        return ResearchOpportunityResponse(
            enrichment_run=EnrichmentRunRead.model_validate(run),
            created_opportunity=created_opportunity,
            opportunity=enrich_opportunity(opportunity) if opportunity else None,
            draft_opportunity=draft_opportunity,
            field_intelligence=[
                FieldIntelligenceRead.model_validate(record) for record in field_records
            ],
            draft_field_intelligence=draft_fields,
            opportunity_enrichment=(
                OpportunityEnrichmentRead.model_validate(enrichment_record)
                if enrichment_record
                else None
            ),
            draft_enrichment=draft_enrichment,
            executive_action=(
                ExecutiveActionRead.model_validate(executive_action)
                if executive_action
                else None
            ),
            finance_forecast=(
                FinanceForecastRead.model_validate(finance_forecast)
                if finance_forecast
                else None
            ),
            sources=sources,
            overall_confidence=draft_enrichment.overall_confidence,
        )
    except (MissingOpenAIKeyError, OpenAIRequestError, InvalidOpenAIJSONError) as exc:
        _mark_run_failed(db, run.id, _safe_error_message(exc))
        raise
    except Exception as exc:
        _mark_run_failed(db, run.id, "Opportunity research failed before completion.")
        raise OpenAIRequestError("Opportunity research failed before completion.") from exc


def build_chatgpt_assist_prompt(
    request: ChatGPTAssistPromptRequest,
) -> ChatGPTAssistPromptResponse:
    prompt = "\n".join(
        [
            "You are MiSi, a senior commercial intelligence analyst for Mitie Fire & Security.",
            "",
            "Task: research and build a UK Fire & Security commercial opportunity intelligence pack.",
            "Use ChatGPT web research if available. If you cannot verify a fact, label it inferred, estimated or unknown. Do not present guesses as known facts.",
            "",
            "Commercial question to answer:",
            "Where is the opportunity, what should Mitie pursue, what is it worth, what is the risk, and what action is needed now?",
            "",
            "User research brief:",
            json.dumps(request.model_dump(exclude_none=True), indent=2, sort_keys=True),
            "",
            "Output rules:",
            "- Return valid JSON only. No markdown fence, no commentary before or after the JSON.",
            "- Match the JSON schema exactly.",
            "- Every major opportunity field must be populated with known, inferred, estimated or unknown metadata.",
            "- If evidence is weak, use value_type unknown with confidence_score 0 and a clear next step.",
            "- Revenue and margin estimates must include rationale and confidence.",
            "- Use concise, board-level commercial language.",
            "- Include source URLs wherever public evidence exists.",
            "- Treat the information as commercially sensitive.",
            "",
            "JSON schema to match:",
            json.dumps(RESEARCH_OPPORTUNITY_JSON_SCHEMA, indent=2, sort_keys=True),
        ]
    )
    return ChatGPTAssistPromptResponse(
        prompt=prompt,
        expected_output_schema=RESEARCH_OPPORTUNITY_JSON_SCHEMA,
        copy_steps=[
            "Copy this prompt into ChatGPT Plus.",
            "Let ChatGPT research and return JSON only.",
            "Paste the JSON back into MiSi ChatGPT Assist Import.",
            "MiSi will validate, label and import the intelligence pack without using the API.",
        ],
        safety_note=(
            "This is a manual human-in-the-loop workflow. MiSi does not automate "
            "ChatGPT, scrape a Plus session or send OpenAI keys to the browser."
        ),
    )


def import_chatgpt_assist_result(
    request: ChatGPTAssistImportRequest,
    *,
    db: Session,
) -> ResearchOpportunityResponse:
    research_request = ResearchOpportunityRequest(
        query=request.query,
        sector_hint=request.sector_hint,
        region_hint=request.region_hint,
        buyer_hint=request.buyer_hint,
        create_opportunity=request.create_opportunity,
    )
    run = EnrichmentRun(
        run_type="manual_chatgpt_assist",
        status="running",
        user_query=request.query,
        model_used="chatgpt_plus_manual",
        search_performed=True,
        sources_checked=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        structured = _validate_chatgpt_assist_json(request.result_json)
        sources = structured.sources
        run.sources_checked = [source.model_dump() for source in sources]
        db.commit()

        draft_opportunity = _draft_from_ai_result(structured, request=research_request)
        draft_enrichment = _enrichment_from_ai_result(structured)
        draft_fields = _field_intelligence_from_ai_result(
            structured,
            sources=sources,
        )

        opportunity: Opportunity | None = None
        field_records: list[FieldIntelligence] = []
        enrichment_record: OpportunityEnrichment | None = None
        executive_action: ExecutiveAction | None = None
        finance_forecast: FinanceForecast | None = None
        created_opportunity = False
        records_created = 0
        records_updated = 0

        if request.create_opportunity:
            opportunity, created_opportunity = _create_or_update_opportunity(
                db,
                request=research_request,
                draft=draft_opportunity,
            )
            db.flush()
            records_created += 1 if created_opportunity else 0
            records_updated += 0 if created_opportunity else 1

            run.opportunity_id = opportunity.id
            field_records = _persist_field_intelligence(
                db,
                opportunity_id=opportunity.id,
                fields=draft_fields,
            )
            records_created += len(field_records)

            enrichment_record = _persist_opportunity_enrichment(
                db,
                opportunity_id=opportunity.id,
                run_id=run.id,
                enrichment=draft_enrichment,
            )
            records_created += 1

            finance_forecast = _persist_finance_forecast(
                db,
                opportunity_id=opportunity.id,
                draft=draft_opportunity,
                payload=_finance_forecast_payload_from_ai(
                    structured,
                    draft_opportunity,
                ),
            )
            if finance_forecast is not None:
                records_created += 1

            executive_action = _persist_executive_action(
                db,
                opportunity_id=opportunity.id,
                draft=draft_opportunity,
                payload=structured.executive_action.model_dump(),
            )
            if executive_action is not None:
                records_created += 1

        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.records_created = records_created
        run.records_updated = records_updated
        db.commit()
        db.refresh(run)

        if opportunity is not None:
            db.refresh(opportunity)
        for record in [*field_records, enrichment_record, executive_action, finance_forecast]:
            if record is not None:
                db.refresh(record)

        return ResearchOpportunityResponse(
            enrichment_run=EnrichmentRunRead.model_validate(run),
            created_opportunity=created_opportunity,
            opportunity=enrich_opportunity(opportunity) if opportunity else None,
            draft_opportunity=draft_opportunity,
            field_intelligence=[
                FieldIntelligenceRead.model_validate(record) for record in field_records
            ],
            draft_field_intelligence=draft_fields,
            opportunity_enrichment=(
                OpportunityEnrichmentRead.model_validate(enrichment_record)
                if enrichment_record
                else None
            ),
            draft_enrichment=draft_enrichment,
            executive_action=(
                ExecutiveActionRead.model_validate(executive_action)
                if executive_action
                else None
            ),
            finance_forecast=(
                FinanceForecastRead.model_validate(finance_forecast)
                if finance_forecast
                else None
            ),
            sources=sources,
            overall_confidence=draft_enrichment.overall_confidence,
        )
    except InvalidOpenAIJSONError as exc:
        _mark_run_failed(db, run.id, "Manual ChatGPT JSON failed MiSi validation.")
        raise exc
    except Exception as exc:
        _mark_run_failed(db, run.id, "Manual ChatGPT import failed before completion.")
        raise InvalidOpenAIJSONError(
            "Manual ChatGPT output could not be imported as structured MiSi JSON."
        ) from exc


def autofill_opportunities_with_openai(
    request: AutofillOpportunitiesRequest,
    *,
    db: Session,
    client: Any | None = None,
    settings: Settings | None = None,
) -> AutofillOpportunitiesResponse:
    active_settings = settings or get_settings()
    openai_client = client or get_openai_client(active_settings)
    opportunities = list(db.scalars(select(Opportunity).order_by(Opportunity.id)).all())
    candidates: list[Opportunity] = []
    skipped_count = 0

    for opportunity in opportunities:
        if request.only_incomplete and not _is_incomplete_opportunity(opportunity):
            skipped_count += 1
            continue
        if len(candidates) >= request.limit:
            break
        candidates.append(opportunity)

    results = [
        _autofill_single_opportunity(
            opportunity,
            request=request,
            db=db,
            client=openai_client,
            settings=active_settings,
        )
        for opportunity in candidates
    ]
    warnings = [
        warning
        for result in results
        for warning in result.confidence_warnings
    ]

    return AutofillOpportunitiesResponse(
        records_scanned=len(candidates),
        records_enriched=sum(1 for result in results if result.status == "enriched"),
        records_skipped=skipped_count,
        records_failed=sum(1 for result in results if result.status == "failed"),
        fields_filled=sum(result.fields_filled for result in results),
        fields_still_unknown=sum(result.fields_still_unknown for result in results),
        confidence_warnings=warnings[:25],
        results=results,
    )


def _autofill_single_opportunity(
    opportunity: Opportunity,
    *,
    request: AutofillOpportunitiesRequest,
    db: Session,
    client: Any,
    settings: Settings,
) -> AutofillOpportunityResult:
    research_request = _autofill_research_request(opportunity)
    run = EnrichmentRun(
        run_type="bulk_opportunity_autofill",
        status="running",
        user_query=research_request.query,
        opportunity_id=opportunity.id,
        model_used=settings.openai_model,
        search_performed=False,
        sources_checked=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        original_values = {
            field_name: _opportunity_field_value(opportunity, field_name)
            for field_name in KEY_FIELD_NAMES
        }
        search_result = research_internet_with_openai(
            _internet_research_request(research_request),
            client=client,
            settings=settings,
        )
        sources = _sources_from_search(search_result)
        run.search_performed = True
        run.sources_checked = [source.model_dump() for source in sources]
        db.commit()

        structured = _convert_search_to_record(
            request=research_request,
            search_result=search_result,
            client=client,
            settings=settings,
        )
        sources = _merge_sources(sources, structured.sources)
        run.sources_checked = [source.model_dump() for source in sources]

        draft = _draft_from_ai_result(structured, request=research_request)
        draft_enrichment = _enrichment_from_ai_result(structured)
        draft_fields = _field_intelligence_from_ai_result(structured, sources=sources)
        apply_result = _apply_autofill_values(
            opportunity,
            draft_fields=draft_fields,
            request=request,
        )
        field_records = _autofill_field_intelligence_records(
            opportunity,
            original_values=original_values,
            draft_fields=draft_fields,
            filled_field_names=apply_result["filled_field_names"],
            sources=sources,
        )
        persisted_fields = _persist_field_intelligence(
            db,
            opportunity_id=opportunity.id,
            fields=field_records,
        )
        enrichment_record = _persist_opportunity_enrichment(
            db,
            opportunity_id=opportunity.id,
            run_id=run.id,
            enrichment=draft_enrichment,
        )
        unknown_count = sum(
            1 for field in field_records if field.value_type == "unknown"
        )
        warnings = list(apply_result["confidence_warnings"])
        if unknown_count:
            warnings.append(
                f"{opportunity.name}: {unknown_count} fields remain unknown and need source confirmation."
            )

        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.records_created = len(persisted_fields) + 1
        run.records_updated = 1 if apply_result["fields_filled"] else 0
        db.commit()
        db.refresh(run)
        db.refresh(opportunity)
        db.refresh(enrichment_record)

        return AutofillOpportunityResult(
            opportunity_id=opportunity.id,
            opportunity_name=opportunity.name,
            status="enriched",
            enrichment_run_id=run.id,
            fields_filled=apply_result["fields_filled"],
            fields_preserved=apply_result["fields_preserved"],
            fields_still_unknown=unknown_count,
            confidence_warnings=warnings[:8],
        )
    except (MissingOpenAIKeyError, OpenAIRequestError, InvalidOpenAIJSONError) as exc:
        _mark_run_failed(db, run.id, _safe_error_message(exc))
        return AutofillOpportunityResult(
            opportunity_id=opportunity.id,
            opportunity_name=opportunity.name,
            status="failed",
            enrichment_run_id=run.id,
            error_message=_safe_error_message(exc),
            confidence_warnings=[
                f"{opportunity.name}: autofill failed; existing opportunity values were preserved."
            ],
        )
    except Exception as exc:
        logger.exception(
            "Unexpected opportunity autofill failure for opportunity_id=%s",
            opportunity.id,
        )
        _mark_run_failed(db, run.id, "Autofill failed for this opportunity.")
        return AutofillOpportunityResult(
            opportunity_id=opportunity.id,
            opportunity_name=opportunity.name,
            status="failed",
            enrichment_run_id=run.id,
            error_message="Autofill failed for this opportunity.",
            confidence_warnings=[
                f"{opportunity.name}: autofill failed; existing opportunity values were preserved."
            ],
        )


def _autofill_research_request(opportunity: Opportunity) -> ResearchOpportunityRequest:
    context_parts = [
        opportunity.name,
        f"buyer {opportunity.buyer_name}",
        f"sector {opportunity.sector}",
        f"region {opportunity.region}",
        f"stage {opportunity.stage}",
        "UK Fire and Security commercial opportunity",
    ]
    action = _text_value(opportunity.recommended_action)
    if action:
        context_parts.append(f"current next action {action}")
    return ResearchOpportunityRequest(
        query=" | ".join(part for part in context_parts if _text_value(part)),
        sector_hint=_text_value(opportunity.sector),
        region_hint=_text_value(opportunity.region),
        buyer_hint=_text_value(opportunity.buyer_name),
        create_opportunity=False,
    )


def _apply_autofill_values(
    opportunity: Opportunity,
    *,
    draft_fields: list[ResearchOpportunityFieldIntelligence],
    request: AutofillOpportunitiesRequest,
) -> dict[str, Any]:
    fields_by_name = {field.field_name: field for field in draft_fields}
    filled_field_names: set[str] = set()
    preserved_field_names: set[str] = set()
    warnings: list[str] = []

    for field_name in AI_OPPORTUNITY_FIELD_NAMES:
        field = fields_by_name.get(field_name)
        current_value = _opportunity_field_value(opportunity, field_name)
        if field is None or not _ai_field_can_fill(field):
            if not _is_weak_field_value(field_name, current_value):
                preserved_field_names.add(field_name)
            continue

        normalised_value = _normalise_autofill_value(field_name, field.field_value)
        if _is_empty_autofill_value(field_name, normalised_value):
            if not _is_weak_field_value(field_name, current_value):
                preserved_field_names.add(field_name)
            continue

        should_fill = _is_weak_field_value(field_name, current_value)
        should_overwrite = (
            request.allow_overwrite
            and field.confidence_score >= request.overwrite_confidence_threshold
        )
        if should_fill or should_overwrite:
            _set_opportunity_field(opportunity, field_name, normalised_value)
            filled_field_names.add(field_name)
            if field.confidence_score < 0.55:
                warnings.append(
                    f"{opportunity.name}: {field_name.replace('_', ' ')} was filled at {round(field.confidence_score * 100)}% confidence; confirm before governance."
                )
        else:
            preserved_field_names.add(field_name)

    if _is_weak_field_value("weighted_value", opportunity.weighted_value):
        weighted_value = _weighted_value_from_opportunity(opportunity)
        if weighted_value is not None:
            opportunity.weighted_value = weighted_value
            filled_field_names.add("weighted_value")

    return {
        "filled_field_names": filled_field_names,
        "preserved_field_names": preserved_field_names,
        "fields_filled": len(filled_field_names),
        "fields_preserved": len(preserved_field_names),
        "confidence_warnings": warnings,
    }


def _autofill_field_intelligence_records(
    opportunity: Opportunity,
    *,
    original_values: dict[str, Any],
    draft_fields: list[ResearchOpportunityFieldIntelligence],
    filled_field_names: set[str],
    sources: list[ResearchOpportunitySource],
) -> list[ResearchOpportunityFieldIntelligence]:
    fields_by_name = {field.field_name: field for field in draft_fields}
    source_urls = [source.url for source in sources[:3]]
    source_titles = [source.title for source in sources[:3]]
    records: list[ResearchOpportunityFieldIntelligence] = []

    for field_name in KEY_FIELD_NAMES:
        current_value = _serialise_opportunity_field_value(
            _opportunity_field_value(opportunity, field_name),
        )
        original_value = original_values.get(field_name)
        ai_field = fields_by_name.get(field_name)

        if field_name in filled_field_names:
            if field_name == "weighted_value":
                records.append(
                    ResearchOpportunityFieldIntelligence(
                        field_name=field_name,
                        field_value=current_value,
                        value_type="system_calculated",
                        confidence_score=_weighted_confidence_from_fields(fields_by_name),
                        rationale="Calculated by MiSi after autofill from total contract value and probability.",
                        source_urls=source_urls,
                        source_titles=source_titles,
                        recommended_next_step="Confirm value and probability assumptions before LE1 forecast use.",
                        needs_user_confirmation=True,
                    )
                )
            elif ai_field is not None:
                records.append(ai_field.model_copy(update={"field_value": current_value}))
            else:
                records.append(
                    _unknown_field(
                        field_name,
                        source_urls=source_urls,
                        source_titles=source_titles,
                    )
                )
            continue

        if not _is_weak_field_value(field_name, original_value):
            records.append(
                _user_provided_field(
                    field_name,
                    current_value,
                )
            )
            continue

        if ai_field is not None:
            records.append(ai_field)
            continue

        records.append(
            _unknown_field(
                field_name,
                source_urls=source_urls,
                source_titles=source_titles,
            )
        )

    return records


def _is_incomplete_opportunity(opportunity: Opportunity) -> bool:
    return any(
        _is_weak_field_value(field_name, _opportunity_field_value(opportunity, field_name))
        for field_name in KEY_FIELD_NAMES
    )


def _opportunity_field_value(opportunity: Opportunity, field_name: str) -> Any:
    return getattr(opportunity, field_name, None)


def _is_weak_field_value(field_name: str, value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip().lower()
        return (
            not text
            or text in {"unknown", "n/a", "none", "null", "not set", "tbc", "review_required"}
            or "confirmation required" in text
        )
    if field_name in {
        "estimated_annual_revenue",
        "estimated_total_contract_value",
        "estimated_gross_margin",
        "margin_percentage",
        "probability",
        "weighted_value",
        "strategic_fit_score",
    }:
        try:
            return float(value) <= 0
        except (TypeError, ValueError):
            return True
    return False


def _ai_field_can_fill(field: ResearchOpportunityFieldIntelligence) -> bool:
    return field.value_type != "unknown" and field.field_value not in (None, "", [])


def _normalise_autofill_value(field_name: str, value: Any) -> Any:
    if field_name in {
        "estimated_annual_revenue",
        "estimated_total_contract_value",
        "estimated_gross_margin",
    }:
        return _money_value(value)
    if field_name == "margin_percentage":
        return _percentage_value(value)
    if field_name == "probability":
        return _probability_value(value)
    if field_name == "strategic_fit_score":
        return _score_value(value)
    if field_name == "submission_deadline":
        return _date_value(value)
    if field_name == "forecast_start_month":
        return _month_value(value)
    return _text_value(value)


def _is_empty_autofill_value(field_name: str, value: Any) -> bool:
    if field_name == "submission_deadline":
        return value is None
    if field_name == "forecast_start_month":
        return value is None
    if isinstance(value, str):
        return not value.strip()
    if field_name in {
        "estimated_annual_revenue",
        "estimated_total_contract_value",
        "estimated_gross_margin",
        "margin_percentage",
        "probability",
        "weighted_value",
        "strategic_fit_score",
    }:
        try:
            return float(value) <= 0
        except (TypeError, ValueError):
            return True
    return value is None


def _set_opportunity_field(opportunity: Opportunity, field_name: str, value: Any) -> None:
    setattr(opportunity, field_name, value)


def _weighted_value_from_opportunity(opportunity: Opportunity) -> float | None:
    value = _money_value(opportunity.estimated_total_contract_value)
    probability = _probability_value(opportunity.probability)
    if value <= 0 or probability <= 0:
        return None
    return round(value * probability, 2)


def _weighted_confidence_from_fields(
    fields_by_name: dict[str, ResearchOpportunityFieldIntelligence],
) -> float:
    value_field = fields_by_name.get("estimated_total_contract_value")
    probability_field = fields_by_name.get("probability")
    if value_field is None or probability_field is None:
        return 0.5
    return round(min(value_field.confidence_score, probability_field.confidence_score), 2)


def _serialise_opportunity_field_value(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    return value


def _user_provided_field(
    field_name: str,
    value: Any,
) -> ResearchOpportunityFieldIntelligence:
    label = field_name.replace("_", " ")
    return ResearchOpportunityFieldIntelligence(
        field_name=field_name,
        field_value=_serialise_opportunity_field_value(value),
        value_type="user_provided",
        confidence_score=1,
        rationale=f"Existing MiSi {label} was preserved during bulk autofill.",
        source_urls=[],
        source_titles=[],
        recommended_next_step="Only change this value if an approved commercial source confirms the update.",
        needs_user_confirmation=False,
    )


def _internet_research_request(
    request: ResearchOpportunityRequest,
) -> InternetIntelligenceRequest:
    query_parts = [request.query]
    if request.buyer_hint:
        query_parts.append(f"buyer: {request.buyer_hint}")
    if request.sector_hint:
        query_parts.append(f"sector: {request.sector_hint}")
    if request.region_hint:
        query_parts.append(f"region: {request.region_hint}")
    return InternetIntelligenceRequest(
        intelligence_type="opportunity_intelligence",
        query=" | ".join(query_parts),
        sector=request.sector_hint,
        region=request.region_hint,
        buyer_name=request.buyer_hint,
        opportunity_name=request.query,
    )


def _convert_search_to_record(
    *,
    request: ResearchOpportunityRequest,
    search_result: InternetIntelligenceResult,
    client: Any,
    settings: Settings,
) -> ResearchOpportunityAIResult:
    prompt_payload = {
        "user_query": request.model_dump(exclude_none=True),
        "internet_research": search_result.model_dump(),
        "required_opportunity_field_names": AI_OPPORTUNITY_FIELD_NAMES,
    }
    try:
        response = client.responses.create(
            model=settings.openai_model,
            instructions=_conversion_system_prompt(),
            input=json.dumps(prompt_payload, sort_keys=True),
            reasoning={"effort": "low"},
            text={
                "format": {
                    "type": "json_schema",
                    "name": "misi_standing_start_opportunity",
                    "schema": RESEARCH_OPPORTUNITY_JSON_SCHEMA,
                    "strict": True,
                }
            },
            store=False,
            max_output_tokens=4500,
            timeout=settings.openai_request_timeout_seconds,
        )
    except OpenAIError as exc:
        raise OpenAIRequestError("OpenAI opportunity research request failed.") from exc

    content = _extract_response_text(response)
    try:
        payload = json.loads(content)
        return _validate_structured_payload(payload)
    except (KeyError, json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise InvalidOpenAIJSONError(
            "OpenAI returned invalid structured JSON for opportunity research."
        ) from exc


def _validate_structured_payload(payload: dict[str, Any]) -> ResearchOpportunityAIResult:
    return ResearchOpportunityAIResult.model_validate(payload)


def _validate_chatgpt_assist_json(content: str) -> ResearchOpportunityAIResult:
    try:
        payload = json.loads(_strip_json_fence(content))
        return _validate_structured_payload(payload)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise InvalidOpenAIJSONError(
            "Manual ChatGPT output is not valid MiSi structured JSON."
        ) from exc


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


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


def _conversion_system_prompt() -> str:
    return build_commercial_system_prompt(
        role=(
            "You are MiSi, a senior commercial intelligence analyst for Mitie "
            "Fire & Security."
        ),
        task=(
            "Convert source-attributed internet research into a complete "
            "commercial opportunity intelligence record from a standing start."
        ),
        output_contract="Return only JSON matching the schema.",
        extra_rules=[
            "Do not fabricate facts as known.",
            "Use known only when the evidence or user input directly supports the value.",
            "Use inferred for reasoned commercial conclusions, estimated for numerical assumptions and unknown when evidence is insufficient.",
            "Every unknown field must include null or a useful placeholder, confidence_score 0, a rationale explaining why it is unknown, needs_user_confirmation true and a recommended next step in the rationale.",
            "Populate every required nested opportunity field.",
            "Revenue and margin estimates must include commercial rationale.",
            "Keep rationales and assessments under 35 words each.",
            "Use strategic_fit_score on a 0-100 scale.",
            "Probability may be returned as 0-1 or 0-100; the backend will normalise it.",
            "Return no more than three buyer drivers, three risks, three unknowns and three next steps unless the schema field specifically requires more.",
            "Use phrases such as scope confirmation required, asset data risk, margin protection required and executive attention required only when supported by the supplied evidence or a clearly labelled inference.",
        ],
    )


def _sources_from_search(
    search_result: InternetIntelligenceResult,
) -> list[ResearchOpportunitySource]:
    sources: list[ResearchOpportunitySource] = []
    seen: set[str] = set()
    for finding in search_result.findings:
        for url in finding.source_urls:
            normalised_url = url.strip()
            if normalised_url and normalised_url not in seen:
                seen.add(normalised_url)
                sources.append(
                    ResearchOpportunitySource(
                        title=finding.title,
                        url=normalised_url,
                    )
                )
    for url in search_result.source_urls:
        normalised_url = url.strip()
        if normalised_url and normalised_url not in seen:
            seen.add(normalised_url)
            sources.append(
                ResearchOpportunitySource(
                    title="Source discovered during internet research",
                    url=normalised_url,
                )
            )
    return sources[:12]


def _merge_sources(
    primary: list[ResearchOpportunitySource],
    secondary: list[ResearchOpportunitySource],
) -> list[ResearchOpportunitySource]:
    merged: list[ResearchOpportunitySource] = []
    seen: set[str] = set()
    for source in [*secondary, *primary]:
        url = source.url.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append(source)
    return merged[:12]


def _draft_from_ai_result(
    result: ResearchOpportunityAIResult,
    *,
    request: ResearchOpportunityRequest,
) -> ResearchOpportunityDraft:
    opportunity = result.opportunity
    draft = ResearchOpportunityDraft(
        name=_ai_field_value(opportunity.name),
        buyer_name=_ai_field_value(opportunity.buyer_name),
        sector=_ai_field_value(opportunity.sector) or request.sector_hint,
        region=_ai_field_value(opportunity.region) or request.region_hint,
        source_type=_ai_field_value(opportunity.source_type),
        stage=_ai_field_value(opportunity.stage),
        estimated_annual_revenue=_ai_field_value(opportunity.estimated_annual_revenue),
        estimated_total_contract_value=_ai_field_value(
            opportunity.estimated_total_contract_value,
        ),
        estimated_gross_margin=_ai_field_value(opportunity.estimated_gross_margin),
        margin_percentage=_ai_field_value(opportunity.margin_percentage),
        probability=_ai_field_value(opportunity.probability),
        submission_deadline=_ai_field_value(opportunity.submission_deadline),
        forecast_start_month=_ai_field_value(opportunity.forecast_start_month),
        self_delivery_fit=_ai_field_value(opportunity.self_delivery_fit),
        risk_rating=_ai_field_value(opportunity.risk_rating),
        strategic_fit_score=_ai_field_value(opportunity.strategic_fit_score),
        bid_no_bid_recommendation=_ai_field_value(
            opportunity.bid_no_bid_recommendation,
        ),
        recommended_action=_ai_field_value(opportunity.recommended_action),
        finance_forecast_category=_forecast_category_from_ai(result),
        executive_action=result.executive_action.recommended_action,
    )
    return draft.model_copy(update={"weighted_value": _calculate_weighted_value(draft)})


def _enrichment_from_ai_result(
    result: ResearchOpportunityAIResult,
) -> ResearchOpportunityEnrichmentPack:
    intelligence = result.intelligence
    return ResearchOpportunityEnrichmentPack(
        buyer_summary=intelligence.buyer_summary,
        opportunity_summary=intelligence.opportunity_summary,
        likely_scope=intelligence.likely_scope,
        estimated_contract_value_rationale=(
            result.opportunity.estimated_total_contract_value.rationale
        ),
        likely_buyer_drivers=intelligence.likely_buyer_drivers,
        compliance_drivers=intelligence.compliance_drivers,
        competitor_assessment=intelligence.competitor_assessment,
        commercial_assessment=intelligence.commercial_assessment,
        mobilisation_assessment=intelligence.mobilisation_assessment,
        self_delivery_assessment=intelligence.self_delivery_assessment,
        finance_assessment=intelligence.finance_assessment,
        executive_recommendation=intelligence.executive_recommendation,
        unknowns=intelligence.unknowns,
        recommended_next_steps=intelligence.recommended_next_steps,
        overall_confidence=intelligence.overall_confidence,
    )


def _field_intelligence_from_ai_result(
    result: ResearchOpportunityAIResult,
    *,
    sources: list[ResearchOpportunitySource],
) -> list[ResearchOpportunityFieldIntelligence]:
    fields: list[ResearchOpportunityFieldIntelligence] = []
    opportunity = result.opportunity
    for field_name in AI_OPPORTUNITY_FIELD_NAMES:
        ai_field = getattr(opportunity, field_name)
        source_urls = _source_urls_for_ai_field(ai_field, sources)
        fields.append(
            ResearchOpportunityFieldIntelligence(
                field_name=field_name,
                field_value=_ai_field_value(ai_field),
                value_type=ai_field.value_type,
                confidence_score=ai_field.confidence_score,
                rationale=ai_field.rationale,
                source_urls=source_urls,
                source_titles=_source_titles_for_urls(source_urls, sources),
                recommended_next_step=_recommended_next_step_for_ai_field(
                    field_name,
                    ai_field,
                    result,
                ),
                needs_user_confirmation=ai_field.value_type != "known",
            )
        )

    weighted_value = _calculate_weighted_value(_draft_from_ai_result(result, request=ResearchOpportunityRequest(query="system")))
    if weighted_value is None:
        fields.append(
            _unknown_field(
                "weighted_value",
                source_urls=[source.url for source in sources[:3]],
                source_titles=[source.title for source in sources[:3]],
            )
        )
    else:
        fields.append(
            ResearchOpportunityFieldIntelligence(
                field_name="weighted_value",
                field_value=weighted_value,
                value_type="system_calculated",
                confidence_score=min(
                    result.opportunity.estimated_total_contract_value.confidence_score,
                    result.opportunity.probability.confidence_score,
                ),
                rationale=(
                    "Calculated by MiSi from AI-estimated total contract value and "
                    "probability after numeric normalisation."
                ),
                source_urls=[source.url for source in sources[:3]],
                source_titles=[source.title for source in sources[:3]],
                recommended_next_step="Validate the contract value and probability assumptions before using this in forecast review.",
                needs_user_confirmation=True,
            )
        )
    return fields


def _ai_field_value(field: ResearchOpportunityAIFieldBase) -> Any:
    return getattr(field, "value", None)


def _source_urls_for_ai_field(
    field: ResearchOpportunityAIFieldBase,
    sources: list[ResearchOpportunitySource],
) -> list[str]:
    urls = [url.strip() for url in field.source_urls if url.strip()]
    if urls:
        return urls[:6]
    return [source.url for source in sources[:3]]


def _source_titles_for_urls(
    urls: list[str],
    sources: list[ResearchOpportunitySource],
) -> list[str]:
    titles_by_url = {source.url: source.title for source in sources}
    return [titles_by_url[url] for url in urls if url in titles_by_url]


def _recommended_next_step_for_ai_field(
    field_name: str,
    field: ResearchOpportunityAIFieldBase,
    result: ResearchOpportunityAIResult,
) -> str:
    label = field_name.replace("_", " ")
    if field.value_type == "unknown":
        return f"Confirm the {label} from the tender pack, buyer contact, CRM or approved internal source."
    if field.value_type == "estimated":
        return f"Validate the {label} estimate against source evidence before using it commercially."
    if field.value_type == "inferred":
        return f"Confirm the inferred {label} with source evidence or the relevant internal owner."
    if result.intelligence.recommended_next_steps:
        return result.intelligence.recommended_next_steps[0]
    return f"Review the source evidence supporting {label}."


def _forecast_category_from_ai(result: ResearchOpportunityAIResult) -> str:
    probability = _probability_value(result.opportunity.probability.value)
    risk_rating = _text_value(result.opportunity.risk_rating.value) or "Amber"
    if result.opportunity.estimated_total_contract_value.value is None:
        return "Excluded"
    if risk_rating == "Red":
        return "At risk"
    if probability >= 0.65:
        return "Likely"
    if probability >= 0.4:
        return "Best case"
    return "Stretch"


def _finance_forecast_payload_from_ai(
    result: ResearchOpportunityAIResult,
    draft: ResearchOpportunityDraft,
) -> dict[str, Any]:
    return {
        "forecast_category": draft.finance_forecast_category,
        "start_month": draft.forecast_start_month,
        "revenue_to_year_end": draft.estimated_annual_revenue,
        "estimated_margin": draft.estimated_gross_margin,
        "margin_percentage": draft.margin_percentage,
        "probability_weighting": draft.probability,
        "risk_adjustment": _risk_adjustment_from_rating(draft.risk_rating),
        "notes": result.intelligence.finance_assessment,
    }


def _risk_adjustment_from_rating(risk_rating: str | None) -> float:
    rating = (risk_rating or "").strip().lower()
    if rating == "red":
        return 0.4
    if rating == "amber":
        return 0.2
    if rating == "green":
        return 0.05
    return 0.25


def _normalise_field_intelligence(
    raw_fields: list[dict[str, Any]],
    *,
    draft: ResearchOpportunityDraft,
    enrichment: ResearchOpportunityEnrichmentPack,
    sources: list[ResearchOpportunitySource],
) -> list[ResearchOpportunityFieldIntelligence]:
    fields_by_name: dict[str, ResearchOpportunityFieldIntelligence] = {}
    for raw_field in raw_fields:
        try:
            field = ResearchOpportunityFieldIntelligence.model_validate(raw_field)
        except ValidationError:
            continue
        normalised_name = _normalise_field_name(field.field_name)
        fields_by_name[normalised_name] = field.model_copy(
            update={"field_name": normalised_name},
        )

    source_urls = [source.url for source in sources[:3]]
    source_titles = [source.title for source in sources[:3]]
    for field_name in KEY_FIELD_NAMES:
        if field_name in fields_by_name:
            continue
        value = _draft_or_enrichment_value(field_name, draft, enrichment)
        if value in (None, "", []):
            fields_by_name[field_name] = _unknown_field(
                field_name,
                source_urls=source_urls,
                source_titles=source_titles,
            )
        else:
            fields_by_name[field_name] = ResearchOpportunityFieldIntelligence(
                field_name=field_name,
                field_value=value,
                value_type="inferred",
                confidence_score=0.45,
                rationale=(
                    "Derived from the structured opportunity record because the AI "
                    "did not provide field-level metadata."
                ),
                source_urls=source_urls,
                source_titles=source_titles,
                recommended_next_step="Validate this inferred value against the tender notice, buyer website or internal CRM.",
                needs_user_confirmation=True,
            )

    weighted_value = _calculate_weighted_value(draft)
    if weighted_value is not None:
        fields_by_name["weighted_value"] = ResearchOpportunityFieldIntelligence(
            field_name="weighted_value",
            field_value=weighted_value,
            value_type="system_calculated",
            confidence_score=_weighted_value_confidence(fields_by_name),
            rationale=(
                "Calculated by MiSi from estimated total contract value and probability."
            ),
            source_urls=source_urls,
            source_titles=source_titles,
            recommended_next_step="Confirm the estimated contract value and probability assumptions.",
            needs_user_confirmation=True,
        )

    return [fields_by_name[field_name] for field_name in KEY_FIELD_NAMES]


def _normalise_field_name(field_name: str) -> str:
    aliases = {
        "opportunity_name": "name",
        "tender_stage": "stage",
        "buyer_drivers": "likely_buyer_drivers",
        "finance_category": "finance_forecast_category",
    }
    normalised = field_name.strip().lower().replace(" ", "_").replace("-", "_")
    return aliases.get(normalised, normalised)


def _draft_or_enrichment_value(
    field_name: str,
    draft: ResearchOpportunityDraft,
    enrichment: ResearchOpportunityEnrichmentPack,
) -> Any:
    if hasattr(draft, field_name):
        return getattr(draft, field_name)
    if hasattr(enrichment, field_name):
        return getattr(enrichment, field_name)
    if field_name == "likely_buyer_drivers":
        return enrichment.likely_buyer_drivers
    if field_name == "competitor_threat":
        return enrichment.competitor_threat
    if field_name == "mobilisation_risks":
        return enrichment.mobilisation_risks
    if field_name == "commercial_risks":
        return enrichment.commercial_risks
    return None


def _unknown_field(
    field_name: str,
    *,
    source_urls: list[str],
    source_titles: list[str],
) -> ResearchOpportunityFieldIntelligence:
    label = field_name.replace("_", " ")
    return ResearchOpportunityFieldIntelligence(
        field_name=field_name,
        field_value=None,
        value_type="unknown",
        confidence_score=0,
        rationale=f"The {label} could not be determined from the available public evidence.",
        source_urls=source_urls,
        source_titles=source_titles,
        recommended_next_step=f"Confirm the {label} from the tender pack, buyer contact, CRM or approved internal source.",
        needs_user_confirmation=True,
    )


def _create_or_update_opportunity(
    db: Session,
    *,
    request: ResearchOpportunityRequest,
    draft: ResearchOpportunityDraft,
) -> tuple[Opportunity, bool]:
    name = _text_value(draft.name) or f"AI research: {request.query[:180]}"
    buyer_name = (
        _text_value(draft.buyer_name)
        or _text_value(request.buyer_hint)
        or "Unknown buyer - confirmation required"
    )
    existing = db.scalar(
        select(Opportunity)
        .where(Opportunity.name == name)
        .where(Opportunity.buyer_name == buyer_name)
    )
    opportunity = existing or Opportunity(name=name, buyer_name=buyer_name)
    opportunity.sector = (
        _text_value(draft.sector)
        or _text_value(request.sector_hint)
        or "Unknown sector - confirmation required"
    )
    opportunity.region = (
        _text_value(draft.region)
        or _text_value(request.region_hint)
        or "Unknown region - confirmation required"
    )
    opportunity.source_type = _text_value(draft.source_type) or "AI internet research"
    opportunity.stage = _text_value(draft.stage) or "Market signal"
    opportunity.owner = "Commercial Intelligence"
    opportunity.estimated_annual_revenue = _money_value(draft.estimated_annual_revenue)
    opportunity.estimated_total_contract_value = _money_value(
        draft.estimated_total_contract_value,
    )
    opportunity.estimated_gross_margin = _money_value(draft.estimated_gross_margin)
    opportunity.margin_percentage = _percentage_value(draft.margin_percentage)
    opportunity.probability = _probability_value(draft.probability)
    opportunity.weighted_value = _money_value(
        _calculate_weighted_value(draft) or draft.weighted_value,
    )
    opportunity.submission_deadline = _date_value(draft.submission_deadline)
    opportunity.forecast_start_month = _month_value(draft.forecast_start_month)
    opportunity.self_delivery_fit = _text_value(draft.self_delivery_fit) or "Unknown"
    opportunity.risk_rating = _text_value(draft.risk_rating) or "Amber"
    opportunity.strategic_fit_score = _score_value(draft.strategic_fit_score)
    opportunity.bid_no_bid_recommendation = (
        _text_value(draft.bid_no_bid_recommendation) or "Watch"
    )
    opportunity.recommended_action = (
        _text_value(draft.recommended_action)
        or "Validate source evidence and complete commercial qualification."
    )
    if existing is None:
        db.add(opportunity)
        return opportunity, True
    return opportunity, False


def _persist_field_intelligence(
    db: Session,
    *,
    opportunity_id: int,
    fields: list[ResearchOpportunityFieldIntelligence],
) -> list[FieldIntelligence]:
    records: list[FieldIntelligence] = []
    for field in fields:
        record = FieldIntelligence(
            entity_type="opportunity",
            entity_id=opportunity_id,
            field_name=field.field_name,
            field_value=field.field_value,
            value_type=field.value_type,
            confidence_score=field.confidence_score,
            rationale=field.rationale,
            source_urls=field.source_urls,
            source_titles=field.source_titles,
            recommended_next_step=field.recommended_next_step,
            needs_user_confirmation=field.needs_user_confirmation,
        )
        db.add(record)
        records.append(record)
    return records


def _persist_opportunity_enrichment(
    db: Session,
    *,
    opportunity_id: int,
    run_id: int,
    enrichment: ResearchOpportunityEnrichmentPack,
) -> OpportunityEnrichment:
    record = OpportunityEnrichment(
        opportunity_id=opportunity_id,
        enrichment_run_id=run_id,
        buyer_summary=enrichment.buyer_summary,
        opportunity_summary=enrichment.opportunity_summary,
        likely_scope="; ".join(enrichment.likely_scope),
        estimated_contract_value_rationale=(
            enrichment.estimated_contract_value_rationale
        ),
        likely_buyer_drivers=enrichment.likely_buyer_drivers,
        compliance_drivers=enrichment.compliance_drivers,
        competitor_assessment=enrichment.competitor_assessment,
        commercial_assessment=enrichment.commercial_assessment,
        mobilisation_assessment=enrichment.mobilisation_assessment,
        self_delivery_assessment=enrichment.self_delivery_assessment,
        finance_assessment=enrichment.finance_assessment,
        executive_recommendation=enrichment.executive_recommendation,
        unknowns=enrichment.unknowns,
        recommended_next_steps=enrichment.recommended_next_steps,
        overall_confidence=enrichment.overall_confidence,
    )
    db.add(record)
    return record


def _persist_finance_forecast(
    db: Session,
    *,
    opportunity_id: int,
    draft: ResearchOpportunityDraft,
    payload: dict[str, Any],
) -> FinanceForecast | None:
    forecast_category = _text_value(payload.get("forecast_category")) or _text_value(
        draft.finance_forecast_category,
    )
    start_month = _month_value(payload.get("start_month")) or _month_value(
        draft.forecast_start_month,
    )
    if not forecast_category or not start_month:
        return None
    record = FinanceForecast(
        opportunity_id=opportunity_id,
        forecast_category=forecast_category,
        start_month=start_month,
        revenue_to_year_end=_money_value(
            payload.get("revenue_to_year_end")
            if payload.get("revenue_to_year_end") is not None
            else draft.estimated_annual_revenue,
        ),
        estimated_margin=_money_value(
            payload.get("estimated_margin")
            if payload.get("estimated_margin") is not None
            else draft.estimated_gross_margin,
        ),
        margin_percentage=_percentage_value(
            payload.get("margin_percentage")
            if payload.get("margin_percentage") is not None
            else draft.margin_percentage,
        ),
        probability_weighting=_probability_value(
            payload.get("probability_weighting")
            if payload.get("probability_weighting") is not None
            else draft.probability,
        ),
        risk_adjustment=_probability_value(payload.get("risk_adjustment")),
        notes=_text_value(payload.get("notes"))
        or "Created by standing-start AI opportunity research.",
    )
    db.add(record)
    return record


def _persist_executive_action(
    db: Session,
    *,
    opportunity_id: int,
    draft: ResearchOpportunityDraft,
    payload: dict[str, Any],
) -> ExecutiveAction | None:
    recommended_action = _text_value(payload.get("recommended_action")) or _text_value(
        draft.executive_action,
    )
    if not recommended_action:
        return None
    record = ExecutiveAction(
        priority=_text_value(payload.get("priority")) or "Medium",
        category=_text_value(payload.get("category")) or "AI Opportunity Research",
        owner=_text_value(payload.get("owner")) or "Commercial Director",
        due_date=_date_value(payload.get("due_date")) or date.today() + timedelta(days=7),
        related_opportunity_id=opportunity_id,
        commercial_value=_money_value(
            payload.get("commercial_value")
            if payload.get("commercial_value") is not None
            else draft.estimated_total_contract_value,
        ),
        reason=_text_value(payload.get("reason"))
        or "AI research identified a commercial action requiring review.",
        recommended_action=recommended_action,
        status="open",
    )
    db.add(record)
    return record


def _mark_run_failed(db: Session, run_id: int, error_message: str) -> None:
    db.rollback()
    run = db.get(EnrichmentRun, run_id)
    if run is None:
        return
    run.status = "failed"
    run.finished_at = datetime.now(UTC)
    run.error_message = error_message
    db.commit()


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, MissingOpenAIKeyError):
        return "OpenAI is not configured for backend opportunity research."
    if isinstance(exc, InvalidOpenAIJSONError):
        return "OpenAI returned invalid structured JSON for opportunity research."
    return "OpenAI opportunity research request failed."


def _text_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "n/a", "none", "null"}:
        return None
    return text


def _money_value(value: Any) -> float:
    if value is None:
        return 0
    try:
        return round(max(float(value), 0), 2)
    except (TypeError, ValueError):
        return 0


def _percentage_value(value: Any) -> float:
    if value is None:
        return 0
    try:
        return round(max(min(float(value), 100), 0), 2)
    except (TypeError, ValueError):
        return 0


def _probability_value(value: Any) -> float:
    if value is None:
        return 0
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return 0
    if probability > 1:
        probability = probability / 100
    return round(max(min(probability, 1), 0), 4)


def _score_value(value: Any) -> float:
    if value is None:
        return 0
    try:
        return round(max(min(float(value), 100), 0), 2)
    except (TypeError, ValueError):
        return 0


def _date_value(value: Any) -> date | None:
    text = _text_value(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _month_value(value: Any) -> str | None:
    text = _text_value(value)
    if text is None:
        return None
    if len(text) >= 7 and text[4] == "-":
        return text[:7]
    return None


def _calculate_weighted_value(draft: ResearchOpportunityDraft) -> float | None:
    value = _money_value(draft.estimated_total_contract_value)
    probability = _probability_value(draft.probability)
    if value <= 0 or probability <= 0:
        return None
    return round(value * probability, 2)


def _weighted_value_confidence(
    fields_by_name: dict[str, ResearchOpportunityFieldIntelligence],
) -> float:
    value_field = fields_by_name.get("estimated_total_contract_value")
    probability_field = fields_by_name.get("probability")
    if value_field is None or probability_field is None:
        return 0.2
    return round(
        min(value_field.confidence_score, probability_field.confidence_score),
        2,
    )
