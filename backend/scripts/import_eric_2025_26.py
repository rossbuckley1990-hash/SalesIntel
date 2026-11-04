"""Preview or explicitly import the official, locally downloaded ERIC site CSV."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.eric_2025_26 import parse_eric_site_data, validate_official_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Local exact NHS England ERIC 2025/26 v2 site CSV")
    parser.add_argument("--retrieved-at", required=True, help="When the CSV was downloaded, as an ISO timestamp with timezone, e.g. 2026-10-28T12:00:00+00:00")
    parser.add_argument("--apply", action="store_true", help="Explicitly import to the configured SalesIntel database; default is preview only")
    args = parser.parse_args()
    try:
        retrieved_at = datetime.fromisoformat(args.retrieved_at.replace("Z", "+00:00"))
        if retrieved_at.utcoffset() is None:
            raise ValueError("--retrieved-at must include a timezone")
        data = args.csv.read_bytes()
        validate_official_file(data)
        observations = parse_eric_site_data(data, retrieved_at=retrieved_at)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Prepared {len(observations)} site observations of general estates backlog; this does not establish fire or security need.")
    if not args.apply:
        print("Preview only. Pass --apply to import into the configured database.")
        return
    from app.db import SessionLocal, init_db
    from app.routers.evidence_observations import import_evidence
    from app.schemas.evidence_observation import EvidenceImportRequest

    init_db()
    imported = duplicates = 0
    with SessionLocal() as db:
        for start in range(0, len(observations), 500):
            result = import_evidence(EvidenceImportRequest(observations=observations[start:start + 500]), db=db)
            imported += result.imported
            duplicates += result.duplicates
    print(f"Imported {imported}; already present {duplicates}.")


if __name__ == "__main__":
    main()
