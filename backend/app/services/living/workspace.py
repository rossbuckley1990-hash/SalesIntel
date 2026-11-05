from datetime import UTC, date, datetime
from decimal import Decimal
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    BuyerProfile,
    CompetitorProfile,
    EnrichmentRun,
    ExecutiveAction,
    FieldIntelligence,
    Opportunity,
    OpportunityEnrichment,
)
from app.models.living import (
    Asset,
    AuditEvent,
    Decision,
    EvidenceReview,
    Outcome,
    Requirement,
    Scenario,
    Snapshot,
)
from app.schemas.living import DiscoverRequest
from app.services.finance_summary import build_finance_forecast_summary
from app.services.opportunity_intelligence import enrich_opportunities
from app.services.living.actions import action_records
from app.services.living.audit import change, commit_event, record


def require_opportunity(db: Session, opportunity_id: int) -> Opportunity:
    obj = db.get(Opportunity, opportunity_id)
    if obj is None:
        raise HTTPException(404, "Opportunity not found")
    return obj


def latest_fields(db: Session, opportunity_id: int) -> list[FieldIntelligence]:
    fields = db.scalars(
        select(FieldIntelligence)
        .where(
            FieldIntelligence.entity_type == "opportunity",
            FieldIntelligence.entity_id == opportunity_id,
        )
        .order_by(FieldIntelligence.id)
    )
    return list({field.field_name: field for field in fields}.values())


def financial_values(opportunity: Opportunity, fields: list[FieldIntelligence]) -> dict:
    provenance = {field.field_name: field for field in fields}
    result = {}
    for name in [
        "estimated_annual_revenue",
        "estimated_total_contract_value",
        "estimated_gross_margin",
        "margin_percentage",
        "probability",
    ]:
        field = provenance.get(name)
        value = getattr(opportunity, name)
        unknown = (
            field is not None
            and (field.value_type == "unknown" or field.field_value is None)
        ) or (field is None and value == 0)
        result[name] = None if unknown else value
    result["weighted_contract_value"] = (
        None
        if result["estimated_total_contract_value"] is None
        or result["probability"] is None
        else float(
            Decimal(str(result["estimated_total_contract_value"]))
            * Decimal(str(result["probability"]))
        )
    )
    return result


def qualification(
    opportunity: Opportunity, fields: list[FieldIntelligence], today: date | None = None
) -> dict:
    today = today or date.today()
    values = financial_values(opportunity, fields)
    criteria = [
        {
            "label": "Commercial value recorded",
            "passed": values["estimated_annual_revenue"] is not None,
            "basis": "Annual revenue has a recorded value and is not marked unknown.",
        },
        {
            "label": "Delivery fit recorded",
            "passed": opportunity.self_delivery_fit.lower() in {"high", "strong"},
            "basis": f"Recorded delivery fit: {opportunity.self_delivery_fit}. Capacity/accreditations still need evidence.",
        },
        {
            "label": "Margin at least 25%",
            "passed": values["margin_percentage"] is not None
            and values["margin_percentage"] >= 25,
            "basis": "Rule threshold of 25%, subject to Finance approval.",
        },
        {
            "label": "Submission still open",
            "passed": opportunity.submission_deadline is not None
            and opportunity.submission_deadline >= today,
            "basis": f"Recorded deadline: {opportunity.submission_deadline or 'unknown'}.",
        },
    ]
    score = sum(25 for criterion in criteria if criterion["passed"])
    risks = []
    if opportunity.risk_rating.lower() in {"red", "high", "amber", "medium"}:
        risks.append(f"Recorded commercial risk: {opportunity.risk_rating}.")
    if not criteria[0]["passed"]:
        risks.append("Annual revenue is missing; financial size cannot be confirmed.")
    if not criteria[1]["passed"]:
        risks.append("Delivery capability has not been established.")
    if not criteria[2]["passed"]:
        risks.append("Margin is below the review threshold or remains unknown.")
    if not criteria[3]["passed"]:
        risks.append("Submission date is missing or has passed.")
    gaps = [f.field_name.replace("_", " ") for f in fields if f.value_type == "unknown"]
    recommendation = (
        "Investigate before commitment"
        if score < 75 or opportunity.risk_rating.lower() in {"red", "high"}
        else "Consider pursuit after evidence review"
    )
    return {
        "score": score,
        "criteria": criteria,
        "risks": risks,
        "gaps": gaps,
        "recommendation": recommendation,
        "method": "Four disclosed checks, 25 points each. Decision support only; no automatic approval.",
    }


