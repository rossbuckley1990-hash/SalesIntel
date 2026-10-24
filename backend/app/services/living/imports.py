import hashlib
import json
import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.tracker_upload import (
    FIELD_ALIASES,
    _parse_percentage_points,
    _apply_update,
    _canonical_row,
    _find_existing_opportunity,
    _opportunity_payload,
    _payload_with_create_defaults,
    _validate_row,
    parse_tracker_file,
)
from app.models import FieldIntelligence, Opportunity
from app.models.living import ImportPreview
from app.services.living.audit import change, commit_event, json_value, record


def fingerprint(db: Session) -> str:
    payload = [
        record(o) for o in db.scalars(select(Opportunity).order_by(Opportunity.id))
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def preview_import(
    db: Session, filename: str, content: bytes, mapping: dict[str, str]
) -> dict:
    if Path(filename).suffix.lower() == ".xlsx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 30 * 1024 * 1024:
                    raise HTTPException(413, "Expanded workbook exceeds 30MB.")
        except BadZipFile as exc:
            raise HTTPException(400, "The workbook is not a valid XLSX file.") from exc
    try:
        parsed = parse_tracker_file(filename=filename, content=content)
    except Exception as exc:
        raise HTTPException(
            400, "Could not parse the selected tracker. Check its CSV/XLSX format."
        ) from exc
    if len(parsed.rows) > 5000:
        raise HTTPException(413, "Review imports in batches of at most 5,000 rows.")
    headers = list(parsed.rows[0]) if parsed.rows else []
    header_map = {**parsed.header_map, **mapping}
    if any(
        k not in headers or (v and v not in FIELD_ALIASES) for k, v in mapping.items()
    ):
        raise HTTPException(422, "Mapping contains an unknown column or target field.")
    targets = [v for v in header_map.values() if v]
    if len(set(targets)) != len(targets):
        raise HTTPException(422, "Two columns cannot map to the same target field.")
    rows, errors, seen = [], [], set()
    for index, raw in enumerate(parsed.rows, 2):
        canonical = _canonical_row(raw, header_map)
        row_errors = [
            e.model_dump() for e in _validate_row(canonical, row_number=index)
        ]
        if row_errors:
            errors.extend(row_errors)
            continue
        raw_probability = _parse_percentage_points(canonical.get("probability"))
        if raw_probability is not None and (
            not math.isfinite(raw_probability)
            or raw_probability < 0
            or raw_probability > 100
        ):
            errors.append(
                {
                    "row_number": index,
                    "field": "probability",
                    "message": "Probability must be between 0% and 100%; values are never clamped.",
                }
            )
            continue
        payload = _opportunity_payload(canonical)
        if any(
            isinstance(v, float) and (not math.isfinite(v) or v < 0 or v > 1e12)
            for v in payload.values()
        ):
            errors.append(
                {
                    "row_number": index,
                    "field": "numeric",
                    "message": "Numbers must be finite, non-negative and no greater than one trillion.",
                }
            )
            continue
        if (
            payload.get("probability", 0) > 1
            or payload.get("margin_percentage", 0) > 100
        ):
            errors.append(
                {
                    "row_number": index,
                    "field": "percentage",
                    "message": "Probability and margin must be between 0% and 100%.",
                }
            )
            continue
        if any(
            isinstance(v, str) and len(v) > (2000 if k == "recommended_action" else 255)
            for k, v in payload.items()
        ):
            errors.append(
                {
                    "row_number": index,
                    "field": "text",
                    "message": "A text value is too long.",
                }
            )
            continue
        key = (
            payload["name"].strip().casefold(),
            payload["buyer_name"].strip().casefold(),
        )
        if key in seen:
            errors.append(
                {
                    "row_number": index,
                    "field": "duplicate",
                    "message": "Duplicate opportunity and buyer within this file.",
                }
            )
            continue
        seen.add(key)
        existing = _find_existing_opportunity(
            db, name=payload["name"], buyer_name=payload["buyer_name"]
        )
        aliases = {
            "estimated_revenue": "estimated_total_contract_value",
            "estimated_margin": "estimated_gross_margin",
            "source": "source_type",
            "comments": "recommended_action",
            "discipline": "recommended_action",
        }
        supplied = {aliases.get(k, k) for k in canonical} & payload.keys()
        provenance = {key: "user_provided" for key in supplied}
        finance_fields = {
            "estimated_annual_revenue",
            "estimated_total_contract_value",
            "estimated_gross_margin",
            "margin_percentage",
            "probability",
        }
        for key in payload:
            if key not in supplied and existing is not None:
                payload[key] = getattr(existing, key)
            elif key in finance_fields and key not in supplied:
                payload[key] = 0
                provenance[key] = "unknown"
        # Annual margin can only be derived from an explicitly supplied annual basis.
        if (
            "estimated_gross_margin" not in supplied
            and {"estimated_annual_revenue", "margin_percentage"} <= supplied
        ):
            payload["estimated_gross_margin"] = float(
                (
                    Decimal(str(payload["estimated_annual_revenue"]))
                    * Decimal(str(payload["margin_percentage"]))
                    / 100
                ).quantize(Decimal(".01"))
            )
            provenance["estimated_gross_margin"] = "system_calculated"
        payload["weighted_value"] = round(
            payload["estimated_total_contract_value"] * payload["probability"], 2
        )
        rows.append(
            {
                "row": index,
                "operation": "update" if existing else "create",
                "provenance": provenance,
                "existing_id": existing.id if existing else None,
                "before": record(existing) if existing else None,
                "values": {k: json_value(v) for k, v in payload.items()},
            }
        )
    if not parsed.rows:
        errors.append(
            {"row_number": None, "field": "file", "message": "No data rows were found."}
        )
    preview = ImportPreview(
        id=str(uuid4()),
        filename=Path(filename).name,
        rows=rows,
        errors=errors,
        fingerprint=fingerprint(db),
    )
    db.add(preview)
    db.commit()
    return {
        "id": preview.id,
        "filename": preview.filename,
        "headers": headers,
        "mapping": header_map,
        "fields": list(FIELD_ALIASES),
        "rows": rows,
        "errors": errors,
        "can_commit": bool(rows) and not errors,
        "expires_in_minutes": 30,
    }


def commit_import(db: Session, preview_id: str) -> dict:
    preview = db.get(ImportPreview, preview_id)
    if preview is None:
        raise HTTPException(404, "Import preview not found")
    created_at = (
        preview.created_at.replace(tzinfo=UTC)
        if preview.created_at.tzinfo is None
        else preview.created_at
    )
    if preview.committed or created_at < datetime.now(UTC) - timedelta(minutes=30):
        raise HTTPException(
            409,
            "This preview was already committed or has expired. Preview the file again.",
        )
    if preview.errors or not preview.rows:
        raise HTTPException(422, "Resolve all validation errors before importing.")
    if fingerprint(db) != preview.fingerprint:
        raise HTTPException(
            409,
            "The pipeline changed after preview. Preview again to review current differences.",
        )
    changes = []
    for row in preview.rows:
        payload = dict(row["values"])
        if payload.get("submission_deadline"):
            payload["submission_deadline"] = date.fromisoformat(
                payload["submission_deadline"]
            )
        o = db.get(Opportunity, row["existing_id"]) if row["existing_id"] else None
        before = record(o) if o else None
        if o is None:
            o = Opportunity(**_payload_with_create_defaults(payload))
            db.add(o)
        else:
            _apply_update(o, payload)
        changes.append(change(db, o, before))
        for key, kind in row["provenance"].items():
            value = None if kind == "unknown" else payload[key]
            field = FieldIntelligence(
                entity_type="opportunity",
                entity_id=o.id,
                field_name=key,
                field_value=json_value(value),
                value_type=kind,
                confidence_score=0 if kind == "unknown" else 0.5,
                rationale="Explicitly reviewed tracker import. The import does not independently verify the claim. Missing cells stay unknown; calculated annual margin uses supplied annual revenue × margin percentage.",
                source_titles=[preview.filename + f" row {row['row']}"],
                source_urls=[],
                needs_user_confirmation=True,
                recommended_next_step="Validate against the approved commercial source.",
            )
            db.add(field)
            changes.append(change(db, field))
    before = record(preview)
    preview.committed = True
    changes.append(change(db, preview, before))
    event = commit_event(
        db, "Commit reviewed tracker import", "Local reviewer", changes
    )
    return {"rows_imported": len(preview.rows), "event_id": event.id}
