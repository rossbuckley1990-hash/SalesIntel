"""Convert the published 2025/26 ERIC site data to attributable observations.

ERIC describes general estates backlog, not fire or security maintenance.
"""
import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.schemas.evidence_observation import EvidenceObservationInput

SOURCE_URL = "https://digital.nhs.uk/data-and-information/publications/statistical/estates-returns-information-collection/summary-page-and-dataset-for-eric-2025-26"
DATA_URL = "https://files.digital.nhs.uk/4F/6A7342/ERIC%20-%202025_26%20-%20Site%20data%20-%20v2.csv"
# Pin the exact v2 publication: a different file must not inherit its provenance.
SOURCE_SHA256 = "50a6286f05a7e3bd06e1849120d85392c17c25a4a17eaa4ae2779403cc3fd931"
SOURCE_TITLE = "NHS England ERIC 2025/26 site data v2"
BACKLOG_FIELDS = {
    "S03_08": "high-risk",
    "S03_09": "significant-risk",
    "S03_10": "moderate-risk",
    "S03_11": "low-risk",
}
REQUIRED_COLUMNS = ("Trust Code", "Trust Name", "EFM Site Id", "Site Code", "Site Name")


def validate_official_file(data: bytes) -> None:
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("File does not match the pinned NHS ERIC 2025/26 site data v2 SHA-256.")


def parse_eric_site_data(data: bytes, *, retrieved_at: datetime) -> list[EvidenceObservationInput]:
    """Parse rows with positive recorded backlog, keeping missing fields unknown."""
    reader = csv.reader(io.StringIO(data.decode("cp1252"), newline=""))
    try:
        codes, names = next(reader), next(reader)
    except StopIteration as exc:
        raise ValueError("ERIC file must contain both header rows.") from exc
    try:
        cols = {name: names.index(name) for name in REQUIRED_COLUMNS}
        metrics = {code: codes.index(code) for code in BACKLOG_FIELDS}
    except ValueError as exc:
        raise ValueError("ERIC site headers are missing expected columns.") from exc
    if len(codes) != len(names) or any(
        names[index] != f"Cost to eradicate {BACKLOG_FIELDS[code].replace('-', ' ')} backlog (£)"
        for code, index in metrics.items()
    ):
        raise ValueError("ERIC site metric headers do not match the expected schema.")

    observations: list[EvidenceObservationInput] = []
    for row in reader:
        if len(row) != len(names):
            raise ValueError("ERIC site row has an unexpected number of columns.")
        trust_code = row[cols["Trust Code"]].strip()
        trust_name = row[cols["Trust Name"]].strip()
        site_name = row[cols["Site Name"]].strip()
        efm_id = row[cols["EFM Site Id"]].strip()
        site_code = row[cols["Site Code"]].strip()
        if not re.fullmatch(r"[A-Za-z0-9]+", trust_code) or not re.fullmatch(r"[A-Za-z0-9]+", efm_id) or not trust_name or not site_name:
            continue
        values: list[tuple[str, Decimal]] = []
        for code, index in metrics.items():
            try:
                value = Decimal(row[index].strip())
            except InvalidOperation:
                continue
            if value.is_finite() and value >= 0:
                values.append((BACKLOG_FIELDS[code], value))
        if not any(value > 0 for _, value in values):
            continue
        amounts = "; ".join(f"{label}: £{value:,.2f}" for label, value in values)
        site = f"{site_name} (EFM site {efm_id}"
        if site_code:
            site += f", site code {site_code}"
        site += ")"
        statement = (
            f"For financial year 1 April 2025 to 31 March 2026, NHS ERIC reports "
            f"estimated cost to eradicate general estates backlog at this site: {amounts}. "
            "Missing or not applicable categories are not included. This is not fire or security "
            "specific and does not establish non-compliance, supplier performance or a buying requirement. "
            "Contains information from NHS England, licenced under the current version of the Open Government Licence."
        )
        observations.append(EvidenceObservationInput(
            organisation_id=f"nhs-ods:{trust_code}", organisation_name=trust_name,
            site=site, category="maintenance", observed_statement=statement,
            source_title=SOURCE_TITLE, source_reference=f"ERIC 2025/26 v2 EFM site {efm_id}",
            source_url=SOURCE_URL, published_at=date(2026, 10, 15),
            observed_at=date(2026, 3, 31), retrieved_at=retrieved_at,
        ))
    return observations
