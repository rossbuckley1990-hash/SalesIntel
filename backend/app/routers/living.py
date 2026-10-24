import json
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ExecutiveAction, FieldIntelligence
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
from app.routers.upload import (
    _read_upload_with_limit,
    _validate_tracker_upload_metadata,
)
from app.ingestion.tracker_upload import (
    TrackerFileTooLargeError,
    UnsupportedTrackerFormatError,
)
from app.schemas.living import (
    TenderExtract,
    TenderCapture,
    ActionRequest,
    ActionUpdate,
    AssetRequest,
    AssetReview,
    DecisionRequest,
    DiscoverRequest,
    OutcomeUpdate,
    RequirementInput,
    ReviewRequest,
    SaveScenario,
    ScenarioInput,
    SnapshotRequest,
)
from app.services.living.actions import action_records, save_details
from app.services.living.assets import create_asset
from app.services.living.audit import change, commit_event, record, undo_latest
from app.services.living.exports import export_docx, export_pdf, export_xlsx
from app.services.living.finance import calculate_scenario
from app.services.living.imports import commit_import, preview_import
from app.services.living.workspace import (
    discover,
    latest_fields,
    opportunity_detail,
    qualification,
    require_opportunity,
    snapshot_payload,
    workspace,
)


def local_boundary():
    if get_settings().app_env not in {"local", "test", "demo", "development"}:
        raise HTTPException(
            503,
            "Living workspace requires enterprise identity and roles before deployment beyond local development.",
        )


router = APIRouter(
    prefix="/api/living",
    tags=["living workspace"],
    dependencies=[Depends(local_boundary)],
)


@router.get("/workspace")
def get_workspace(db: Session = Depends(get_db)):
    return workspace(db)


@router.get("/opportunities/{opportunity_id}")
def get_detail(opportunity_id: int, db: Session = Depends(get_db)):
    return opportunity_detail(db, opportunity_id)


@router.post("/discover")
def discover_opportunities(request: DiscoverRequest, db: Session = Depends(get_db)):
    return discover(db, request)


@router.post("/opportunities/{opportunity_id}/decisions")
def decide(
    opportunity_id: int, request: DecisionRequest, db: Session = Depends(get_db)
):
    opportunity = require_opportunity(db, opportunity_id)
    decision = Decision(
        opportunity_id=opportunity_id,
        choice=request.choice,
        rationale=request.rationale,
        reviewer=request.reviewer,
        qualification=qualification(opportunity, latest_fields(db, opportunity_id)),
    )
    db.add(decision)
    changes = [change(db, decision)]
    action = ExecutiveAction(
        priority="high" if opportunity.risk_rating.lower() == "red" else "medium",
        category="Pursuit decision",
        owner=request.owner,
        due_date=request.due_date,
        related_opportunity_id=opportunity_id,
        reason=request.rationale,
        recommended_action=request.action,
        status="open",
    )
    db.add(action)
    changes.append(change(db, action))
    outcome = db.scalar(select(Outcome).where(Outcome.opportunity_id == opportunity_id))
    before = record(outcome) if outcome else None
    if outcome is None:
        outcome = Outcome(opportunity_id=opportunity_id, owner=request.owner)
        db.add(outcome)
    if outcome.stage not in {"won", "realised"}:
        outcome.stage = (
            "approved"
            if request.choice == "pursue"
            else "investigating" if request.choice == "investigate" else "identified"
        )
    outcome.action_id = action.id
    outcome.decision_id = decision.id
    outcome.owner = request.owner
    outcome.due_date = request.due_date
    outcome.assumptions = request.rationale
    changes.append(change(db, outcome, before))
    event = commit_event(
        db,
        "Record pursuit decision",
        request.reviewer,
        changes,
        "Local review only; actor identity is not authenticated.",
    )
    return {
        "decision": record(decision),
        "action": record(action),
        "outcome": record(outcome),
        "event_id": event.id,
    }


@router.post("/evidence/{field_id}/reviews")
def review_evidence(
    field_id: int, request: ReviewRequest, db: Session = Depends(get_db)
):
    if db.get(FieldIntelligence, field_id) is None:
        raise HTTPException(404, "Evidence field not found")
    review = EvidenceReview(field_id=field_id, **request.model_dump())
    db.add(review)
    commit_event(
        db,
        "Review evidence",
        request.reviewer,
        [change(db, review)],
        "Review does not change source provenance or turn assumptions into facts.",
    )
    return record(review)


