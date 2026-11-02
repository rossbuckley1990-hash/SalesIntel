"""Fetch corporate PSC records for explicit company numbers through Companies House.

Uses COMPANIES_HOUSE_API_KEY. Individuals are omitted. Stop on any API error,
including rate limiting; resume manually later. Not a streaming connection.
"""
import argparse
import json
from app.config import get_settings
from app.db import SessionLocal
from app.ingestion.companies_house import fetch_corporate_control_snapshot
from app.services.market_relationships import ingest_reviewed_psc_snapshot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('company_numbers',nargs='+')
    args=parser.parse_args()
    if len(args.company_numbers)>20: parser.error('At most 20 companies per invocation')
    key=get_settings().companies_house_api_key
    with SessionLocal() as db:
        for number in args.company_numbers:
            record=fetch_corporate_control_snapshot(number,api_key=key)
            if not record['controllers']:
                print(json.dumps({'company_number':number,'result':'no eligible corporate controllers; absence not proof'}));continue
            result=ingest_reviewed_psc_snapshot(db,record,from_official_api=True)
            db.commit()
            print(json.dumps({'company_number':number,'result':result},default=str))
if __name__=='__main__':main()
