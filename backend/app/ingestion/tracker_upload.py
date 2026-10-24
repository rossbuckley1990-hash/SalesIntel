from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Opportunity
from app.schemas import (
    TrackerImportSummary,
    TrackerRecordReference,
    TrackerValidationError,
)

MAX_TRACKER_UPLOAD_BYTES = 5 * 1024 * 1024

FIELD_ALIASES: dict[str, set[str]] = {
    "name": {
        "opportunity",
        "opportunity name",
        "opportunity title",
        "project",
        "project name",
        "name",
        "title",
    },
    "buyer_name": {
        "buyer",
        "buyer client",
        "buyer name",
        "client",
        "client name",
        "customer",
        "customer name",
        "prospect",
    },
    "sector": {"sector", "market", "vertical"},
    "region": {"region", "area", "geography", "location"},
    "stage": {"stage", "status", "stage status", "pipeline stage", "bid stage"},
    "owner": {"owner", "sales owner", "account owner", "bdm", "opportunity owner"},
    "estimated_revenue": {
        "estimated revenue",
        "estimated value",
        "contract value",
        "estimated contract value",
        "total contract value",
        "tcv",
        "value",
        "revenue",
    },
    "estimated_annual_revenue": {
        "annual revenue",
        "estimated annual revenue",
        "annualised revenue",
        "yearly revenue",
    },
    "estimated_margin": {
        "estimated margin",
        "gross margin",
        "estimated gross margin",
        "gm",
        "margin value",
    },
    "margin_percentage": {
        "margin",
        "margin pct",
        "margin percentage",
        "margin percent",
        "gm pct",
        "gm percentage",
        "gross margin percentage",
        "gross margin percent",
    },
    "probability": {
        "probability",
        "probability pct",
        "probability percentage",
        "win probability",
        "chance",
    },
    "submission_deadline": {
        "deadline",
        "submission deadline",
        "tender deadline",
        "bid deadline",
        "return date",
    },
    "forecast_start_month": {
        "forecast start month",
        "forecast month",
        "start month",
        "forecast start",
        "start date",
    },
    "discipline": {"discipline", "service line", "work type", "trade"},
    "comments": {"comments", "comment", "notes", "note", "recommended action", "next action"},
    "source": {"source", "source type", "origin"},
    "self_delivery_fit": {"self delivery fit", "self-delivery fit", "delivery fit"},
    "risk_rating": {"risk", "risk rating", "commercial risk"},
    "strategic_fit_score": {"strategic fit", "strategic fit score", "fit score"},
    "bid_no_bid_recommendation": {
        "bid no bid",
        "bid/no-bid",
        "bid no bid recommendation",
        "recommendation",
    },
}

REQUIRED_FIELDS = {
    "name": "opportunity name",
    "buyer_name": "buyer/client",
}


class TrackerUploadError(ValueError):
    pass


class UnsupportedTrackerFormatError(TrackerUploadError):
    pass


class TrackerFileTooLargeError(TrackerUploadError):
    pass


@dataclass(frozen=True)
class ParsedTrackerFile:
    rows: list[dict[str, Any]]
    header_map: dict[str, str]


def import_tracker_upload(
    db: Session,
    *,
    filename: str,
    content: bytes,
    max_bytes: int = MAX_TRACKER_UPLOAD_BYTES,
) -> TrackerImportSummary:
    if len(content) > max_bytes:
        raise TrackerFileTooLargeError(
            f"Tracker upload exceeds the {_format_upload_limit(max_bytes)} limit."
        )

    parsed_file = parse_tracker_file(filename=filename, content=content)
    rows_received = len(parsed_file.rows)
    missing_required_fields = [
        label
        for canonical_field, label in REQUIRED_FIELDS.items()
        if canonical_field not in parsed_file.header_map.values()
    ]
    if missing_required_fields:
        return TrackerImportSummary(
            rows_received=rows_received,
            rows_imported=0,
            rows_skipped=rows_received,
            validation_errors=[
                TrackerValidationError(
                    row_number=None,
                    field="headers",
                    message=(
                        "Missing required column(s): "
                        + ", ".join(missing_required_fields)
                    ),
                )
            ],
            created_records=[],
            updated_records=[],
        )

    created_records: list[TrackerRecordReference] = []
    updated_records: list[TrackerRecordReference] = []
    validation_errors: list[TrackerValidationError] = []
    skipped_rows = 0

    for index, raw_row in enumerate(parsed_file.rows, start=2):
        mapped_row = _canonical_row(raw_row, parsed_file.header_map)
        row_errors = _validate_row(mapped_row, row_number=index)
        if row_errors:
            validation_errors.extend(row_errors)
            skipped_rows += 1
            continue

        payload = _opportunity_payload(mapped_row)
        opportunity = _find_existing_opportunity(
            db,
            name=payload["name"],
            buyer_name=payload["buyer_name"],
        )
        if opportunity is None:
            opportunity = Opportunity(**_payload_with_create_defaults(payload))
            db.add(opportunity)
            db.flush()
            created_records.append(_record_reference(opportunity))
        else:
            _apply_update(opportunity, payload)
            db.flush()
            updated_records.append(_record_reference(opportunity))

    db.commit()
    rows_imported = len(created_records) + len(updated_records)
    return TrackerImportSummary(
        rows_received=rows_received,
        rows_imported=rows_imported,
        rows_skipped=skipped_rows,
        validation_errors=validation_errors,
        created_records=created_records,
        updated_records=updated_records,
    )


