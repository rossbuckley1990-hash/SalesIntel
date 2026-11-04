"""Preview or import published ERIC location references; no buyer is verified."""
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.eric_site_references import parse_site_references  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--apply", action="store_true", help="Import into the configured database")
    args = parser.parse_args()
    try:
        references = parse_site_references(args.csv.read_bytes())
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    print(f"Prepared {len(references)} published site references with exact numeric UPRNs. Matches are not verified current occupants.")
    if not args.apply:
        print("Preview only; pass --apply to import.")
        return
    from sqlalchemy import select
    from app.db import SessionLocal, init_db
    from app.models.public_site_reference import PublicSiteReference

    init_db()
    with SessionLocal() as db:
        existing = set(db.scalars(select(PublicSiteReference.source_record_id)).all())
        new = [PublicSiteReference(**record) for record in references if record["source_record_id"] not in existing]
        db.add_all(new)
        db.commit()
    print(f"Imported {len(new)}; already present {len(references) - len(new)}.")


if __name__ == "__main__":
    main()
