from datetime import UTC, date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common import MisiSchema

EvidenceCategory = Literal["service_issue", "customer_feedback", "compliance", "maintenance", "supplier", "estate_change", "other"]


class EvidenceObservationInput(MisiSchema):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True, extra="forbid")

    # This is an importer-supplied identifier, not an independently verified identity.
    organisation_id: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z][A-Za-z0-9_-]{1,31}:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    organisation_name: str = Field(min_length=1, max_length=255)
    site: str = Field(min_length=1, max_length=255)
    category: EvidenceCategory
    observed_statement: str = Field(min_length=1, max_length=4000)
    source_title: str = Field(min_length=1, max_length=255)
    source_reference: str = Field(min_length=1, max_length=512)
    source_url: str | None = Field(default=None, max_length=2048)
    published_at: date | None = None
    observed_at: date | None = None
    retrieved_at: datetime

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("source_url must be an HTTP or HTTPS URL")
        return value

    @field_validator("retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")
        return value.astimezone(UTC)


class EvidenceObservationRead(EvidenceObservationInput):
    id: int
    imported_at: datetime

    @field_validator("retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        # SQLite drops timezone metadata; input is always normalized to UTC.
        return value.replace(tzinfo=UTC) if value.utcoffset() is None else value.astimezone(UTC)

    @field_validator("imported_at")
    @classmethod
    def imported_at_is_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.utcoffset() is None else value.astimezone(UTC)


class EvidenceImportRequest(MisiSchema):
    model_config = ConfigDict(extra="forbid")
    observations: list[EvidenceObservationInput] = Field(min_length=1, max_length=1000)


class EvidenceImportResult(MisiSchema):
    imported: int
    duplicates: int


class EvidencePage(MisiSchema):
    items: list[EvidenceObservationRead]
    total: int


class AccountSummary(MisiSchema):
    organisation_id: str
    organisation_name: str
    observation_count: int


class AccountPage(MisiSchema):
    items: list[AccountSummary]
    total: int


class EvidenceDossier(MisiSchema):
    organisation_id: str
    organisation_name: str
    observations: list[EvidenceObservationRead]
    total: int
