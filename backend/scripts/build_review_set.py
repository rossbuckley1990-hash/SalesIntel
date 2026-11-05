"""Build the frozen, blinded review set for the opportunity-quality evaluation (PR #9).

Run against an ISOLATED COPY of a database, never the live one. It creates (once) an evaluation workspace in that copy,
copies the private-company research records into it with named people removed, and samples the three arms with the
fixed protocol in app/intelligence/opportunity_review.py. Writes the review set (served to reviewers) and the sealed key.

    DATABASE_URL=sqlite:////path/to/copy.db PYTHONPATH=backend .venv/bin/python backend/scripts/build_review_set.py --as-of 2026-11-05
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select

import app.models  # noqa: F401  registers every model
from app.db import SessionLocal
from app.intelligence import opportunity_review as review
from app.models.prospect import Prospect
from app.models.tenancy import Organisation
from app.tenancy import ORG, SYSTEM

OUT = Path(__file__).parents[1] / 'reference_data' / 'evaluation'
SLUG = 'evaluation-reference-profile'


def strip_people(data: dict) -> dict:
    """Named individuals stay out of an evaluation dataset: keep counts, drop names, quotes and personal routes."""
    d = deepcopy(data)
    d['people'] = [{'name': '', 'role': p.get('role', ''), 'source_url': p.get('source_url', '')} for p in d.get('people') or []]
    d['contact_routes'] = [{'kind': r.get('kind', ''), 'label': r.get('label', ''), 'source_url': r.get('source_url', ''), 'value': ''} for r in d.get('contact_routes') or []]
    return d


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--as-of', required=True)
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of)
    with SessionLocal() as system:
        system.info[SYSTEM] = True
        org = system.scalar(select(Organisation).where(Organisation.slug == SLUG))
        if org is None:
            org = Organisation(name='Evaluation (reference profile)', slug=SLUG, created_at=datetime.now(UTC))
            system.add(org)
            system.flush()
        existing = {p.dedup_key for p in system.scalars(select(Prospect).where(Prospect.organisation_id == org.id))}
        for p in system.scalars(select(Prospect).where(Prospect.organisation_id != org.id)):
            if p.dedup_key not in existing and p.status != 'dismissed':
                system.add(Prospect(organisation_id=org.id, dedup_key=p.dedup_key, name=p.name, status='new', data=strip_people(p.data),
                                    created_at=p.created_at, updated_at=p.updated_at))
                existing.add(p.dedup_key)
        system.commit()
        org_id = org.id
    with SessionLocal() as db:
        db.info[ORG] = org_id
        review_set, key = review.build(db, as_of)
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{review_set['set_key']}"
    (OUT / f'{stem}.json').write_text(json.dumps(review_set, indent=1, ensure_ascii=False))
    (OUT / f'{stem}.key.json').write_text(json.dumps(key, indent=1, ensure_ascii=False))
    print(json.dumps({'items': len(review_set['items']), 'pools': key['pools'], 'pool_by_source': key['pool_by_source'],
                      'arms': {a: sum(1 for k in key['items'].values() if a in k['arms']) for a in ('salesintel', 'salesintel_pr8', 'renewal', 'keyword')},
                      'future_evidence_dropped': key['future_evidence_dropped'], 'candidates': key['candidates']}, indent=1))


if __name__ == '__main__':
    main()
