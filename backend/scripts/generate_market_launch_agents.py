"""Generate local launchd plist files. Does not install, start, or alter services."""
from __future__ import annotations

import argparse
from pathlib import Path
import plistlib
import sys

from app.config import REPO_ROOT


INTERVALS = {'public-contracts-scotland': '86400', 'renewal-radar': '3600'}


def make_plist(source: str, database_path: Path) -> dict:
    if source not in ('find-a-tender', 'contracts-finder', 'public-contracts-scotland', 'renewal-radar'):
        raise ValueError('Unsupported source')
    root = REPO_ROOT.resolve()
    runtime = root / '.runtime'
    source_slug = source.replace('-', '.')
    return {
        'Label': f'com.misi.market.{source_slug}',
        'ProgramArguments': [str(root / '.venv/bin/python'), str(root / 'backend/scripts/market_monitor.py'),
                             '--watch', '--source', source, '--interval', INTERVALS.get(source, '900'), '--max-pages', '2'],
        'WorkingDirectory': str(root),
        'EnvironmentVariables': {'APP_ENV': 'local', 'PYTHONPATH': str(root / 'backend'),
                                 'DATABASE_URL': 'sqlite:///' + str(database_path.resolve())},
        'RunAtLoad': True,
        'KeepAlive': True,
        'ThrottleInterval': 60,
        'ProcessType': 'Background',
        'StandardOutPath': str(runtime / f'market-{source}.log'),
        'StandardErrorPath': str(runtime / f'market-{source}.error.log'),
    }


def make_backfill_plist(database_path: Path) -> dict:
    root = REPO_ROOT.resolve()
    return {
        'Label': 'com.misi.market.backfill',
        'ProgramArguments': [str(root / '.venv/bin/python'), str(root / 'backend/scripts/market_backfill_watch.py'),
                             '--from-year', '2021', '--to-year', '2025', '--interval', '60',
                             '--daily-budget', '96', '--system-curl'],
        'WorkingDirectory': str(root),
        'EnvironmentVariables': {'APP_ENV': 'local', 'PYTHONPATH': str(root / 'backend'),
                                 'DATABASE_URL': 'sqlite:///' + str(database_path.resolve())},
        'RunAtLoad': True,
        'KeepAlive': {'SuccessfulExit': False},
        'ThrottleInterval': 60,
        'ProcessType': 'Background',
        'StandardOutPath': str(root / '.runtime/market-backfill.log'),
        'StandardErrorPath': str(root / '.runtime/market-backfill.error.log'),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-path', type=Path, required=True, help='Existing local SQLite database file')
    parser.add_argument('--output-dir', type=Path, default=REPO_ROOT / '.runtime' / 'launch-agents')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('launchd agent generation requires macOS')
    if not args.database_path.is_file():
        parser.error('database-path must be an existing SQLite database file')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jobs = [make_plist(source, args.database_path) for source in ('find-a-tender', 'contracts-finder', 'public-contracts-scotland', 'renewal-radar')]
    jobs.append(make_backfill_plist(args.database_path))
    for data in jobs:
        path = args.output_dir / (data['Label'] + '.plist')
        with path.open('wb') as output:
            plistlib.dump(data, output, sort_keys=True)
        path.chmod(0o600)
        print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
