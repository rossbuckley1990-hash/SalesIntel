"""Preview or atomically replace the local LFB incident snapshot."""
import argparse
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.lfb_incidents import DOWNLOAD_URL, SOURCE_URL, import_workbook  # noqa: E402

MAX_DOWNLOAD = 200 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Official dataset URL redirected; review the destination before updating the importer.")


def download_official(destination: Path) -> datetime:
    """Download only the fixed HTTPS official URL, bounded in memory and size."""
    total = 0
    opener = build_opener(NoRedirect())
    request = Request(DOWNLOAD_URL, headers={"User-Agent": "Mozilla/5.0 SalesIntel-public-data-import/1.0"})
    with opener.open(request, timeout=120) as response, destination.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_DOWNLOAD:
                raise ValueError("Dataset exceeds the 200 MiB download limit.")
            out.write(chunk)
    if not total:
        raise ValueError("The dataset download was empty.")
    return datetime.now(UTC)


def process(path: Path, apply: bool, retrieved_at: datetime | None, acquisition_method: str):
    if apply:
        from app.db import SessionLocal, init_db
        init_db()
        with SessionLocal() as db:
            return import_workbook(path, db, retrieved_at=retrieved_at, acquisition_method=acquisition_method)
    return import_workbook(path, retrieved_at=retrieved_at, acquisition_method=acquisition_method)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, nargs="?", help="Locally downloaded LFB incident workbook")
    parser.add_argument("--download", action="store_true", help="Download the current workbook from the fixed official LFB source to a temporary file")
    parser.add_argument("--retrieved-at", help="Local file download time in ISO format with timezone; unknown when omitted")
    parser.add_argument("--apply", action="store_true", help="Replace the configured database's incident snapshot; default is preview only")
    args = parser.parse_args()
    if bool(args.workbook) == bool(args.download):
        parser.error("Provide either a local workbook or --download.")
    if args.download and args.retrieved_at:
        parser.error("--retrieved-at is recorded automatically with --download.")
    try:
        retrieved_at = datetime.fromisoformat(args.retrieved_at.replace("Z", "+00:00")) if args.retrieved_at else None
        if retrieved_at is not None and retrieved_at.utcoffset() is None:
            raise ValueError("--retrieved-at must include a timezone.")
        if args.download:
            with tempfile.TemporaryDirectory(prefix="misi-lfb-") as temp_dir:
                path = Path(temp_dir) / "LFB Incident data from 2024 onwards.xlsx"
                retrieved_at = download_official(path)
                result = process(path, args.apply, retrieved_at, "official_download")
        else:
            result = process(args.workbook, args.apply, retrieved_at, "local_file")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"LFB source: {SOURCE_URL} (Open Government Licence v2). File SHA-256: {result.sha256}")
    if result.already_imported:
        print("The identical file has already been imported; no changes made.")
        return
    print(f"Rows read: {result.rows_seen}; retained non-residential UPRN incidents: {result.records_imported}; excluded: {result.rows_excluded}; eligible incident dates: {result.min_date} to {result.max_date}.")
    print("Data covers attended incidents only, not all alarm activations. AFA does not establish a faulty system or supplier failure.")
    if not args.apply:
        print("Preview only. Use --apply to replace the configured database snapshot.")


if __name__ == "__main__":
    main()
