from app.schemas.common import MisiSchema


class TrackerRecordReference(MisiSchema):
    id: int
    name: str
    buyer_name: str


class TrackerValidationError(MisiSchema):
    row_number: int | None = None
    field: str
    message: str


class TrackerImportSummary(MisiSchema):
    rows_received: int
    rows_imported: int
    rows_skipped: int
    validation_errors: list[TrackerValidationError]
    created_records: list[TrackerRecordReference]
    updated_records: list[TrackerRecordReference]