def opportunity_detail(db: Session, opportunity_id: int) -> dict:
    opportunity = require_opportunity(db, opportunity_id)
    fields = latest_fields(db, opportunity_id)
    reviews = {
        r.field_id: record(r)
        for r in db.scalars(select(EvidenceReview).order_by(EvidenceReview.id))
    }
    now = datetime.now(UTC)
    evidence = []
    for field in fields:
        payload = record(field)
        updated = (
            field.updated_at.replace(tzinfo=UTC)
            if field.updated_at.tzinfo is None
            else field.updated_at
        )
        payload["stale"] = (now - updated).days > 30
        payload["review"] = reviews.get(field.id)
        evidence.append(payload)
    enrichment = db.scalar(
        select(OpportunityEnrichment)
        .where(OpportunityEnrichment.opportunity_id == opportunity_id)
        .order_by(OpportunityEnrichment.id.desc())
    )
    buyer = db.scalar(
        select(BuyerProfile).where(BuyerProfile.buyer_name == opportunity.buyer_name)
    )
    return {
        "opportunity": enrich_opportunities([opportunity])[0].model_dump(mode="json"),
        "financials": financial_values(opportunity, fields),
        "evidence": evidence,
        "qualification": qualification(opportunity, fields),
        "enrichment": record(enrichment) if enrichment else None,
        "buyer": record(buyer) if buyer else None,
        "actions": action_records(db, opportunity_id),
        "decisions": [
            record(d)
            for d in db.scalars(
                select(Decision)
                .where(Decision.opportunity_id == opportunity_id)
                .order_by(Decision.id.desc())
            )
        ],
        "requirements": [
            record(r)
            for r in db.scalars(
                select(Requirement).where(Requirement.opportunity_id == opportunity_id)
            )
        ],
        "scenarios": [
            record(s)
            for s in db.scalars(
                select(Scenario)
                .where(Scenario.opportunity_id == opportunity_id)
                .order_by(Scenario.id.desc())
            )
        ],
        "outcome": next(
            (
                record(o)
                for o in db.scalars(
                    select(Outcome).where(Outcome.opportunity_id == opportunity_id)
                )
            ),
            None,
        ),
    }


def portfolio(db: Session) -> list[dict]:
    opportunities = list(db.scalars(select(Opportunity).order_by(Opportunity.id)))
    all_fields: dict[int, dict[str, FieldIntelligence]] = {}
    for f in db.scalars(
        select(FieldIntelligence)
        .where(FieldIntelligence.entity_type == "opportunity")
        .order_by(FieldIntelligence.id)
    ):
        all_fields.setdefault(f.entity_id, {})[f.field_name] = f
    enriched = enrich_opportunities(opportunities)
    output = []
    for opportunity, enriched_opportunity in zip(opportunities, enriched, strict=True):
        fields = list(all_fields.get(opportunity.id, {}).values())
        output.append(
            {
                **enriched_opportunity.model_dump(mode="json"),
                "financials": financial_values(opportunity, fields),
                "evidence_count": len(fields),
                "unknown_count": sum(f.value_type == "unknown" for f in fields),
                "qualification": qualification(opportunity, fields),
            }
        )
    return output


def snapshot_payload(db: Session) -> dict:
    return {
        "opportunities": portfolio(db),
        "finance": build_finance_forecast_summary(db).model_dump(mode="json"),
    }


