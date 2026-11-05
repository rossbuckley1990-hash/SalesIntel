"""Time-safe comparison of the Shadow Radar with the renewal and keyword baselines on a SalesIntel database.

  PYTHONPATH=backend python backend/scripts/evaluate_shadow_radar.py --db PATH --out backend/reference_data/shadow_evaluation_YYYY-MM-DD.json

Reads only; writes the report file. Every arm sees only records published by each decision date.
"""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.intelligence.shadow_evaluation import evaluate
from app.models.market_contract import MarketContract
from app.services.shadow import observations
from app.tenancy import SYSTEM


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value and str(value) != 'None' else None
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--horizon', type=int, default=120)
    args = parser.parse_args()
    engine = create_engine(f'sqlite:///file:{Path(args.db).resolve()}?mode=ro&uri=true')
    with Session(engine) as db:
        db.info[SYSTEM] = True
        obs = observations(db)
        contracts = [{'buyer': c.buyer, 'fit': c.fit, 'published': _day(c.facts.get('published')),
                      'end': _day(c.facts.get('published_end_date')) or _day(c.facts.get('estimated_end_date'))} for c in db.scalars(select(MarketContract))]
    data_end = max(o['available_on'] for o in obs)
    first_works = min((o['available_on'] for o in obs if o['signal_type'].startswith('works')), default=data_end)
    # Decision dates every 30 days from when the adjacent-works capture begins, leaving room for at least 60 days of outcomes.
    dates, d = [], first_works + timedelta(days=30)
    while d <= data_end - timedelta(days=60):
        dates.append(d)
        d += timedelta(days=30)
    report = evaluate(obs, contracts, dates, args.horizon, data_end)
    report['inputs'] = {'observations': len(obs), 'works_observations': sum(1 for o in obs if o['signal_type'].startswith('works')), 'contracts': len(contracts),
                        'works_capture_starts': str(first_works)}
    report['limitations'] = [
        'The adjacent-works capture covers only about six months, so outcome windows are short and partly censored at the data end.',
        'Regulator pages hold only the current judgement, so older regulator evidence is missing (inherited from the existing backtest).',
        'Observations were back-filled: their publication dates are real, but SalesIntel did not hold them on those dates. The test assumes it would have.',
        'A hit is entity-level (the organisation bought relevant work), not proof that the specific hypothesis was right.',
        'Small numbers: read the 95% intervals, not the point estimates.']
    Path(args.out).write_text(json.dumps(report, indent=1, default=str))
    print(json.dumps({k: report[k] for k in ('arms', 'by_sensor', 'outcomes_in_window', 'decision_dates', 'inputs')}, indent=1, default=str))


if __name__ == '__main__':
    main()
