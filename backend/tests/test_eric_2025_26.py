import csv
import io
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.ingestion.eric_2025_26 import parse_eric_site_data, validate_official_file
from app.models.evidence_observation import EvidenceObservation
from app.routers.evidence_observations import import_evidence
from app.schemas.evidence_observation import EvidenceImportRequest


def fixture_csv() -> bytes:
    rows = [
        ["", "", "", "", "", "S03_08", "S03_09", "S03_10", "S03_11"],
        ["Trust Code", "Trust Name", "EFM Site Id", "Site Code", "Site Name", "Cost to eradicate high risk backlog (£)", "Cost to eradicate significant risk backlog (£)", "Cost to eradicate moderate risk backlog (£)", "Cost to eradicate low risk backlog (£)"],
        ["R0A", "Example NHS Trust", "123", "SITE1", "Example Hospital", "1000", "Not Applicable", "0", "250"],
        ["R0A", "Example NHS Trust", "124", "SITE2", "No backlog", "0", "0", "0", "0"],
        ["R0A", "Example NHS Trust", "125", "SITE3", "No data", "Not Applicable", "", "", ""],
    ]
    out = io.StringIO(newline="")
    csv.writer(out).writerows(rows)
    return out.getvalue().encode("cp1252")


def test_eric_preserves_values_and_unknowns_and_uses_only_general_estate_claims():
    results = parse_eric_site_data(fixture_csv(), retrieved_at=datetime(2026, 10, 28, tzinfo=UTC))
    assert len(results) == 1
    obs = results[0]
    assert obs.organisation_id == "nhs-ods:R0A"
    assert "EFM site 123" in obs.site
    assert "high-risk: £1,000.00" in obs.observed_statement
    assert "moderate-risk: £0.00" in obs.observed_statement
    assert "significant-risk:" not in obs.observed_statement
    assert "not fire or security specific" in obs.observed_statement
    assert obs.observed_at.isoformat() == "2026-03-31"
    assert obs.published_at.isoformat() == "2026-10-15"


def test_schema_and_source_reject_untrusted_or_truncated_data():
    with pytest.raises(ValueError, match="SHA-256"):
        validate_official_file(fixture_csv())
    with pytest.raises(ValueError, match="headers"):
        parse_eric_site_data(b"unexpected\nheader\n", retrieved_at=datetime(2026, 10, 28, tzinfo=UTC))


def test_same_data_imported_twice_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    EvidenceObservation.__table__.create(engine)
    data = fixture_csv()
    first = parse_eric_site_data(data, retrieved_at=datetime(2026, 10, 28, tzinfo=UTC))
    second = parse_eric_site_data(data, retrieved_at=datetime(2026, 10, 29, tzinfo=UTC))
    with Session(engine) as db:
        assert import_evidence(EvidenceImportRequest(observations=first), db).imported == 1
        assert import_evidence(EvidenceImportRequest(observations=second), db).duplicates == 1
        assert db.scalar(select(func.count()).select_from(EvidenceObservation)) == 1
