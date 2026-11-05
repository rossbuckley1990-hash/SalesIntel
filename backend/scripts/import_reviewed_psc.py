"""Import selected manually reviewed corporate-control claims from a JSON file.

These are cached-page snapshots, not continuously refreshed API records or
proof that the current register remains unchanged. Caller supplies the file.
"""
import argparse
import json
from pathlib import Path
from app.db import SessionLocal
from app.services.market_relationships import ingest_reviewed_psc_snapshot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path',type=Path)
    args=parser.parse_args()
    snapshots=json.loads(args.path.read_text(encoding='utf-8'))
    if not isinstance(snapshots,list) or len(snapshots)>100:
        raise ValueError('Expected at most 100 snapshots')
    with SessionLocal() as db:
        try:
            results=[ingest_reviewed_psc_snapshot(db,row) for row in snapshots]
            db.commit()
        except Exception:
            db.rollback(); raise
    print(json.dumps(results,default=str))

if __name__=='__main__': main()
