"""Run the historical backtest on the stored records and write its result as JSON.

Usage: backtest_signal_inference.py OUTPUT_JSON, with DATABASE_URL set. Reads only.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
import json
from pathlib import Path
import sys
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.intelligence.renewal_intelligence import evaluate
from app.intelligence.signal_backtest import incremental_discoveries, prospective_scorecard, run_backtest
from app.intelligence.signal_inference import fire_service_rises, observation, procurement_observations, sequence_observations
from app.models.lfb_incident import LfbIncident
from app.models.market_inference import MarketHypothesis
from app.models.market_network import SourceRevision
from app.services.market_inference import FIRE_DATA_URL, _site_map


def fire_history(db) -> list[dict]:
    """Alarm rises as each would have appeared at a month end, so no later data leaks in."""
    sites = _site_map(db)
    incidents = [(uprn, day) for uprn, day in db.execute(select(LfbIncident.uprn, LfbIncident.incident_date).where(LfbIncident.stop_code_description == 'AFA')) if uprn in sites]
    found = {}
    for year, month in ((y, m) for y in (2025, 2026) for m in range(1, 13)):
        as_of = date(year, month, 1)
        if as_of > date(2026, 11, 1):
            continue
        for rise in fire_service_rises(incidents, as_of=as_of):
            site = sites[rise['uprn']]
            item = observation('false_alarm_rise', statement=f"Attendance rise at {site.site_name}.", occurred=rise['as_of'], available=as_of, url=f"{FIRE_DATA_URL}#{rise['uprn']}", group='fire_service', reliability='statutory_record', buyer=site.organisation_name, fams=['fire_alarm'], scope='site')
            found.setdefault(rise['uprn'] + str(as_of.year), item)
    return list(found.values())


def main() -> int:
    started = time.time()
    with SessionLocal() as db:
        rows = db.scalars(select(SourceRevision).where(SourceRevision.superseded_at.is_(None), SourceRevision.ocid.is_not(None))).all()
        evaluation = evaluate(rows, datetime.now(UTC).date())
        views = [x['view'] for x in evaluation['contracts']]
        fire = fire_history(db)
        observations = procurement_observations(rows) + sequence_observations(views, evaluation['notices']) + fire
        made = [{'decision': x.decision, 'buyer': x.buyer, 'kind': x.kind, 'first_seen': x.first_seen.date()} for x in db.scalars(select(MarketHypothesis))]
        result = {'run_on': datetime.now(UTC).isoformat(), 'backtest': run_backtest(views, evaluation['notices'], observations), 'incremental': incremental_discoveries(views, evaluation['notices'], observations),
                  'prospective': prospective_scorecard(made, evaluation['notices'], datetime.now(UTC).date()),
                  'fire_service_observations': len(fire), 'seconds': round(time.time() - started), 'model_cost': 0}
    Path(sys.argv[1]).write_text(json.dumps(result, indent=1, default=str) + '\n')
    print(json.dumps({k: v for k, v in result['backtest'].items() if k != 'examples'}, indent=0, default=str))
    print(json.dumps(result['incremental']), result['fire_service_observations'], result['seconds'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
