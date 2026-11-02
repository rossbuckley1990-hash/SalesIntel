"""Fetch explicit UK company numbers from the authenticated Companies House API.

Set COMPANIES_HOUSE_API_KEY in the environment. Pass company numbers (not names)
that have already been resolved from reliable sources. No automatic name merges.
"""
import argparse
import json
import sys

from app.config import get_settings
from app.db import SessionLocal
from app.ingestion.companies_house import CompaniesHouseError, fetch_company_profile
from app.services.market_network import ingest_market_company


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('company_numbers', nargs='+', help='Companies House company numbers')
    args = parser.parse_args()
    if len(args.company_numbers) > 20:
        parser.error('At most 20 companies per invocation')
    key = get_settings().companies_house_api_key
    if not key:
        print('Companies House API key is not configured.', file=sys.stderr)
        return 1
    failures = 0
    with SessionLocal() as db:
        for number in args.company_numbers:
            try:
                record = fetch_company_profile(number, api_key=key)
                result = ingest_market_company(db, record)
                db.commit()
                print(json.dumps({'company_number': record['release_id'], 'result': result}, default=str))
            except (CompaniesHouseError, ValueError) as exc:
                db.rollback()
                print(json.dumps({'company_number': number, 'error': str(exc)}), file=sys.stderr)
                failures += 1
                # Stop after a rate limit or access failure; do not repeatedly send requests.
                if 'rate limit' in str(exc) or 'HTTP 401' in str(exc) or 'HTTP 403' in str(exc):
                    break
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
