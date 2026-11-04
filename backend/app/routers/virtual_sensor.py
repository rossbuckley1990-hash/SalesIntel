"""LFB automatic-fire-alarm attendance patterns, not claims of equipment fault.

Counts compare only non-residential, exact-location observations with the same
reported property type. Sites with zero attendances are absent from this data.
"""
from datetime import UTC, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.lfb_incident import LfbImportRun, LfbIncident
from app.models.lfb_inspection_match import LfbInspectionMatch
from app.ingestion.lfb_inspections import SOURCE as INSPECTION_SOURCE

router = APIRouter(prefix="/api/virtual-sensors/false-alarms", tags=["virtual sensors"])
SOURCE_URL = "https://data.london.gov.uk/dataset/london-fire-brigade-incident-records-em8xy"
POLICY_URL = "https://www.london-fire.gov.uk/news/2024-news/october/keeping-communities-safe-london-fire-brigade-introduces-new-policy-which-aims-to-reduce-attendance-at-false-alarms/"
# The policy changed part way through 29 October. Exclude the transition day.
FIRST_FULL_POLICY_DAY = date(2024, 10, 30)
LIMITATIONS = [
    "The source records fire-brigade attendances, not all alarm activations. AFA does not establish a fault or its cause.",
    "From 29 October 2024 London Fire Brigade changed its response to many non-residential alarms; exemptions and hours affect which incidents appear.",
    "The peer mean excludes this site and uses only other sites with at least one recorded attendance in the same property type and period. Sites with zero attendances are absent; estate size, occupancy, operating hours and exposure are unknown. Small peer groups are unreliable.",
    "A UPRN identifies a location, not its occupier, owner, buyer or maintenance supplier. Verify current identity and source context before engagement.",
    "Imported-record dates do not establish complete dataset coverage; site category and source observations can be incomplete or stale. Counts are exploratory, not a probability or evidence of non-compliance, supplier underperformance or buying intent.",
    "Sites are ordered by attendance count, not by verified commercial value or likelihood of purchase.",
    "The workbook's recorded filename and hash identify the imported file; a hash alone does not verify its publisher or completeness. Check it against the official source.",
]


def _window(db: Session) -> tuple[date | None, date | None]:
    earliest, latest = db.execute(
        select(func.min(LfbIncident.incident_date), func.max(LfbIncident.incident_date))
        .join(LfbImportRun, LfbIncident.import_run_id == LfbImportRun.id)
        .where(LfbImportRun.status == "completed")
    ).one()
    if earliest is None or latest is None or latest < FIRST_FULL_POLICY_DAY:
        return None, None
    return max(earliest, latest - timedelta(days=364), FIRST_FULL_POLICY_DAY), latest


def _eligible(start: date, end: date):
    return (
        LfbImportRun.status == "completed",
        LfbIncident.incident_date >= start,
        LfbIncident.incident_date <= end,
        func.lower(func.trim(LfbIncident.incident_group)) == "false alarm",
        func.lower(func.trim(LfbIncident.stop_code_description)) == "afa",
        func.lower(func.trim(LfbIncident.property_category)) == "non residential",
        func.lower(func.trim(LfbIncident.address_qualifier)) == "correct incident location",
        LfbIncident.uprn != "",
        LfbIncident.uprn != "0",
        func.trim(LfbIncident.property_type) != "",
        func.lower(func.trim(LfbIncident.property_type)).not_in(["unknown", "unspecified", "not known", "n/a"]),
    )


def _groups(start: date, end: date):
    # An identifier with conflicting property types is excluded. This avoids
    # counting one UPRN as two sites or attributing an arbitrary peer group.
    return (
        select(
            LfbIncident.uprn.label("uprn"),
            func.min(LfbIncident.property_type).label("property_type"),
            func.count().label("attendances"),
            func.min(LfbIncident.incident_date).label("first_seen"),
            func.max(LfbIncident.incident_date).label("last_seen"),
            func.min(LfbIncident.postcode_district).label("postcode_district"),
            func.count(distinct(LfbIncident.postcode_district)).label("district_count"),
        )
        .join(LfbImportRun, LfbIncident.import_run_id == LfbImportRun.id)
        .where(*_eligible(start, end))
        .group_by(LfbIncident.uprn)
        .having(func.count(distinct(LfbIncident.property_type)) == 1)
        .cte("observed_sites")
    )


def _query(start: date, end: date):
    groups = _groups(start, end)
    # Same time period and reported property type; this is a descriptive mean
    # over observed sites, not a prevalence or a normalised alarm rate.
    cohorts = (
        select(groups.c.property_type, func.count().label("cohort_sites"),
               func.sum(groups.c.attendances).label("cohort_attendances"))
        .group_by(groups.c.property_type)
        .cte("cohorts")
    )
    return groups, select(groups, cohorts.c.cohort_sites, cohorts.c.cohort_attendances).join(
        cohorts, cohorts.c.property_type == groups.c.property_type
    )


def _site(row, start: date, end: date) -> dict:
    district = row.postcode_district if row.district_count == 1 else ""
    brief = (
        f"Investigate non-residential UPRN {row.uprn}, reported property type {row.property_type}"
        f"{f', postcode district {district}' if district else ''}. Public London Fire Brigade data records "
        f"{row.attendances} automatic-fire-alarm false-alarm attendances from {start} to {end}. "
        "Find current public evidence of the site's identity and organisation, plus any relevant fire "
        "maintenance context and an appropriate contact role. Verify that evidence refers to this exact "
        "site; UPRN alone does not identify the occupier or supplier. AFA attendance does not establish "
        "a fault, supplier failure, non-compliance or intent to buy. Distinguish fact from inference."
    )
    peer_count = row.cohort_sites - 1
    peer_mean = round((row.cohort_attendances - row.attendances) / peer_count, 2) if peer_count else None
    return {
        "uprn": row.uprn, "property_type": row.property_type, "postcode_district": district,
        "attendances": row.attendances, "first_seen": row.first_seen, "last_seen": row.last_seen,
        "comparison": {"cohort_sites": peer_count, "mean_attendances": peer_mean},
        "research_brief": brief,
    }


