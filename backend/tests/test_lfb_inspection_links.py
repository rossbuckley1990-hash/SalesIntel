from datetime import datetime

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session
import pytest

from app.db import Base, create_database_engine
from app.ingestion.lfb_inspections import import_matches
from app.models.lfb_inspection_match import LfbInspectionMatch
from app.models.public_site_reference import PublicSiteReference
from app.routers.virtual_sensor import inspection_context


def _workbook(path, rows):
    book = Workbook()
    sheet = book.active
    sheet.append([]); sheet.append([]); sheet.append([]); sheet.append([])
    sheet.append([None, "Borough", "Building Address", None, "Postcode", "Reason for Visit or Outcome", "Job Step Completion Date", "Property Use"])
    for address, postcode, outcome in rows:
        sheet.append([None, "Islington", address, None, postcode, outcome, datetime(2025, 2, 1), "Hospital"])
    book.save(path)


def _ref(uprn, name="The Whittington Hospital", postcode="N19 5NF", org="Example NHS Trust"):
    return PublicSiteReference(source_record_id="test:" + uprn, uprn=uprn, organisation_id="nhs:trust",
        organisation_name=org, site_name=name, postcode=postcode,
        source_url="https://example.org/nhs-data", source_period="2025/26")


def test_link_requires_full_postcode_and_exact_hospital_name_and_retains_block(tmp_path):
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    workbook = tmp_path / "visits.xlsx"
    _workbook(workbook, [("The Whittington Hospital, Block L", "N195NF", "Premises Non Compliant"),
                         ("Unrelated Hospital", "N195NF", "Audit"),
                         ("The Whittington Hospital", "N19 5ZZ", "Audit")])
    with Session(engine) as db:
        db.add(_ref("12345")); db.commit()
        report = import_matches(workbook, db)
        assert report["matches"] == 1
        result = inspection_context("12345", db)
        assert result["matches"][0]["inspection_address"] == "The Whittington Hospital, Block L"
        assert result["matches"][0]["reason_or_outcome"] == "Premises Non Compliant"
        assert "different building or block" in result["limitations"][0]
        assert "historical" in result["limitations"][1]


def test_ambiguous_same_name_and_postcode_are_not_joined(tmp_path):
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    workbook = tmp_path / "visits.xlsx"
    _workbook(workbook, [("The Whittington Hospital, Block L", "N19 5NF", "Audit")])
    with Session(engine) as db:
        db.add_all([_ref("12345"), _ref("67890")]); db.commit()
        report = import_matches(workbook, db)
        assert report["matches"] == 0
        assert db.scalars(select(LfbInspectionMatch)).all() == []


def test_failed_or_empty_reimport_keeps_existing_candidate_matches(tmp_path):
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    first, second = tmp_path / "first.xlsx", tmp_path / "second.xlsx"
    _workbook(first, [("The Whittington Hospital, Block L", "N19 5NF", "Audit")])
    _workbook(second, [("Unrelated Hospital", "N19 5NF", "Audit")])
    with Session(engine) as db:
        db.add(_ref("12345")); db.commit()
        import_matches(first, db)
        with pytest.raises(ValueError, match="existing matches were retained"):
            import_matches(second, db)
        assert len(db.scalars(select(LfbInspectionMatch)).all()) == 1