@router.post("/actions")
def add_action(request: ActionRequest, db: Session = Depends(get_db)):
    require_opportunity(db, request.opportunity_id)
    action = ExecutiveAction(
        priority=request.priority,
        category="Pursuit action",
        owner=request.owner,
        due_date=request.due_date,
        related_opportunity_id=request.opportunity_id,
        reason=request.reason,
        recommended_action=request.action,
        status="open",
    )
    db.add(action)
    changes = [change(db, action), save_details(db, action, request.depends_on)]
    commit_event(db, "Create pursuit action", request.owner, changes)
    return record(action)


@router.patch("/actions/{action_id}")
def update_action(action_id: int, request: ActionUpdate, db: Session = Depends(get_db)):
    action = db.get(ExecutiveAction, action_id)
    if action is None:
        raise HTTPException(404, "Action not found")
    if action.status != request.expected_status:
        raise HTTPException(409, "Action status changed. Refresh before updating.")
    before = record(action)
    action.owner = request.owner
    action.due_date = request.due_date
    action.status = request.status
    action.recommended_action = request.action
    dependencies = request.depends_on
    if dependencies is None:
        dependencies = next(
            a["depends_on"] for a in action_records(db) if a["id"] == action.id
        )
    changes = [
        change(db, action, before),
        save_details(db, action, dependencies, request.completion_evidence),
    ]
    commit_event(
        db, "Update pursuit action", request.owner, changes, request.completion_evidence
    )
    return record(action)


@router.post("/scenarios/calculate")
def calculate(request: ScenarioInput):
    return calculate_scenario(request)


@router.post("/scenarios")
def save_scenario(request: SaveScenario, db: Session = Depends(get_db)):
    require_opportunity(db, request.opportunity_id)
    result = calculate_scenario(request.inputs)
    scenario = Scenario(
        opportunity_id=request.opportunity_id,
        name=request.name,
        owner=request.owner,
        assumptions=request.inputs.model_dump(mode="json"),
        result=result,
        expected_contribution=Decimal(result["proposed"]["expected_contribution"]),
    )
    db.add(scenario)
    commit_event(db, "Save financial scenario", request.owner, [change(db, scenario)])
    return record(scenario)


@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db)):
    return [
        record(s) for s in db.scalars(select(Scenario).order_by(Scenario.id.desc()))
    ]


@router.post("/snapshots")
def save_snapshot(request: SnapshotRequest, db: Session = Depends(get_db)):
    snapshot = Snapshot(
        label=request.label, reviewer=request.reviewer, payload=snapshot_payload(db)
    )
    db.add(snapshot)
    commit_event(
        db, "Accept portfolio snapshot", request.reviewer, [change(db, snapshot)]
    )
    return {k: v for k, v in record(snapshot).items() if k != "payload"}


@router.get("/snapshots")
def list_snapshots(db: Session = Depends(get_db)):
    return [
        record(s)
        for s in db.scalars(select(Snapshot).order_by(Snapshot.id.desc()).limit(40))
    ]


@router.post("/assets")
def generate_asset(request: AssetRequest, db: Session = Depends(get_db)):
    return record(create_asset(db, request))


@router.get("/assets/{asset_id}")
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    return record(asset)


