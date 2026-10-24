from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.connectors import (
    BuyerWebsiteWatchlistConnector,
    ContractsFinderConnector,
    FindATenderConnector,
    ManualMarketSignalUploadConnector,
    SourceConnector,
    SourceRecord,
    default_market_source_connectors,
)
from app.db import Base, create_database_engine, get_db
from app.main import create_app
from app.models import MarketSignal, SourceRun
from app.services.market_data_refresh import refresh_market_data


def _testing_session(tmp_path) -> sessionmaker[Session]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'source-runs.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_default_source_connectors_expose_required_interface() -> None:
    connectors = default_market_source_connectors()

    assert [connector.connector_name for connector in connectors] == [
        "Find a Tender",
        "Contracts Finder",
        "Manual Market Signal Upload",
        "Buyer Website Watchlist",
    ]
    assert all(isinstance(connector.source_type, str) for connector in connectors)
    assert all(hasattr(connector, "fetch") for connector in connectors)
    assert all(hasattr(connector, "normalise") for connector in connectors)
    assert all(connector.last_checked is None for connector in connectors)

    for connector in connectors:
        records = connector.normalise(connector.fetch())
        assert records
        assert connector.last_checked is not None
        assert all(record.attribution for record in records)
        assert all(record.source_type == connector.source_type for record in records)


def test_market_data_refresh_populates_market_signals_and_source_runs(tmp_path) -> None:
    testing_session = _testing_session(tmp_path)

    with testing_session() as db:
        summary = refresh_market_data(db)

        assert summary.records_found == 4
        assert summary.records_imported == 4
        assert len(summary.source_runs) == 4
        assert {run.connector_name for run in summary.source_runs} == {
            "Find a Tender",
            "Contracts Finder",
            "Manual Market Signal Upload",
            "Buyer Website Watchlist",
        }
        assert all(run.status == "success" for run in summary.source_runs)
        assert all(run.finished_at is not None for run in summary.source_runs)
        assert db.scalar(select(func.count(MarketSignal.id))) == 4
        assert db.scalar(select(func.count(SourceRun.id))) == 4

        first_signal = db.scalar(
            select(MarketSignal).where(MarketSignal.source_type == "find_a_tender")
        )
        assert first_signal is not None
        assert first_signal.source_url == "https://www.find-tender.service.gov.uk/"
        assert "Find a Tender" in first_signal.source_attribution
        assert first_signal.suggested_action

        second_summary = refresh_market_data(db)
        assert second_summary.records_found == 4
        assert second_summary.records_imported == 0
        assert db.scalar(select(func.count(MarketSignal.id))) == 4
        assert db.scalar(select(func.count(SourceRun.id))) == 8


def test_refresh_market_data_records_connector_failures(tmp_path) -> None:
    class BrokenConnector(SourceConnector):
        connector_name = "Broken Test Connector"
        source_type = "broken_test_connector"
        last_checked = None

        def fetch(self) -> list[dict[str, object]]:
            raise RuntimeError("Controlled connector failure")

        def normalise(self, records: list[dict[str, object]]) -> list[SourceRecord]:
            return []

    testing_session = _testing_session(tmp_path)

    with testing_session() as db:
        summary = refresh_market_data(db, connectors=[BrokenConnector()])

        assert summary.records_found == 0
        assert summary.records_imported == 0
        assert len(summary.source_runs) == 1
        run = summary.source_runs[0]
        assert run.connector_name == "Broken Test Connector"
        assert run.status == "failed"
        assert run.errors == ["Controlled connector failure"]
        assert db.scalar(select(func.count(MarketSignal.id))) == 0


def test_source_refresh_api_triggers_refresh_and_lists_run_history(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SingleRecordConnector(SourceConnector):
        connector_name = "Single Test Connector"
        source_type = "single_test_connector"
        last_checked = None

        def fetch(self) -> list[dict[str, object]]:
            self.last_checked = datetime.now(UTC)
            return [{"title": "raw"}]

        def normalise(self, records: list[dict[str, object]]) -> list[SourceRecord]:
            return [
                SourceRecord(
                    title="Single mock signal",
                    buyer_name="Example Buyer",
                    sector="Government",
                    region="London",
                    estimated_value=250_000,
                    expected_tender_date=None,
                    source_type=self.source_type,
                    attribution="Controlled unit-test connector sample.",
                    source_url="https://example.invalid/source",
                    confidence_score=0.5,
                    suggested_action="Review sample source connector output.",
                    retrieved_at=self.last_checked,
                )
            ]

    import app.services.market_data_refresh as refresh_service

    monkeypatch.setattr(
        refresh_service,
        "default_market_source_connectors",
        lambda: [SingleRecordConnector()],
    )
    testing_session = _testing_session(tmp_path)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.post("/api/refresh-market-data")
    assert response.status_code == 200
    body = response.json()
    assert body["records_found"] == 1
    assert body["records_imported"] == 1
    assert body["source_runs"][0]["connector_name"] == "Single Test Connector"

    runs_response = client.get("/api/source-runs")
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert len(runs) == 1
    assert runs[0]["status"] == "success"

    signals_response = client.get("/api/market-signals")
    assert signals_response.status_code == 200
    signals = signals_response.json()
    assert len(signals) == 1
    assert signals[0]["source_type"] == "single_test_connector"
    assert signals[0]["source_attribution"] == "Controlled unit-test connector sample."
