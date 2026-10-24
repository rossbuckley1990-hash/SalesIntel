from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors import SourceConnector, SourceRecord, default_market_source_connectors
from app.models import MarketSignal, SourceRun
from app.schemas import MarketDataRefreshResponse


def refresh_market_data(
    db: Session,
    connectors: list[SourceConnector] | None = None,
) -> MarketDataRefreshResponse:
    active_connectors = connectors or default_market_source_connectors()
    source_runs: list[SourceRun] = []

    for connector in active_connectors:
        run = SourceRun(
            connector_name=connector.connector_name,
            started_at=datetime.now(UTC),
            finished_at=None,
            status="running",
            records_found=0,
            records_imported=0,
            errors=[],
        )
        db.add(run)
        db.flush()

        try:
            raw_records = connector.fetch()
            records = connector.normalise(raw_records)
            run.records_found = len(records)
            run.records_imported = _import_market_signal_records(db, records)
            run.status = "success"
        except Exception as exc:  # pragma: no cover - exercised by endpoint/service tests.
            run.status = "failed"
            run.errors = [str(exc)]
        finally:
            run.finished_at = datetime.now(UTC)
            db.flush()
            source_runs.append(run)

    db.commit()
    return MarketDataRefreshResponse(
        source_runs=source_runs,
        records_found=sum(run.records_found for run in source_runs),
        records_imported=sum(run.records_imported for run in source_runs),
    )


def list_source_runs(db: Session, *, limit: int = 100) -> list[SourceRun]:
    return list(
        db.scalars(
            select(SourceRun)
            .order_by(SourceRun.started_at.desc(), SourceRun.id.desc())
            .limit(limit)
        )
    )


def _import_market_signal_records(
    db: Session,
    records: list[SourceRecord],
) -> int:
    imported = 0
    for record in records:
        if _market_signal_exists(db, record):
            continue
        db.add(
            MarketSignal(
                title=record.title,
                buyer_name=record.buyer_name,
                sector=record.sector,
                region=record.region,
                estimated_value=record.estimated_value,
                expected_tender_date=record.expected_tender_date,
                source_type=record.source_type,
                source_url=record.source_url,
                source_attribution=record.attribution,
                confidence_score=record.confidence_score,
                suggested_action=record.suggested_action,
            )
        )
        imported += 1
    return imported


def _market_signal_exists(db: Session, record: SourceRecord) -> bool:
    statement = select(MarketSignal.id).where(
        MarketSignal.source_type == record.source_type,
        MarketSignal.title == record.title,
        MarketSignal.buyer_name == record.buyer_name,
    )
    if record.source_url:
        statement = statement.where(MarketSignal.source_url == record.source_url)
    return db.scalar(statement) is not None
