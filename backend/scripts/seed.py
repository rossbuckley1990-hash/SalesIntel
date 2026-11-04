from pathlib import Path
import argparse
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db import SessionLocal, init_db, reset_db  # noqa: E402
from app.services.seed import seed_sample_data  # noqa: E402


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the SalesIntel local database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables before inserting sample data.",
    )
    args = parser.parse_args()

    if args.reset:
        reset_db()
    else:
        init_db()

    with SessionLocal() as db:
        counts = seed_sample_data(db)
    print(f"Inserted sample records: {counts}")
