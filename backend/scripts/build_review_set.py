"""Build the frozen, blinded review set for the opportunity-quality evaluation (protocol v2).

Run against an ISOLATED COPY of a database, never the live one. It:
- creates (once) an evaluation workspace in that copy, and copies the private-company research records into it with
  named people removed;
- draws a random seed and salt, and samples every arm with the protocol in app/intelligence/opportunity_review.py;
- excludes every lead published in the withdrawn v1 set.

It writes three things:
- the review set, which is served to reviewers;
- the public commitment (dataset hash, salted key hash, protocol, code version), both into the repository;
- the private key, OUTSIDE the repository (file mode 600). That key, together with the database snapshot, reproduces
  the set exactly. It is supplied to the app only after the review is complete and locked, and it is accepted only if it
  matches the commitment.

Usage:

    DATABASE_URL=sqlite:////path/to/copy.db PYTHONPATH=backend .venv/bin/python backend/scripts/build_review_set.py \
        --as-of 2026-11-05 --exclude-from /path/to/withdrawn-v1.key.json --key-dir ~/.salesintel/evaluation

    .venv/bin/python backend/scripts/build_review_set.py --verify ~/.salesintel/evaluation/<set>.key.json   # check a key
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path

OUT = Path(__file__).parents[1] / 'reference_data' / 'evaluation'
REPO = Path(__file__).parents[2]
SLUG = 'evaluation-reference-profile'


def strip_people(data: dict) -> dict:
    """Named individuals stay out of an evaluation dataset: keep counts, drop names, quotes and personal routes."""
    d = deepcopy(data)
    d['people'] = [{'name': '', 'role': p.get('role', ''), 'source_url': p.get('source_url', '')} for p in d.get('people') or []]
    d['contact_routes'] = [{'kind': r.get('kind', ''), 'label': r.get('label', ''), 'source_url': r.get('source_url', ''), 'value': ''} for r in d.get('contact_routes') or []]
    return d


def code_version() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True, check=False).stdout.strip()
    return {'commit': git('rev-parse', 'HEAD'), 'tracked_changes': bool(git('status', '--porcelain', '--untracked-files=no'))}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def verify(path: Path) -> None:
    from app.intelligence import opportunity_review as review
    key = json.loads(path.read_text())
    commitment = json.loads((OUT / f"{key['set_key']}.commitment.json").read_text())
    data = json.loads((OUT / f"{key['set_key']}.json").read_text())
    review.verify_key(commitment, key)
    assert review.digest(data) == commitment['dataset_sha256'] and set(key['items']) == {i['id'] for i in data['items']}
    print(f"Verified: {path.name} matches the commitment for {key['set_key']} ({len(key['items'])} items).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--as-of')
    parser.add_argument('--exclude-from', help='a withdrawn set\'s key file: every lead it contains is excluded from the frames')
    parser.add_argument('--exclude-list', help='a JSON list of {"lead_key": ...}: leads already published with their method, excluded too')
    parser.add_argument('--key-dir', default=str(Path.home() / '.salesintel' / 'evaluation'))
    parser.add_argument('--replace', action='store_true', help='overwrite an existing set (only before anyone has reviewed it)')
    parser.add_argument('--verify', help='check a private key against the committed set, and stop')
    args = parser.parse_args()
    if args.verify:
        verify(Path(args.verify).expanduser())
        return
    from sqlalchemy import select

    import app.models  # noqa: F401  registers every model
    from app.config import get_settings
    from app.db import SessionLocal
    from app.intelligence import opportunity_review as review
    from app.models.prospect import Prospect
    from app.models.tenancy import Organisation
    from app.tenancy import ORG, SYSTEM

    as_of = date.fromisoformat(args.as_of)
    key_dir = Path(args.key_dir).expanduser()
    if REPO in key_dir.resolve().parents or key_dir.resolve() == REPO:
        raise SystemExit('The key must be written outside the repository.')
    exclude: set[str] = set()
    if args.exclude_from:
        withdrawn = json.loads(Path(args.exclude_from).expanduser().read_text())
        exclude = {v['lead_key'] for v in withdrawn['items'].values()}
    exposed: set[str] = set()
    if args.exclude_list:
        exposed = {x['lead_key'] for x in json.loads(Path(args.exclude_list).expanduser().read_text())}
        exclude |= exposed
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
    seed, salt = secrets.randbelow(2 ** 31), secrets.token_hex(32)
    with SessionLocal() as db:
        db.info[ORG] = org_id
        review_set, key = review.build(db, as_of, seed=seed, salt=salt, exclude=exclude)
    stem = review_set['set_key']
    if (OUT / f'{stem}.json').exists() and not args.replace:
        raise SystemExit(f'{stem} already exists. A frozen set is never redrawn once anyone may have seen it.')
    database = get_settings().database_url.removeprefix('sqlite:///')
    key['built'] = {'at': datetime.now(UTC).isoformat(timespec='seconds'), 'code': code_version(),
                    'database': {'path': database, 'sha256': file_sha256(Path(database)) if os.path.exists(database) else None},
                    'excluded_leads': sorted(exclude), 'exclude_from': Path(args.exclude_from).name if args.exclude_from else None,
                    'excluded_as_published': sorted(exposed), 'exclude_list': Path(args.exclude_list).name if args.exclude_list else None}
    commitment = {**review.commit(review_set, key), 'created_at': key['built']['at'], 'code': key['built']['code']}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{stem}.json').write_text(json.dumps(review_set, indent=1, ensure_ascii=False) + '\n')
    (OUT / f'{stem}.commitment.json').write_text(json.dumps(commitment, indent=1, ensure_ascii=False) + '\n')
    key_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(key_dir, 0o700)
    key_file = key_dir / f'{stem}.key.json'
    key_file.write_text(json.dumps(key, indent=1, ensure_ascii=False) + '\n')
    os.chmod(key_file, 0o600)
    print(json.dumps({'set_key': stem, 'items': len(review_set['items']), 'pools': key['pools'], 'frames': key['frames'],
                      'excluded_published': key['excluded_published'], 'unjudgeable': key['unjudgeable'],
                      'sampled': {a: sum(1 for k in key['items'].values() if a in k['sampled_by']) for a in review.ARMS},
                      'future_evidence_dropped': key['future_evidence_dropped'], 'key': str(key_file)}, indent=1))


if __name__ == '__main__':
    main()
