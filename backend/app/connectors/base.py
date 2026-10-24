from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class SourceRecord:
    title: str
    buyer_name: str
    sector: str
    region: str
    estimated_value: float | None
    expected_tender_date: date | None
    source_type: str
    attribution: str
    source_url: str | None = None
    confidence_score: float = 0
    suggested_action: str = ""
    retrieved_at: datetime | None = None


class SourceConnector(ABC):
    connector_name: str
    source_type: str
    last_checked: datetime | None = None

    @property
    def name(self) -> str:
        return self.connector_name

    @abstractmethod
    def fetch(self) -> list[dict[str, object]]:
        """Fetch raw records from an approved data source or controlled mock."""

    @abstractmethod
    def normalise(self, records: list[dict[str, object]]) -> list[SourceRecord]:
        """Convert raw connector records into source-attributed market signals."""
