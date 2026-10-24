from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, create_database_engine, get_db
from app.main import create_app
from app.models import Opportunity

REPO_ROOT = Path(__file__).resolve().parents[2]


def _client_with_database(tmp_path: Path) -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'tracker-upload.db'}")
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session


def test_csv_tracker_upload_creates_and_updates_opportunities(tmp_path: Path) -> None:
    client, testing_session = _client_with_database(tmp_path)
    sample_path = REPO_ROOT / "sample_data" / "tracker_upload_sample.csv"
    file_bytes = sample_path.read_bytes()

    create_response = client.post(
        "/api/upload-tracker",
        files={"file": (sample_path.name, file_bytes, "text/csv")},
    )

    assert create_response.status_code == 200
    create_summary = create_response.json()
    assert create_summary["rows_received"] == 3
    assert create_summary["rows_imported"] == 3
    assert create_summary["rows_skipped"] == 0
    assert len(create_summary["created_records"]) == 3
    assert create_summary["updated_records"] == []

    update_response = client.post(
        "/api/upload-tracker",
        files={"file": (sample_path.name, file_bytes, "text/csv")},
    )

    assert update_response.status_code == 200
    update_summary = update_response.json()
    assert update_summary["rows_received"] == 3
    assert update_summary["rows_imported"] == 3
    assert update_summary["rows_skipped"] == 0
    assert update_summary["created_records"] == []
    assert len(update_summary["updated_records"]) == 3

    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 3
        retail = db.scalar(
            select(Opportunity).where(
                Opportunity.name == "Retail fire alarm lifecycle refresh"
            )
        )
        assert retail is not None
        assert retail.buyer_name == "Example Retail Estates"
        assert retail.estimated_total_contract_value == 1_250_000
        assert retail.estimated_gross_margin == 275_000
        assert retail.margin_percentage == 22
        assert retail.probability == 0.64
        assert retail.weighted_value == 800_000
        assert retail.forecast_start_month == "2026-09"
        assert retail.source_type == "tracker_upload"


def test_xlsx_tracker_upload_accepts_sparse_optional_columns(tmp_path: Path) -> None:
    client, testing_session = _client_with_database(tmp_path)
    sample_path = REPO_ROOT / "sample_data" / "tracker_upload_sample.xlsx"

    response = client.post(
        "/api/upload-tracker",
        files={
            "file": (
                sample_path.name,
                sample_path.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    summary = response.json()
    assert summary["rows_received"] == 2
    assert summary["rows_imported"] == 2
    assert summary["rows_skipped"] == 0
    assert summary["validation_errors"] == []

    with testing_session() as db:
        university = db.scalar(
            select(Opportunity).where(
                Opportunity.name == "University PAVA phased upgrade"
            )
        )
        assert university is not None
        assert university.buyer_name == "Example University Estates"
        assert university.sector == "Unknown"
        assert university.region == "Unknown"
        assert university.owner == "Unassigned"
        assert university.source_type == "tracker_upload"
        assert university.stage == "PQQ"
        assert university.probability == 0.47
        assert university.forecast_start_month == "2026-11"
        assert university.recommended_action == "Confirm summer access and evidence pack."


def test_tracker_upload_reports_missing_required_columns(tmp_path: Path) -> None:
    client, _testing_session = _client_with_database(tmp_path)
    content = b"Opportunity Name,Stage\nExample opportunity,Pricing\n"

    response = client.post(
        "/api/upload-tracker",
        files={"file": ("missing-buyer.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    summary = response.json()
    assert summary["rows_received"] == 1
    assert summary["rows_imported"] == 0
    assert summary["rows_skipped"] == 1
    assert summary["validation_errors"][0]["field"] == "headers"
    assert "buyer/client" in summary["validation_errors"][0]["message"]


def test_tracker_upload_skips_rows_with_clear_validation_errors(tmp_path: Path) -> None:
    client, testing_session = _client_with_database(tmp_path)
    content = (
        "Opportunity Name,Client,Estimated Revenue,Probability,Deadline\n"
        "Bad value opportunity,Example Client,not money,maybe,not a date\n"
    ).encode()

    response = client.post(
        "/api/upload-tracker",
        files={"file": ("bad-values.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    summary = response.json()
    assert summary["rows_received"] == 1
    assert summary["rows_imported"] == 0
    assert summary["rows_skipped"] == 1
    error_fields = {error["field"] for error in summary["validation_errors"]}
    assert {"estimated_revenue", "probability", "deadline"} <= error_fields

    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 0


def test_tracker_upload_rejects_unsupported_file_type(tmp_path: Path) -> None:
    client, _testing_session = _client_with_database(tmp_path)

    response = client.post(
        "/api/upload-tracker",
        files={"file": ("tracker.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert ".csv or .xlsx" in response.json()["detail"]


def test_tracker_upload_rejects_unsupported_content_type(tmp_path: Path) -> None:
    client, _testing_session = _client_with_database(tmp_path)
    content = b"Opportunity Name,Client\nExample,Example Buyer\n"

    response = client.post(
        "/api/upload-tracker",
        files={"file": ("tracker.csv", content, "application/x-msdownload")},
    )

    assert response.status_code == 400
    assert "content type" in response.json()["detail"]


def test_tracker_upload_rejects_files_over_configured_size_limit(tmp_path: Path) -> None:
    client, _testing_session = _client_with_database(tmp_path)
    content = b"Opportunity Name,Client\n" + (b"A" * (5 * 1024 * 1024))

    response = client.post(
        "/api/upload-tracker",
        files={"file": ("oversized.csv", content, "text/csv")},
    )

    assert response.status_code == 413
    assert "5MB limit" in response.json()["detail"]
