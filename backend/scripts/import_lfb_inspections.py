"""Import an explicitly obtained local official workbook; does not fetch data."""
import argparse
import json
from pathlib import Path
from app.db import SessionLocal
from app.ingestion.lfb_inspections import import_matches

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("workbook", type=Path)
args = parser.parse_args()
with SessionLocal() as db:
    print(json.dumps(import_matches(args.workbook, db)))