def snapshot_diff(previous: Snapshot | None, current: Snapshot | None) -> dict:
    if previous is None or current is None:
        return {
            "previous": None,
            "current": record(current) if current else None,
            "changes": [],
            "forecast_movement": None,
            "message": "Two explicitly accepted snapshots are needed to show movement.",
        }
    old = {o["id"]: o for o in previous.payload["opportunities"]}
    new = {o["id"]: o for o in current.payload["opportunities"]}
    changes = []
    watched = [
        "stage",
        "submission_deadline",
        "forecast_start_month",
        "risk_rating",
        "self_delivery_fit",
        "owner",
    ]
    for oid in old.keys() | new.keys():
        if oid not in old or oid not in new:
            item = new.get(oid) or old[oid]
            changes.append(
                {
                    "opportunity_id": oid,
                    "name": item["name"],
                    "field": "record",
                    "before": "present" if oid in old else None,
                    "after": "present" if oid in new else None,
                }
            )
            continue
        for field in watched:
            if old[oid].get(field) != new[oid].get(field):
                changes.append(
                    {
                        "opportunity_id": oid,
                        "name": new[oid]["name"],
                        "field": field,
                        "before": old[oid].get(field),
                        "after": new[oid].get(field),
                    }
                )
        for field in [
            "estimated_annual_revenue",
            "estimated_gross_margin",
            "margin_percentage",
            "probability",
        ]:
            before = old[oid]["financials"].get(field)
            after = new[oid]["financials"].get(field)
            if before != after:
                changes.append(
                    {
                        "opportunity_id": oid,
                        "name": new[oid]["name"],
                        "field": field,
                        "before": before,
                        "after": after,
                    }
                )
    return {
        "previous": {k: v for k, v in record(previous).items() if k != "payload"},
        "current": {k: v for k, v in record(current).items() if k != "payload"},
        "changes": changes,
        "forecast_movement": round(
            current.payload["finance"]["forecast_to_financial_year_end"]
            - previous.payload["finance"]["forecast_to_financial_year_end"],
            2,
        ),
        "message": "Comparison of accepted local snapshots. Not an overnight or live-market claim.",
    }


def workspace(db: Session) -> dict:
    opportunities = portfolio(db)
    snapshots = list(db.scalars(select(Snapshot).order_by(Snapshot.id.desc()).limit(2)))
    assets = [
        record(a) for a in db.scalars(select(Asset).order_by(Asset.id.desc()).limit(60))
    ]
    for a in assets:
        a.pop("content")
    latest_event = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.undone.is_(False), AuditEvent.action != "undo")
        .order_by(AuditEvent.id.desc())
    )
    actions = action_records(db)
    active = [
        o
        for o in opportunities
        if o["stage"].lower() not in {"won", "lost", "qualified out"}
    ]
    totals = {}
    for field in [
        "estimated_total_contract_value",
        "weighted_contract_value",
        "estimated_gross_margin",
    ]:
        values = [o["financials"][field] for o in active]
        totals[field] = {
            "value": float(
                sum((Decimal(str(v)) for v in values if v is not None), Decimal(0))
            ),
            "unknown": sum(v is None for v in values),
        }
    return {
        "mode": "synthetic" if get_settings().app_env == "demo" else "local",
        "as_of": datetime.now(UTC).isoformat(),
        "notice": (
            "Synthetic demonstration • no live external feeds"
            if get_settings().app_env == "demo"
            else "Local workspace • unauthenticated review records"
        ),
        "opportunities": opportunities,
        "actions": actions,
        "assets": assets,
        "outcomes": [record(o) for o in db.scalars(select(Outcome))],
        "buyers": [record(b) for b in db.scalars(select(BuyerProfile))],
        "competitors": [record(c) for c in db.scalars(select(CompetitorProfile))],
        "finance": build_finance_forecast_summary(db).model_dump(mode="json"),
        "pulse": totals,
        "changes": snapshot_diff(
            snapshots[1] if len(snapshots) > 1 else None,
            snapshots[0] if snapshots else None,
        ),
        "last_event": (
            {"id": latest_event.id, "action": latest_event.action}
            if latest_event
            else None
        ),
        "connector_status": "Market-data refresh uses placeholder connectors. The false-alarm sensor uses an imported public snapshot when available.",
    }


