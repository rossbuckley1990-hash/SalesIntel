from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, create_database_engine, get_db
from app.models.lfb_incident import LfbImportRun, LfbIncident
from app.routers.virtual_sensor import router


@pytest.fixture
def sensor(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'sensor.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        db.add(LfbImportRun(id=1, source_url="https://example.org/source", source_file="test.xlsx",
                            sha256="a" * 64, status="completed", rows_seen=30, records_imported=30,
                            rows_excluded=0, min_date=date(2024, 1, 1), max_date=date(2026, 9, 1)))
        db.add(LfbImportRun(id=2, source_url="https://example.org/source", source_file="pending.xlsx",
                            sha256="b" * 64, status="running", rows_seen=1, records_imported=1,
                            rows_excluded=0, min_date=date(2026, 9, 1), max_date=date(2026, 9, 1)))

        def record(number, uprn, day, **overrides):
            values = dict(incident_number=number, uprn=uprn, incident_date=day, incident_group="False Alarm",
                          stop_code_description="AFA", property_category="Non Residential", property_type="Hospital",
                          address_qualifier="Correct incident location", postcode_district="NW1", import_run_id=1)
            values.update(overrides)
            db.add(LfbIncident(**values))

        record("a1", "101", date(2026, 8, 1))
        record("a2", "101", date(2026, 9, 1))
        record("b1", "102", date(2026, 7, 1))
        record("c1", "103", date(2026, 7, 1), property_type="School")
        record("c2", "103", date(2026, 8, 1), property_type="School")
        record("c3", "103", date(2026, 9, 1), property_type="School")
        # Ineligible incidents must not inflate either the site or cohort.
        record("old", "101", date(2024, 10, 28))
        record("nearby", "101", date(2026, 9, 1), address_qualifier="Nearby address - street not listed in gazetteer")
        record("dwelling", "101", date(2026, 9, 1), property_category="Dwelling")
        record("other", "101", date(2026, 9, 1), stop_code_description="False alarm good intent")
        record("pending", "101", date(2026, 9, 1), import_run_id=2)
        # Conflicting property classification makes a UPRN unsuitable for a peer group.
        record("conf1", "104", date(2026, 8, 1), property_type="School")
        record("conf2", "104", date(2026, 9, 1), property_type="Hospital")
    app = FastAPI()
    app.include_router(router)
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_site_counts_compare_observed_sites_within_same_type_and_period(sensor):
    result = sensor.get("/api/virtual-sensors/false-alarms").json()
    assert result["total"] == 2
    assert [x["uprn"] for x in result["items"]] == ["103", "101"]
    site = result["items"][1]
    assert site["attendances"] == 2
    assert site["comparison"] == {"cohort_sites": 1, "mean_attendances": 1.0}
    assert result["period_start"] == "2025-09-02"
    assert result["period_end"] == "2026-09-01"
    assert "not all alarm activations" in result["limitations"][0]
    assert "not its occupier" in result["limitations"][3]
    assert "not establish a fault" in site["research_brief"]


def test_detail_and_filters_exclude_ambiguous_and_ineligible_sites(sensor):
    result = sensor.get("/api/virtual-sensors/false-alarms/101").json()
    assert [x["incident_number"] for x in result["incidents"]] == ["a2", "a1"]
    assert sensor.get("/api/virtual-sensors/false-alarms/104").status_code == 404
    assert sensor.get("/api/virtual-sensors/false-alarms/101?property_type=School").status_code == 404
    assert sensor.get("/api/virtual-sensors/false-alarms/invalid").status_code == 422
    filtered = sensor.get("/api/virtual-sensors/false-alarms?property_type=Hospital").json()
    assert filtered["total"] == 1 and filtered["items"][0]["uprn"] == "101"


def test_no_import_never_fabricates_candidates(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(router)
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        result = client.get("/api/virtual-sensors/false-alarms").json()
        assert result["total"] == 0 and result["items"] == []
        assert result["period_start"] is None and result["period_end"] is None
        assert client.get("/api/virtual-sensors/false-alarms/101").status_code == 404
    engine.dispose()


def test_reporting_window_excludes_policy_transition_day(tmp_path: Path):
    from app.routers.virtual_sensor import list_false_alarm_sites
    engine = create_database_engine(f"sqlite:///{tmp_path / 'policy.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        db.add(LfbImportRun(id=1, source_url="https://example.org/source", source_file="test.xlsx",
                            sha256="a" * 64, status="completed", rows_seen=3, records_imported=3,
                            rows_excluded=0, min_date=date(2024, 10, 29), max_date=date(2025, 1, 1),
                            acquisition_method="official_download", retrieved_at=datetime(2025, 1, 2, 12, tzinfo=UTC)))
        for number, day in [("transition", date(2024, 10, 29)), ("after", date(2024, 10, 30)), ("later", date(2025, 1, 1))]:
            db.add(LfbIncident(incident_number=number, incident_date=day, incident_group="False Alarm",
                    stop_code_description="AFA", property_category="Non Residential", property_type="Hospital",
                    address_qualifier="Correct incident location", uprn="101", postcode_district="NW1", import_run_id=1))
    with factory() as db:
        result = list_false_alarm_sites(limit=25, offset=0, property_type=None, db=db)
        assert result["period_start"] == date(2024, 10, 30)
        assert result["items"][0]["attendances"] == 2
        assert result["items"][0]["comparison"] == {"cohort_sites": 0, "mean_attendances": None}
        assert result["snapshot"]["sha256"] == "a" * 64
        assert result["snapshot"]["acquisition_method"] == "official_download"
        assert result["snapshot"]["retrieved_at"] == datetime(2025, 1, 2, 12, tzinfo=UTC)
    engine.dispose()
