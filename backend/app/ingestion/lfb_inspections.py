"""Match a local LFB inspection workbook to historical NHS site references.

This is a candidate campus-level association, not proof that an inspected block
is the UPRN recorded in the attendance dataset, or that an outcome is current.
"""
from collections import defaultdict
from datetime import date, datetime
import hashlib
import re
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.lfb_inspection_match import LfbInspectionMatch
from app.models.public_site_reference import PublicSiteReference


SOURCE = "https://www.data.gov.uk/dataset/1d299ca4-a431-4068-80fa-57af4b502762/regulatory-fire-safety-inspections-and-audits1"


def _words(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _postcode(value: str) -> str:
    return re.sub(r"\s+", "", value.upper())


def import_matches(path: Path, db: Session) -> dict:
    if not path.is_file() or path.stat().st_size > 20_000_000:
        raise ValueError("Select a workbook of at most 20 MB.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    refs: dict[str, list[PublicSiteReference]] = defaultdict(list)
    for ref in db.scalars(select(PublicSiteReference)).all():
        if ref.postcode and ref.uprn.isdigit():
            refs[_postcode(ref.postcode)].append(ref)
    if not refs:
        raise ValueError("Import NHS site references before linking inspections.")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        if sheet.max_row > 100_000 or sheet.max_column > 50:
            raise ValueError("Inspection workbook exceeds safe bounds.")
        header = next(sheet.iter_rows(min_row=5, max_row=5, values_only=True), ())
        if tuple(header[1:3]) != ("Borough", "Building Address") or tuple(header[4:8]) != ("Postcode", "Reason for Visit or Outcome", "Job Step Completion Date", "Property Use"):
            raise ValueError("The inspection workbook has an unexpected column layout.")
        matches: dict[str, dict] = {}
        scanned = 0
        for row in sheet.iter_rows(min_row=6, values_only=True):
            scanned += 1
            _, _, address, _, postcode, reason, day, category = (list(row[:8]) + [None] * 8)[:8]
            if not all(isinstance(x, str) and x.strip() for x in (address, postcode, reason)):
                continue
            if isinstance(day, datetime):
                day = day.date()
            if not isinstance(day, date):
                continue
            address_key = f" {_words(address)} "
            candidates = []
            for ref in refs.get(_postcode(postcode), []):
                key = _words(ref.site_name)
                # Generic street names and small buildings are not matched.
                if len(key) >= 12 and any(word in key.split() for word in ("hospital", "infirmary")) and f" {key} " in address_key:
                    candidates.append(ref)
            identities = {(r.uprn, r.site_name, r.organisation_name) for r in candidates}
            if len(identities) != 1:
                continue
            ref = candidates[0]
            fields = (ref.uprn, ref.site_name, ref.organisation_name, postcode, address, str(category or ""), reason, day.isoformat())
            fingerprint = hashlib.sha256("\0".join(fields).encode()).hexdigest()
            matches[fingerprint] = dict(fingerprint=fingerprint, uprn=ref.uprn, organisation_name=ref.organisation_name,
                site_name=ref.site_name, site_reference_url=ref.source_url, site_reference_period=ref.source_period,
                postcode=postcode, inspection_address=address,
                property_use=str(category or "")[:255], reason_or_outcome=reason[:255], completed_on=day,
                source_file=path.name[:255], source_sha256=digest)
        if scanned < 1:
            raise ValueError("The inspection workbook has no data rows; existing matches were retained.")
        if not matches and db.scalar(select(LfbInspectionMatch.fingerprint).limit(1)):
            raise ValueError("No candidate matches found; existing matches were retained for review.")
        db.execute(delete(LfbInspectionMatch))
        db.add_all(LfbInspectionMatch(**item) for item in matches.values())
        db.commit()
        return {"rows_scanned": scanned, "matches": len(matches), "sites": len({x['uprn'] for x in matches.values()}), "sha256": digest}
    except Exception:
        db.rollback()
        raise
    finally:
        workbook.close()
