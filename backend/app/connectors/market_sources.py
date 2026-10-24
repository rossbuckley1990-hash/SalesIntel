from datetime import UTC, date, datetime

from app.connectors.base import SourceConnector, SourceRecord


class MockMarketSourceConnector(SourceConnector):
    connector_name = "Mock Market Source"
    source_type = "mock_market_source"

    def fetch(self) -> list[dict[str, object]]:
        self.last_checked = datetime.now(UTC)
        return self.sample_records()

    def normalise(self, records: list[dict[str, object]]) -> list[SourceRecord]:
        return [
            SourceRecord(
                title=str(record["title"]),
                buyer_name=str(record["buyer_name"]),
                sector=str(record["sector"]),
                region=str(record["region"]),
                estimated_value=(
                    float(record["estimated_value"])
                    if record.get("estimated_value") is not None
                    else None
                ),
                expected_tender_date=record.get("expected_tender_date"),
                source_type=self.source_type,
                attribution=str(record["attribution"]),
                source_url=(
                    str(record["source_url"]) if record.get("source_url") else None
                ),
                confidence_score=float(record.get("confidence_score", 0)),
                suggested_action=str(record.get("suggested_action", "")),
                retrieved_at=self.last_checked,
            )
            for record in records
        ]

    def sample_records(self) -> list[dict[str, object]]:
        return []


class FindATenderConnector(MockMarketSourceConnector):
    connector_name = "Find a Tender"
    source_type = "find_a_tender"

    def sample_records(self) -> list[dict[str, object]]:
        return [
            {
                "title": "Regional fire alarm servicing framework signal",
                "buyer_name": "Northshire Combined Authority",
                "sector": "Local Authority",
                "region": "North West",
                "estimated_value": 1_850_000,
                "expected_tender_date": date(2026, 9, 15),
                "attribution": "Controlled sample based on Find a Tender-style notice metadata.",
                "source_url": "https://www.find-tender.service.gov.uk/",
                "confidence_score": 0.68,
                "suggested_action": "Track notice publication and prepare regional delivery evidence.",
            }
        ]


class ContractsFinderConnector(MockMarketSourceConnector):
    connector_name = "Contracts Finder"
    source_type = "contracts_finder"

    def sample_records(self) -> list[dict[str, object]]:
        return [
            {
                "title": "Blue-light estate CCTV lifecycle opportunity",
                "buyer_name": "Example Police Estates",
                "sector": "Police",
                "region": "East Midlands",
                "estimated_value": 720_000,
                "expected_tender_date": date(2026, 8, 20),
                "attribution": "Controlled sample based on Contracts Finder-style pipeline data.",
                "source_url": "https://www.contractsfinder.service.gov.uk/",
                "confidence_score": 0.64,
                "suggested_action": "Prepare custody and secure-estate references before tender release.",
            }
        ]


class ManualMarketSignalUploadConnector(MockMarketSourceConnector):
    connector_name = "Manual Market Signal Upload"
    source_type = "manual_market_signal_upload"

    def sample_records(self) -> list[dict[str, object]]:
        return [
            {
                "title": "Healthcare fire damper remediation market signal",
                "buyer_name": "Example Integrated Care Estate",
                "sector": "Healthcare",
                "region": "South East",
                "estimated_value": 980_000,
                "expected_tender_date": date(2026, 10, 1),
                "attribution": "Controlled sample representing a manually uploaded market signal.",
                "source_url": None,
                "confidence_score": 0.72,
                "suggested_action": "Confirm estate access constraints and line up healthcare references.",
            }
        ]


class BuyerWebsiteWatchlistConnector(MockMarketSourceConnector):
    connector_name = "Buyer Website Watchlist"
    source_type = "buyer_website_watchlist"

    def sample_records(self) -> list[dict[str, object]]:
        return [
            {
                "title": "University life-safety summer works watchlist signal",
                "buyer_name": "Example University Estates",
                "sector": "Education",
                "region": "Midlands",
                "estimated_value": 540_000,
                "expected_tender_date": date(2026, 7, 30),
                "attribution": "Controlled sample representing a buyer website watchlist item.",
                "source_url": "https://example.invalid/procurement",
                "confidence_score": 0.58,
                "suggested_action": "Start early stakeholder mapping and summer-access delivery planning.",
            }
        ]


def default_market_source_connectors() -> list[SourceConnector]:
    return [
        FindATenderConnector(),
        ContractsFinderConnector(),
        ManualMarketSignalUploadConnector(),
        BuyerWebsiteWatchlistConnector(),
    ]
