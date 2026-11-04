"""Import an LFB workbook snapshot; AFA attendance is not proof of a fault.

The raw workbook is user-supplied. Import is a replace of the local incident
snapshot inside a single transaction. Only non-residential records with a
positive, numeric UPRN are retained; ambiguous address qualifiers are kept so
the analysis can exclude them, not silently promote them to site matches.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterator

from openpyxl import load_workbook
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models.lfb_incident import LfbIncident, LfbImportRun

SOURCE_URL = "https://data.london.gov.uk/dataset/london-fire-brigade-incident-records-em8xy"
DOWNLOAD_URL = "https://data.london.gov.uk/download/em8xy/58m/LFB%20Incident%20data%20from%202024%20onwards.xlsx"
REQUIRED = ("IncidentNumber", "DateOfCall", "IncidentGroup", "StopCodeDescription",
            "PropertyCategory", "PropertyType", "AddressQualifier", "Postcode_district", "UPRN")


@dataclass
class ImportSummary:
    rows_seen: int = 0
    records_imported: int = 0
    rows_excluded: int = 0
    min_date: date | None = None
    max_date: date | None = None
    sha256: str = ""
    already_imported: bool = False


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _uprn(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        value = int(value)
    value = str(value).strip()
    if not value.isdecimal() or len(value) > 20 or int(value) == 0:
        return None
    return value


def _record(row: tuple, indexes: dict[str, int]) -> dict | None:
    def get(name: str):
        index = indexes[name]
        return row[index] if index < len(row) else None

    category = str(get("PropertyCategory") or "").strip()
    uprn = _uprn(get("UPRN"))
    when = get("DateOfCall")
    if isinstance(when, datetime):
        when = when.date()
    incident_number = str(get("IncidentNumber") or "").strip()
    if category.casefold() != "non residential" or not uprn or not isinstance(when, date) or not incident_number:
        return None
    return {
        "incident_number": incident_number,
        "incident_date": when,
        "incident_group": str(get("IncidentGroup") or "").strip(),
        "stop_code_description": str(get("StopCodeDescription") or "").strip(),
        "property_category": category,
        "property_type": str(get("PropertyType") or "").strip(),
        "address_qualifier": str(get("AddressQualifier") or "").strip(),
        "postcode_district": str(get("Postcode_district") or "").strip(),
        "uprn": uprn,
    }


def iter_incidents(path: Path) -> Iterator[dict | None]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if len(workbook.sheetnames) != 1:
            raise ValueError("Expected one incident worksheet in the LFB workbook.")
        rows = workbook[workbook.sheetnames[0]].iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration as exc:
            raise ValueError("LFB workbook is empty.") from exc
        if len(set(name for name in header if name is not None)) != len([name for name in header if name is not None]):
            raise ValueError("LFB workbook contains duplicate headers.")
        try:
            indexes = {name: header.index(name) for name in REQUIRED}
        except ValueError as exc:
            raise ValueError("LFB workbook is missing expected incident columns.") from exc
        for row in rows:
            yield _record(row, indexes)
    finally:
        workbook.close()


def import_workbook(path: Path, db: Session | None = None, *, batch_size: int = 2000,
                    retrieved_at: datetime | None = None, acquisition_method: str = "local_file") -> ImportSummary:
    """Preview with db=None; otherwise replace snapshot atomically, with idempotence.

    Dataset source provenance is based on the operator-supplied file. The hash
    detects unchanged files; it does not authenticate an arbitrary file.
    """
    if not 1 <= batch_size <= 10000:
        raise ValueError("batch_size must be between 1 and 10000")
    if retrieved_at is not None and retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must include a timezone")
    if retrieved_at is not None:
        retrieved_at = retrieved_at.astimezone(UTC)
    if acquisition_method not in {"local_file", "official_download"}:
        raise ValueError("Unrecognised acquisition method")
    summary = ImportSummary(sha256=file_sha256(path))
    if db is not None:
        latest = db.scalar(select(LfbImportRun).where(LfbImportRun.status == "completed").order_by(LfbImportRun.id.desc()).limit(1))
        if latest is not None and latest.sha256 == summary.sha256:
            summary.already_imported = True
            return summary
    run = None
    try:
        if db is not None:
            # Delete in the same transaction as inserts so a failed refresh
            # preserves the previous complete incident snapshot.
            db.execute(delete(LfbIncident))
            run = LfbImportRun(source_url=SOURCE_URL, source_file=path.name[:255], sha256=summary.sha256, retrieved_at=retrieved_at, acquisition_method=acquisition_method,
                status="running", rows_seen=0, records_imported=0, rows_excluded=0)
            db.add(run)
            db.flush()
        batch: list[dict] = []
        for record in iter_incidents(path):
            summary.rows_seen += 1
            if record is None:
                summary.rows_excluded += 1
                continue
            summary.records_imported += 1
            when = record["incident_date"]
            summary.min_date = min(summary.min_date, when) if summary.min_date else when
            summary.max_date = max(summary.max_date, when) if summary.max_date else when
            if db is not None:
                record["import_run_id"] = run.id
                batch.append(record)
                if len(batch) >= batch_size:
                    db.execute(insert(LfbIncident), batch)
                    batch.clear()
        if not summary.rows_seen or not summary.records_imported:
            raise ValueError("Workbook contains no eligible non-residential incidents with a UPRN; no snapshot was applied.")
        if db is not None:
            if batch:
                db.execute(insert(LfbIncident), batch)
            run.status = "completed"
            run.rows_seen = summary.rows_seen
            run.records_imported = summary.records_imported
            run.rows_excluded = summary.rows_excluded
            run.min_date = summary.min_date
            run.max_date = summary.max_date
            db.commit()
    except Exception:
        if db is not None:
            db.rollback()
        raise
    return summary