@router.patch("/assets/{asset_id}/review")
def review_asset(asset_id: int, request: AssetReview, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    before = record(asset)
    asset.review_status = request.status
    asset.reviewer = request.reviewer
    commit_event(
        db, "Review commercial asset", request.reviewer, [change(db, asset, before)]
    )
    return record(asset)


@router.get("/assets/{asset_id}/export/{format}")
def download_asset(asset_id: int, format: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    exporters = {
        "pdf": (export_pdf, "application/pdf"),
        "docx": (
            export_docx,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        "xlsx": (
            export_xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
    if format not in exporters:
        raise HTTPException(400, "Choose PDF, DOCX or XLSX.")
    exporter, media = exporters[format]
    return Response(
        exporter(asset),
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="misi-{asset.kind}-{asset.id}-v{asset.version}.{format}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/opportunities/{opportunity_id}/outcome")
def save_outcome(
    opportunity_id: int, request: OutcomeUpdate, db: Session = Depends(get_db)
):
    require_opportunity(db, opportunity_id)
    outcome = db.scalar(select(Outcome).where(Outcome.opportunity_id == opportunity_id))
    before = record(outcome) if outcome else None
    if outcome is None:
        outcome = Outcome(opportunity_id=opportunity_id, owner=request.owner)
        db.add(outcome)
    if request.stage == "approved" and not db.scalar(
        select(Decision).where(
            Decision.opportunity_id == opportunity_id, Decision.choice == "pursue"
        )
    ):
        raise HTTPException(
            422, "Record an explicit pursuit decision before moving value to approved."
        )
    for key, value in request.model_dump().items():
        setattr(outcome, key, value)
    commit_event(
        db,
        "Update commercial outcome",
        request.owner,
        [change(db, outcome, before)],
        request.completion_evidence,
    )
    return record(outcome)


@router.post("/opportunities/{opportunity_id}/requirements")
def add_requirement(
    opportunity_id: int, request: RequirementInput, db: Session = Depends(get_db)
):
    require_opportunity(db, opportunity_id)
    requirement = Requirement(opportunity_id=opportunity_id, **request.model_dump())
    db.add(requirement)
    commit_event(
        db, "Capture tender requirement", request.owner, [change(db, requirement)]
    )
    return record(requirement)


@router.get("/audit")
def audit_log(db: Session = Depends(get_db)):
    return [
        {k: v for k, v in record(e).items() if k != "changes"}
        for e in db.scalars(
            select(AuditEvent).order_by(AuditEvent.id.desc()).limit(100)
        )
    ]


@router.post("/audit/{event_id}/undo")
def undo(event_id: int, db: Session = Depends(get_db)):
    return undo_latest(db, event_id)


@router.post("/imports/preview")
async def import_preview(
    file: UploadFile = File(...),
    mapping: str = Form("{}"),
    db: Session = Depends(get_db),
):
    try:
        filename = _validate_tracker_upload_metadata(file)
        content = await _read_upload_with_limit(file, get_settings().max_upload_bytes)
        parsed_mapping = json.loads(mapping)
        if not isinstance(parsed_mapping, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in parsed_mapping.items()
        ):
            raise ValueError()
        return preview_import(db, filename, content, parsed_mapping)
    except UnsupportedTrackerFormatError as exc:
        raise HTTPException(400, str(exc)) from exc
    except TrackerFileTooLargeError as exc:
        raise HTTPException(413, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "Invalid field mapping.") from exc


@router.post("/imports/{preview_id}/commit")
def import_commit(preview_id: str, db: Session = Depends(get_db)):
    return commit_import(db, preview_id)


@router.post("/requirements/extract")
def extract_requirements(request: TenderExtract):
    # Deterministic source extraction, never a compliance assertion or model call.
    import re

    candidates = []
    for number, line in enumerate(request.text.splitlines(), 1):
        text = line.strip()
        if re.search(r"\b(must|shall|required|mandatory)\b", text, re.I):
            if len(text) > 4000:
                raise HTTPException(
                    422,
                    f"Source line {number} is too long; split it into numbered clauses first.",
                )
            if len(text) >= 10:
                candidates.append(
                    {
                        "requirement": text,
                        "source_reference": f"{request.source_reference} · pasted extract line {number}",
                        "compliance": "unassessed",
                    }
                )
    return {
        "requirements": candidates[:100],
        "total_candidates": len(candidates),
        "method": "Exact lines containing must, shall, required or mandatory. Review completeness against the original source; this is not an exhaustive legal interpretation.",
    }


@router.post("/opportunities/{opportunity_id}/requirements/capture")
def capture_requirements(
    opportunity_id: int, request: TenderCapture, db: Session = Depends(get_db)
):
    require_opportunity(db, opportunity_id)
    changes, rows = [], []
    for item in request.requirements:
        row = Requirement(opportunity_id=opportunity_id, **item.model_dump())
        db.add(row)
        changes.append(change(db, row))
        rows.append(row)
    commit_event(
        db, "Capture reviewed tender extracts", request.requirements[0].owner, changes
    )
    return [record(row) for row in rows]
