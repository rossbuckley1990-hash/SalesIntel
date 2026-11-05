"""Shadow Radar fixtures: the real 5 November 2026 Contracts Finder capture, plus one clearly synthetic organisation.

Real notices are classified exactly as the live collector would, and no research is replayed about
real organisations. The synthetic organisation (".example" domains) exercises deep research,
contacts and outreach end to end, with corroborating and contradicting evidence.
"""
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.ingestion.adjacent_works import load_capture, store_append_only
from app.intelligence.signal_inference import observation
from app.services import shadow

CAPTURE = Path(__file__).resolve().parents[2] / 'reference_data' / 'adjacent_works_capture_2026-11-05.json'
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)

SYNTHETIC = [
    observation('works_awarded', statement='Harbourside Community Health awarded "Harbourside Community Diagnostic Centre - Main Works" valued at £14,200,000 to Northbank Construction Ltd.',
                occurred=date(2026, 8, 1), available=date(2026, 8, 14), url='https://notices.example/harbourside-cdc-award', group='procurement', reliability='official_notice',
                buyer='Harbourside Community Health', supplier='Northbank Construction Ltd',
                detail={'works_type': 'new_build', 'building_type': 'healthcare', 'value': 14_200_000, 'notice_type': 'Contract', 'title': 'Harbourside Community Diagnostic Centre - Main Works',
                        'publisher': 'Harbourside Community Health', 'beneficiary_inferred': False, 'postcode': 'HB1 1AA', 'source': 'Synthetic fixture', 'project': 'synthetic-harbourside-cdc'}),
    observation('estate_expansion', statement='Example Borough Council granted planning permission for a community diagnostic centre at Quay Street for Harbourside Community Health.',
                occurred=date(2026, 5, 20), available=date(2026, 5, 22), url='https://planning.example/quay-street-cdc', group='planning', reliability='statutory_record',
                buyer='Harbourside Community Health', detail={'publisher': 'Example Borough Council', 'source': 'Synthetic fixture'}),
]


def load(db: Session, *, real: bool = True) -> dict:
    """Load the fixtures in a system session and refresh the radar as of 5 November 2026."""
    got = load_capture(db, CAPTURE) if real else {}
    made = store_append_only(db, SYNTHETIC, NOW)
    return {'real_capture': got, 'synthetic': made, 'radar': shadow.refresh(db, now=NOW, as_of=date(2026, 11, 5))}
