"""Each rep's own sales target, and how far along it is.

A target belongs to one rep: their amount, what it counts, the period and when that period starts. Nothing here is a
forecast. Progress is what the rep has signed in the period and what they have open; what the target implies (wins,
qualified opportunities, a weekly pace) comes from the rep's own planning figures until they have enough closed deals of their
own, and then from those results. Every figure says which it came from.

- What counts is chosen by the rep: new annual contract value (recurring maintenance, a year's worth) or total contract value.
  A deal whose value of that kind is not recorded is counted as a deal, never as £0 and never guessed.
- A deal counts towards the rep who owns it, in the period in which it was marked won.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm import DealRecord, FunnelEvent

BASES = {'annual_contract_value': 'new annual contract value', 'total_contract_value': 'total contract value'}
FIELD = {'annual_contract_value': 'value_annual', 'total_contract_value': 'value_total'}
MONTHS = (12, 6, 3, 1)
ENOUGH = 5  # closed deals of the rep's own before their results replace their planning figures


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year, month = day.year + month // 12, month % 12 + 1
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


def clean(raw: dict | None) -> dict | None:
    """A target as entered, validated. None, or no amount, means the rep has no target set."""
    from app.services.si_engage import money
    if not raw or raw.get('amount') in (None, ''):
        return None
    amount = money(raw['amount'], 'Target')
    if amount <= 0:
        raise ValueError('Target: enter an amount above zero.')
    basis = raw.get('basis') or 'annual_contract_value'
    if basis not in BASES:
        raise ValueError('Target: choose what it counts.')
    try:
        start = date.fromisoformat(str(raw.get('start') or ''))
    except ValueError as exc:
        raise ValueError('Target: give the date the period starts.') from exc
    months = int(raw.get('months') or 12)
    if months not in MONTHS:
        raise ValueError('Target: the period is 12, 6, 3 or 1 months.')
    average = raw.get('average_value')
    average = str(money(average, 'Average deal value')) if average not in (None, '') else None
    if average is not None and Decimal(average) <= 0:
        raise ValueError('Average deal value: enter an amount above zero.')
    per_win = raw.get('qualified_per_win')
    per_win = int(per_win) if per_win not in (None, '') else None
    if per_win is not None and not 1 <= per_win <= 50:
        raise ValueError('Qualified opportunities for each win: between 1 and 50.')
    return {'amount': str(amount), 'basis': basis, 'start': start.isoformat(), 'months': months, 'average_value': average, 'qualified_per_win': per_win}


def _won_on(db: Session, deal_ids: list[int]) -> dict[int, date]:
    """When each deal was marked won, from the record of that step."""
    if not deal_ids:
        return {}
    found: dict[int, date] = {}
    for e in db.scalars(select(FunnelEvent).where(FunnelEvent.event == 'deal_won', FunnelEvent.deal_id.in_(deal_ids)).order_by(FunnelEvent.id)):
        found[e.deal_id] = e.day
    return found


def progress(db: Session, rep: dict | None, today: date | None = None) -> dict | None:
    """How far along a rep's target is. None when the rep has set no target."""
    target = (rep or {}).get('sales_target')
    if not target:
        return None
    today = today or date.today()
    amount, basis, field = float(target['amount']), target['basis'], FIELD[target['basis']]
    start = date.fromisoformat(target['start'])
    end = add_months(start, int(target['months'])) - timedelta(days=1)
    deals = db.scalars(select(DealRecord).where(DealRecord.owner_rep == rep['name'])).all()
    won_on = _won_on(db, [d.id for d in deals if d.stage == 'won'])

    def value(d: DealRecord) -> float | None:
        v = getattr(d, field)
        return None if v is None else float(v)

    signed = [d for d in deals if d.stage == 'won' and start <= won_on.get(d.id, d.updated_at.date()) <= end]
    open_ = [d for d in deals if d.stage not in ('won', 'lost')]
    closed = [d for d in deals if d.stage in ('won', 'lost')]
    won_all = [d for d in closed if d.stage == 'won']
    signed_value = sum(v for d in signed if (v := value(d)) is not None)
    remaining = max(0.0, amount - signed_value)
    status = 'not_started' if today < start else 'ended' if today > end else 'running'
    days_left = (end - today).days + 1 if status == 'running' else (end - start).days + 1 if status == 'not_started' else 0
    weeks_left = math.ceil(days_left / 7) if days_left else 0

    # The rep's own results replace their planning figures once there are enough of them.
    won_values = [v for d in won_all if (v := value(d)) is not None]
    actual = len(closed) >= ENOUGH and bool(won_all) and bool(won_values)
    if actual:
        source, average, per_win = 'results', sum(won_values) / len(won_values), len(closed) / len(won_all)
    else:
        source = 'planning' if target.get('average_value') or target.get('qualified_per_win') else None
        average = float(target['average_value']) if target.get('average_value') else None
        per_win = float(target['qualified_per_win']) if target.get('qualified_per_win') else None
    needed = None
    if remaining > 0 and average and status != 'ended':
        wins = math.ceil(remaining / average)
        qualified = math.ceil(wins * per_win) if per_win else None
        to_find = max(0, qualified - len(open_)) if qualified is not None else None
        needed = {'wins': wins, 'qualified': qualified, 'to_find': to_find,
                  'per_week': round(to_find / weeks_left, 1) if to_find is not None and weeks_left else None}
    return {'amount': amount, 'basis': basis, 'basis_label': BASES[basis], 'start': start.isoformat(), 'end': end.isoformat(), 'months': int(target['months']),
            'status': status, 'weeks_left': weeks_left, 'remaining': remaining, 'reached': signed_value >= amount,
            'signed': {'value': signed_value, 'deals': len(signed), 'unvalued': sum(1 for d in signed if value(d) is None)},
            'open': {'value': sum(v for d in open_ if (v := value(d)) is not None), 'deals': len(open_), 'unvalued': sum(1 for d in open_ if value(d) is None)},
            'figures': {'source': source, 'average_value': average, 'qualified_per_win': per_win, 'closed': len(closed), 'won': len(won_all), 'enough': ENOUGH},
            'needed': needed}