def parse_tracker_file(*, filename: str, content: bytes) -> ParsedTrackerFile:
    extension = Path(filename or "").suffix.lower()
    if extension == ".csv":
        rows = _parse_csv(content)
    elif extension == ".xlsx":
        rows = _parse_xlsx(content)
    else:
        raise UnsupportedTrackerFormatError(
            "Unsupported tracker file type. Upload a .csv or .xlsx file."
        )

    headers = list(rows[0].keys()) if rows else []
    return ParsedTrackerFile(rows=rows, header_map=_header_map(headers))


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    text = _decode_csv(content)
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        return []
    return [
        {key or "": value for key, value in row.items()}
        for row in reader
        if not _is_empty_row(row.values())
    ]


def _parse_xlsx(content: bytes) -> list[dict[str, Any]]:
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    worksheet = workbook.active
    rows = list(worksheet.iter_rows(values_only=True))
    if not rows:
        return []

    header_index = _find_header_row_index(rows)
    if header_index is None:
        return []

    headers = ["" if value is None else str(value).strip() for value in rows[header_index]]
    parsed_rows: list[dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        if _is_empty_row(row):
            continue
        parsed_rows.append(
            {
                headers[column_index] if column_index < len(headers) else "": value
                for column_index, value in enumerate(row)
                if column_index < len(headers) and headers[column_index]
            }
        )
    return parsed_rows


def _format_upload_limit(max_bytes: int) -> str:
    limit_mb = max_bytes / (1024 * 1024)
    return f"{limit_mb:g}MB"


def _find_header_row_index(rows: list[tuple[Any, ...]]) -> int | None:
    for index, row in enumerate(rows):
        if not _is_empty_row(row):
            return index
    return None


def _decode_csv(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def _header_map(headers: list[str]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for header in headers:
        normalised_header = _normalise_header(header)
        for canonical_field, aliases in FIELD_ALIASES.items():
            if normalised_header in aliases and header not in mapped:
                mapped[header] = canonical_field
                break
    return mapped


def _canonical_row(
    row: dict[str, Any],
    header_map: dict[str, str],
) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    for header, value in row.items():
        canonical_field = header_map.get(header)
        if canonical_field and not _is_blank(value):
            canonical[canonical_field] = value
    return canonical


def _validate_row(
    row: dict[str, Any],
    *,
    row_number: int,
) -> list[TrackerValidationError]:
    errors: list[TrackerValidationError] = []
    for field, label in REQUIRED_FIELDS.items():
        if _is_blank(row.get(field)):
            errors.append(
                TrackerValidationError(
                    row_number=row_number,
                    field=label,
                    message=f"Row is missing required {label}.",
                )
            )

    for field in [
        "estimated_revenue",
        "estimated_annual_revenue",
        "estimated_margin",
        "strategic_fit_score",
    ]:
        if field in row and _parse_money(row[field]) is None:
            errors.append(
                TrackerValidationError(
                    row_number=row_number,
                    field=field,
                    message=f"Could not parse numeric value: {row[field]!r}.",
                )
            )

    if "margin_percentage" in row and _parse_percentage_points(row["margin_percentage"]) is None:
        errors.append(
            TrackerValidationError(
                row_number=row_number,
                field="margin %",
                message=f"Could not parse margin percentage: {row['margin_percentage']!r}.",
            )
        )
    if "probability" in row and _parse_probability(row["probability"]) is None:
        errors.append(
            TrackerValidationError(
                row_number=row_number,
                field="probability",
                message=f"Could not parse probability: {row['probability']!r}.",
            )
        )
    if "submission_deadline" in row and _parse_date(row["submission_deadline"]) is None:
        errors.append(
            TrackerValidationError(
                row_number=row_number,
                field="deadline",
                message=f"Could not parse deadline: {row['submission_deadline']!r}.",
            )
        )
    if "forecast_start_month" in row and _parse_forecast_month(row["forecast_start_month"]) is None:
        errors.append(
            TrackerValidationError(
                row_number=row_number,
                field="forecast start month",
                message=(
                    "Could not parse forecast start month: "
                    f"{row['forecast_start_month']!r}."
                ),
            )
        )
    return errors


def _opportunity_payload(row: dict[str, Any]) -> dict[str, Any]:
    total_contract_value = _parse_money(row.get("estimated_revenue")) or 0
    annual_revenue = (
        _parse_money(row.get("estimated_annual_revenue"))
        if "estimated_annual_revenue" in row
        else total_contract_value
    )
    if annual_revenue is None:
        annual_revenue = total_contract_value

    estimated_margin = _parse_money(row.get("estimated_margin")) or 0
    margin_percentage = _parse_percentage_points(row.get("margin_percentage"))
    if margin_percentage is None and total_contract_value and estimated_margin:
        margin_percentage = round((estimated_margin / total_contract_value) * 100, 2)
    if margin_percentage is None:
        margin_percentage = 0
    if estimated_margin == 0 and total_contract_value and margin_percentage:
        estimated_margin = round(total_contract_value * (margin_percentage / 100), 2)

    probability = _parse_probability(row.get("probability")) or 0
    comments = _text(row.get("comments"))
    discipline = _text(row.get("discipline"))
    recommended_action = comments
    if discipline and not recommended_action:
        recommended_action = f"Uploaded discipline: {discipline}."

    return {
        "name": _text(row.get("name")),
        "buyer_name": _text(row.get("buyer_name")),
        "sector": _text(row.get("sector")),
        "region": _text(row.get("region")),
        "source_type": _text(row.get("source")),
        "stage": _text(row.get("stage")),
        "owner": _text(row.get("owner")),
        "estimated_annual_revenue": annual_revenue,
        "estimated_total_contract_value": total_contract_value,
        "estimated_gross_margin": estimated_margin,
        "margin_percentage": margin_percentage,
        "probability": probability,
        "weighted_value": round(total_contract_value * probability, 2),
        "submission_deadline": _parse_date(row.get("submission_deadline")),
        "forecast_start_month": _parse_forecast_month(row.get("forecast_start_month")),
        "self_delivery_fit": _text(row.get("self_delivery_fit")),
        "risk_rating": _text(row.get("risk_rating")),
        "strategic_fit_score": _parse_money(row.get("strategic_fit_score")) or 0,
        "bid_no_bid_recommendation": _text(row.get("bid_no_bid_recommendation")),
        "recommended_action": recommended_action,
    }


def _payload_with_create_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "sector": payload["sector"] or "Unknown",
        "region": payload["region"] or "Unknown",
        "source_type": payload["source_type"] or "tracker_upload",
        "stage": payload["stage"] or "Market signal",
        "owner": payload["owner"] or "Unassigned",
        "self_delivery_fit": payload["self_delivery_fit"] or "unknown",
        "risk_rating": payload["risk_rating"] or "unknown",
        "bid_no_bid_recommendation": (
            payload["bid_no_bid_recommendation"] or "review_required"
        ),
    }


def _apply_update(opportunity: Opportunity, payload: dict[str, Any]) -> None:
    defaults = _payload_with_create_defaults(payload)
    for field, value in defaults.items():
        if value is not None and not (isinstance(value, str) and value == ""):
            setattr(opportunity, field, value)


def _find_existing_opportunity(
    db: Session,
    *,
    name: str,
    buyer_name: str,
) -> Opportunity | None:
    return db.scalar(
        select(Opportunity).where(
            func.lower(Opportunity.name) == name.lower(),
            func.lower(Opportunity.buyer_name) == buyer_name.lower(),
        )
    )


def _record_reference(opportunity: Opportunity) -> TrackerRecordReference:
    return TrackerRecordReference(
        id=opportunity.id,
        name=opportunity.name,
        buyer_name=opportunity.buyer_name,
    )


def _parse_money(value: Any) -> float | None:
    if _is_blank(value):
        return None
    if isinstance(value, int | float):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if cleaned in {"", "-", "."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_percentage_points(value: Any) -> float | None:
    if _is_blank(value):
        return None
    if isinstance(value, int | float):
        number = float(value)
    else:
        cleaned = re.sub(r"[^0-9.\-]", "", str(value))
        if cleaned in {"", "-", "."}:
            return None
        try:
            number = float(cleaned)
        except ValueError:
            return None
    if 0 <= number <= 1:
        return round(number * 100, 2)
    return number


def _parse_probability(value: Any) -> float | None:
    if _is_blank(value):
        return None
    parsed = _parse_percentage_points(value)
    if parsed is None:
        return None
    if parsed < 0:
        return None
    return round(min(parsed / 100, 1), 4)


def _parse_date(value: Any) -> date | None:
    if _is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    for date_format in [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def _parse_forecast_month(value: Any) -> str | None:
    if _is_blank(value):
        return None
    if isinstance(value, datetime | date):
        return f"{value.year}-{value.month:02d}"

    text = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return text
    for date_format in [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%b %Y",
        "%B %Y",
        "%m/%Y",
    ]:
        try:
            parsed = datetime.strptime(text, date_format)
            return f"{parsed.year}-{parsed.month:02d}"
        except ValueError:
            continue
    return None


def _normalise_header(value: str) -> str:
    cleaned = value.strip().lower().replace("&", " and ")
    cleaned = re.sub(r"[%/()_-]+", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _text(value: Any) -> str:
    if _is_blank(value):
        return ""
    return str(value).strip()


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and value.strip() == ""


def _is_empty_row(values: Any) -> bool:
    return all(_is_blank(value) for value in values)
