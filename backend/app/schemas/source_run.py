from datetime import datetime

from app.schemas.common import MisiSchema


class SourceRunRead(MisiSchema):
    id: int
    connector_name: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    records_found: int
    records_imported: int
    errors: list[str]


class MarketDataRefreshResponse(MisiSchema):
    source_runs: list[SourceRunRead]
    records_found: int
    records_imported: int