def discover(db: Session, request: DiscoverRequest) -> dict:
    query = request.query.lower()
    if request.create_draft:
        opportunity = Opportunity(
            name=request.query[:255],
            buyer_name=request.buyer,
            sector=request.sector,
            region=request.region,
            owner=request.owner,
            source_type="User question — unverified",
            stage="Qualification",
            risk_rating="Unknown",
            self_delivery_fit="Unknown",
            recommended_action="Validate the buyer, scope, procurement route and financial assumptions.",
        )
        db.add(opportunity)
        changes = [change(db, opportunity)]
        for key in [
            "estimated_annual_revenue",
            "estimated_total_contract_value",
            "estimated_gross_margin",
            "margin_percentage",
            "probability",
            "self_delivery_fit",
        ]:
            field = FieldIntelligence(
                entity_type="opportunity",
                entity_id=opportunity.id,
                field_name=key,
                field_value=None,
                value_type="unknown",
                confidence_score=0,
                rationale="The user's question does not substantiate this field.",
                source_titles=["User discovery question"],
                source_urls=[],
                needs_user_confirmation=True,
                recommended_next_step="Obtain and review a source before entering a value.",
            )
            db.add(field)
            changes.append(change(db, field))
        run = EnrichmentRun(
            run_type="local_discovery",
            status="completed",
            user_query=request.query,
            opportunity_id=opportunity.id,
            model_used="deterministic-local-v1",
            search_performed=False,
            sources_checked=[],
            records_created=1,
            finished_at=datetime.now(UTC),
        )
        db.add(run)
        changes.append(change(db, run))
        commit_event(db, "Create unverified opportunity", request.owner, changes)
        return {
            "matches": [opportunity.id],
            "created": True,
            "explanation": "Saved your question as an unverified draft. No company, contract, financial value or external evidence has been invented.",
            "intent": "opportunities",
        }
    items = portfolio(db)
    stop = {
        "find",
        "show",
        "which",
        "what",
        "where",
        "the",
        "for",
        "and",
        "are",
        "our",
        "with",
        "most",
        "likely",
        "provide",
        "opportunities",
        "opportunity",
        "five",
        "biggest",
        "this",
        "next",
        "currently",
        "have",
        "can",
        "to",
        "in",
        "of",
        "at",
        "is",
        "a",
    }
    tokens = [w for w in re.findall(r"[a-z]+", query) if w not in stop and len(w) > 2]
    education = any(w in query for w in ["universit", "education", "campus"])
    geography = next(
        (
            g
            for g in ["yorkshire", "london", "midlands", "scotland", "wales"]
            if g in query
        ),
        None,
    )
    at_risk = "risk" in query
    self_delivery = (
        "self-deliver" in query or "subcontract" in query or "missing margin" in query
    )
    gaps = "missing" in query and ("evidence" in query or "capability" in query)
    today = date.today()
    quarter = (today.month - 1) // 3
    quarter_start = date(today.year, quarter * 3 + 1, 1)
    quarter_end = (
        date(today.year + 1, 1, 1)
        if quarter == 3
        else date(today.year, quarter * 3 + 4, 1)
    )
    this_quarter = "this quarter" in query
    scored = []
    for o in items:
        haystack = f"{o['name']} {o['buyer_name']} {o['sector']} {o['region']} {o['recommended_action']}".lower()
        if education and o["sector"].lower() not in {"education", "higher education"}:
            continue
        if geography and geography not in o["region"].lower():
            continue
        if at_risk and o["risk_rating"].lower() not in {"red", "high"}:
            continue
        if gaps and o["unknown_count"] == 0:
            continue
        if self_delivery and o["self_delivery_fit"].lower() not in {
            "high",
            "strong",
            "medium",
            "moderate",
        }:
            continue
        if this_quarter and (
            not o["submission_deadline"]
            or not quarter_start.isoformat()
            <= o["submission_deadline"]
            < quarter_end.isoformat()
        ):
            continue
        score = sum(1 for t in tokens if t in haystack)
        if score or education or at_risk or self_delivery or gaps:
            scored.append(
                (score, o["financials"]["weighted_contract_value"] or -1, o["id"])
            )
    scored.sort(
        key=(lambda row: (row[1], row[0], row[2])) if "biggest" in query else None,
        reverse=True,
    )
    intent = (
        "finance"
        if "forecast" in query
        else (
            "assets"
            if any(w in query for w in ["briefing", "meeting", "leadership"])
            else "selfDelivery" if self_delivery else "opportunities"
        )
    )
    return {
        "matches": [
            i[2] for i in scored[: 5 if "five" in query or "top 5" in query else 20]
        ],
        "created": False,
        "explanation": f"Searched {len(items)} permitted local opportunity records. Ranked by matching terms, then recorded weighted contract value. External sources were not contacted. {"This quarter uses recorded submission deadlines in the current calendar quarter." if this_quarter else ""}",
        "intent": intent,
    }
