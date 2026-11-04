from datetime import date, datetime
import importlib.util
import io
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, create_database_engine
from app.ingestion import lfb_incidents
from app.models.lfb_incident import LfbIncident, LfbImportRun


def incident(number="abc"):
    return dict(incident_number=number, incident_date=date(2026, 1, 1), incident_group="False Alarm",
        stop_code_description="AFA", property_category="Non Residential", property_type="Hospital",
        address_qualifier="Correct incident location", uprn="123456", postcode_district="N1")


def test_row_filters_dwellings_missing_uprns_and_preserves_qualifier():
    names = lfb_incidents.REQUIRED
    indexes = {name: i for i, name in enumerate(names)}
    def row(category, uprn, qualifier="Within same building"):
        values = {"IncidentNumber": "2026-1", "DateOfCall": date(2026, 1, 1), "IncidentGroup": "False Alarm",
                  "StopCodeDescription": "AFA", "PropertyCategory": category, "PropertyType": "Hospital",
                  "AddressQualifier": qualifier, "Postcode_district": "N1", "UPRN": uprn}
        return tuple(values[name] for name in names)
    assert lfb_incidents._record(row("Dwelling", "123"), indexes) is None
    assert lfb_incidents._record(row("Non Residential", 0), indexes) is None
    assert lfb_incidents._record(row("Non Residential", 3.5), indexes) is None
    result = lfb_incidents._record(row("Non Residential", 123), indexes)
    assert result["uprn"] == "123"
    assert result["address_qualifier"] == "Within same building"
    assert result["stop_code_description"] == "AFA"


def test_import_is_atomic_idempotent_and_replaces_snapshot(tmp_path, monkeypatch):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    path = tmp_path / "snapshot.xlsx"
    path.write_bytes(b"first snapshot")
    monkeypatch.setattr(lfb_incidents, "iter_incidents", lambda _: iter([incident(), None]))
    with Session(engine) as db:
        first = lfb_incidents.import_workbook(path, db, batch_size=1, retrieved_at=datetime.fromisoformat("2026-10-28T14:00:00+01:00"))
        assert (first.rows_seen, first.records_imported, first.rows_excluded) == (2, 1, 1)
        assert lfb_incidents.import_workbook(path, db).already_imported
        assert db.scalar(select(func.count()).select_from(LfbImportRun)) == 1
        assert db.scalar(select(LfbImportRun.retrieved_at)).replace(tzinfo=None) == datetime(2026, 10, 28, 13, 0, 0)
        path.write_bytes(b"failed new snapshot")
        monkeypatch.setattr(lfb_incidents, "iter_incidents", lambda _: iter([incident("new"), incident("new")]))
        with pytest.raises(IntegrityError):
            lfb_incidents.import_workbook(path, db, batch_size=1)
        assert [r.incident_number for r in db.scalars(select(LfbIncident)).all()] == ["abc"]
        assert db.scalar(select(func.count()).select_from(LfbImportRun)) == 1
        path.write_bytes(b"valid new snapshot")
        monkeypatch.setattr(lfb_incidents, "iter_incidents", lambda _: iter([incident("new")]))
        result = lfb_incidents.import_workbook(path, db, batch_size=1)
        assert result.records_imported == 1
        assert [r.incident_number for r in db.scalars(select(LfbIncident)).all()] == ["new"]
        assert db.scalar(select(func.count()).select_from(LfbImportRun)) == 2
        path.write_bytes(b"first snapshot")
        monkeypatch.setattr(lfb_incidents, "iter_incidents", lambda _: iter([incident("abc")]))
        assert not lfb_incidents.import_workbook(path, db).already_imported
        assert [r.incident_number for r in db.scalars(select(LfbIncident)).all()] == ["abc"]
    engine.dispose()


def test_download_is_fixed_source_bounded_and_refuses_redirects(tmp_path, monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "import_lfb_incidents.py"
    spec = importlib.util.spec_from_file_location("lfb_import_script", script_path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == lfb_incidents.DOWNLOAD_URL
            assert request.get_header("User-agent") == "Mozilla/5.0 MiSi-public-data-import/1.0"
            assert timeout == 120
            return io.BytesIO(b"test")

    monkeypatch.setattr(script, "build_opener", lambda *_: Opener())
    destination = tmp_path / "test.xlsx"
    retrieved_at = script.download_official(destination)
    assert destination.read_bytes() == b"test"
    assert retrieved_at.utcoffset() is not None
    monkeypatch.setattr(script, "MAX_DOWNLOAD", 3)
    with pytest.raises(ValueError, match="exceeds"):
        script.download_official(destination)
    with pytest.raises(ValueError, match="redirected"):
        script.NoRedirect().redirect_request(None, None, None, None, None, "https://other.example/")