def _context(db: Session, start: date | None, end: date | None) -> dict:
    run = db.scalars(
        select(LfbImportRun).join(LfbIncident, LfbIncident.import_run_id == LfbImportRun.id)
        .where(LfbImportRun.status == "completed").order_by(LfbImportRun.id.desc()).limit(1)
    ).first()
    snapshot = None if run is None else {
        "source_file": run.source_file, "sha256": run.sha256,
        "imported_at": (run.imported_at.replace(tzinfo=UTC) if run.imported_at.utcoffset() is None else run.imported_at), "source_url": run.source_url,
        "acquisition_method": run.acquisition_method,
        "retrieved_at": (run.retrieved_at.replace(tzinfo=UTC) if run.retrieved_at is not None and run.retrieved_at.utcoffset() is None else run.retrieved_at),
        "eligible_min_date": run.min_date, "eligible_max_date": run.max_date,
        "records_imported": run.records_imported,
    }
    return {"period_start": start, "period_end": end, "source_url": SOURCE_URL,
            "policy_url": POLICY_URL, "snapshot": snapshot, "limitations": LIMITATIONS}


@router.get("")
def list_false_alarm_sites(
    limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0),
    property_type: str | None = Query(default=None, max_length=255), db: Session = Depends(get_db),
) -> dict:
    start, end = _window(db)
    if start is None or end is None:
        return {"total": 0, "items": [], **_context(db, None, None)}
    groups, query = _query(start, end)
    filters = [groups.c.attendances >= 2]
    if property_type:
        filters.append(groups.c.property_type == property_type)
    total = db.scalar(select(func.count()).select_from(groups).where(*filters)) or 0
    rows = db.execute(query.where(*filters).order_by(groups.c.attendances.desc(), groups.c.uprn).offset(offset).limit(limit)).all()
    return {"total": total, "items": [_site(row, start, end) for row in rows], **_context(db, start, end)}


def get_site_detail(db: Session, uprn: str, property_type: str | None = None) -> dict:
    start, end = _window(db)
    if start is None or end is None:
        raise HTTPException(status_code=404, detail="No imported post-policy incident data is available.")
    groups, query = _query(start, end)
    filters = [groups.c.uprn == uprn]
    if property_type:
        filters.append(groups.c.property_type == property_type)
    row = db.execute(query.where(*filters)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No eligible observed site for that UPRN and property type.")
    records = db.scalars(
        select(LfbIncident).join(LfbImportRun, LfbIncident.import_run_id == LfbImportRun.id)
        .where(*_eligible(start, end), LfbIncident.uprn == uprn, LfbIncident.property_type == row.property_type)
        .order_by(LfbIncident.incident_date.desc(), LfbIncident.incident_number).limit(200)
    ).all()
    return {"site": _site(row, start, end), "incidents": [
        {"incident_number": x.incident_number, "incident_date": x.incident_date,
         "stop_code_description": x.stop_code_description, "address_qualifier": x.address_qualifier}
        for x in records], **_context(db, start, end)}


@router.get("/{uprn}")
def false_alarm_site(uprn: str, property_type: str | None = Query(default=None, max_length=255),
                     db: Session = Depends(get_db)) -> dict:
    if not uprn.isascii() or not uprn.isdigit() or len(uprn) > 20 or int(uprn) == 0:
        raise HTTPException(status_code=422, detail="UPRN must be a positive numeric identifier.")
    return get_site_detail(db, uprn, property_type)


@router.get("/{uprn}/inspection-context")
def inspection_context(uprn: str, db: Session = Depends(get_db)) -> dict:
    if not uprn.isascii() or not uprn.isdigit() or len(uprn) > 20 or int(uprn) == 0:
        raise HTTPException(status_code=422, detail="UPRN must be a positive numeric identifier.")
    items = db.scalars(select(LfbInspectionMatch).where(LfbInspectionMatch.uprn == uprn)
                       .order_by(LfbInspectionMatch.completed_on.desc(), LfbInspectionMatch.fingerprint).limit(40)).all()
    available = bool(db.scalar(select(LfbInspectionMatch.fingerprint).limit(1)))
    return {"uprn": uprn, "snapshot_available": available, "matches": [{"site_name": x.site_name, "organisation_name": x.organisation_name,
        "site_reference_url": x.site_reference_url, "site_reference_period": x.site_reference_period,
        "postcode": x.postcode, "inspection_address": x.inspection_address,
        "property_use": x.property_use, "reason_or_outcome": x.reason_or_outcome,
        "completed_on": x.completed_on, "source_file": x.source_file,
        "source_sha256": x.source_sha256, "imported_at": x.imported_at} for x in items],
        "source_url": INSPECTION_SOURCE,
        "limitations": ["Candidate link uses the same full postcode and an exact hospital name appearing in the inspection address and a historical NHS site reference. It is not an independently verified UPRN match; the inspection may concern a different building or block.",
                        "The recorded outcome is historical and may have been remedied or superseded. It does not establish current compliance, supplier performance, cause, or intent to buy.",
                        "The dataset is a local snapshot and not refreshed automatically. No match does not mean no inspection occurred."]}
