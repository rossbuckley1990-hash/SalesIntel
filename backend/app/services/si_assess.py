"""Can we win this? Four separate answers that are never blended into one score.

1. Commercial fit: rule-based, from what this workspace sells and covers and what the deal
   records. Each criterion is met, a gap or unknown, with the evidence or the missing fact.
2. Win readiness: what the team has established for this deal, and the specific action for
   each gap.
3. Seller confidence: the salesperson's own view, shown as theirs.
4. Win probability: only an empirical rate from this workspace's own comparable closed deals,
   and only when there are enough of them *and* the method predicted held-out outcomes better
   than the workspace's plain win rate. Otherwise it says so. No language model is asked for a
   percentage, and nothing here is presented as a forecast of a particular customer's decision.
"""
from __future__ import annotations

from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm import Activity, Contact, DealRecord, Task
from app.services.si_core import preferences
from app.services.si_engage import SERVICE_LABEL, WORK_TYPES, quote_is_current

MIN_COMPARABLE = 30      # comparable closed deals before any rate is shown
MIN_EACH_OUTCOME = 5     # at least this many wins and this many losses among them
HOLDOUT_SHARE = 0.3      # the most recent share of closed deals used to test the method
MIN_HOLDOUT = 10
INSUFFICIENT = 'Insufficient historical data for a reliable win probability.'
ENGAGED = {'connected', 'interested', 'meeting_booked', 'requirement_captured', 'call_back'}


def _criterion(key, label, status, evidence, action=''):
    return {'key': key, 'label': label, 'status': status, 'evidence': evidence, 'action': action}


def commercial_fit(db: Session, deal: DealRecord) -> dict:
    prefs = preferences(db)
    ours, territory = set(prefs['services']), [t.lower() for t in prefs['territory']]
    items = []
    if not deal.services:
        items.append(_criterion('services', 'Services we deliver', 'unknown', 'The services in scope are not recorded.', 'Choose the services in scope on the deal.'))
    elif not ours:
        items.append(_criterion('services', 'Services we deliver', 'unknown', 'This workspace has not recorded which services it delivers.',
                                'Record your services in Settings so fit can be checked.'))
    else:
        missing = [SERVICE_LABEL.get(s, s) for s in deal.services if s not in ours]
        items.append(_criterion('services', 'Services we deliver', 'gap' if missing else 'met',
                                f"Not in our recorded services: {', '.join(missing)}." if missing else 'Every service in scope is one we record as delivering.',
                                'Confirm a partner or subcontractor before bidding, or remove the service.' if missing else ''))
    region = ' '.join(str(x) for x in ((deal.origin or {}).get('nation'), (deal.origin or {}).get('region')) if x).strip()
    if not territory:
        items.append(_criterion('territory', 'Within our territory', 'unknown', 'This workspace has not recorded its territory.', 'Record your territory in Settings.'))
    elif not region:
        items.append(_criterion('territory', 'Within our territory', 'unknown', 'The location of the work is not recorded.', 'Record the sites in scope.'))
    else:
        inside = any(t in region.lower() for t in territory)
        items.append(_criterion('territory', 'Within our territory', 'met' if inside else 'gap', f'Recorded location: {region}.',
                                '' if inside else 'Confirm engineer coverage for this location before claiming response times.'))
    if deal.value_total is None and deal.value_annual is None:
        items.append(_criterion('value', 'Contract value known', 'unknown', 'No value is published or estimated.', 'Ask the buyer for the budget or estimate it from the scope.'))
    else:
        basis = {'published': 'published', 'published_derived': 'derived from published figures', 'user_estimate': 'your estimate'}.get(deal.value_basis, deal.value_basis)
        amount = f"£{deal.value_total:,.0f} total" if deal.value_total is not None else f"£{deal.value_annual:,.0f} a year"
        items.append(_criterion('value', 'Contract value known', 'met', f'{amount} ({basis}).'))
    items.append(_criterion('work_type', 'Type of work defined', 'met' if deal.work_type else 'unknown',
                            WORK_TYPES.get(deal.work_type, 'Not recorded.') if deal.work_type else 'Not recorded.',
                            '' if deal.work_type else 'Record whether this is maintenance, remedial works or installation.'))
    items.append(_criterion('accreditations', 'Required accreditations held', 'unknown',
                            'The required accreditations and the ones you hold are not recorded, so compliance is not assumed.',
                            "Record the buyer's required accreditations and evidence that you hold each one."))
    return {'criteria': items, 'met': sum(i['status'] == 'met' for i in items), 'gaps': sum(i['status'] == 'gap' for i in items),
            'unknown': sum(i['status'] == 'unknown' for i in items)}


def win_readiness(db: Session, deal: DealRecord) -> dict:
    q = deal.qualification or {}
    activities = db.scalars(select(Activity).where(Activity.account_id == deal.account_id)).all()
    contacts = db.scalars(select(Contact).where(Contact.account_id == deal.account_id, Contact.status != 'do_not_contact')).all()
    open_tasks = db.scalars(select(Task).where(Task.deal_id == deal.id, Task.status == 'open')).all()
    scope_entries = [v for s in (deal.scope or {}).values() for v in s.values()]
    estimated = [v for v in scope_entries if v.get('basis') == 'estimate']
    engaged = [a for a in activities if a.outcome in ENGAGED]

    def item(key, label, done, evidence, action):
        return {'key': key, 'label': label, 'status': 'done' if done else 'missing', 'evidence': evidence if done else '', 'action': '' if done else action}
    items = [
        item('requirement', "Customer's requirement recorded", bool(q.get('requirement')), q.get('requirement', ''), "Record the customer's requirement in their words."),
        item('decision_maker', 'Decision-maker identified', bool(q.get('decision_maker')), q.get('decision_maker', ''), 'Find out who signs off the contract and who influences it.'),
        item('relationship', 'Two-way contact established', bool(engaged), f'{len(engaged)} conversation(s) with a response recorded.',
             'Have a conversation with the buyer and log what you learned.'),
        item('contact_route', 'Usable contact route', bool(contacts), f'{len(contacts)} contact route(s) on the account.', 'Find the right people and a legitimate business contact route.'),
        item('timing', 'Timing understood', bool(q.get('timing')), q.get('timing', ''), 'Confirm when the buyer intends to decide and start.'),
        item('budget', 'Budget understood', bool(q.get('budget')), q.get('budget', ''), 'Establish the budget or how the buyer will evaluate price.'),
        item('incumbent', 'Incumbent position known', bool(q.get('incumbent')), q.get('incumbent', ''), 'Find out who delivers the service now and what the buyer thinks of it.'),
        item('scope', 'Scope surveyed or stated by the customer', bool(scope_entries) and not estimated,
             f'{len(scope_entries)} scope fact(s), none estimated.', 'Replace estimated quantities with surveyed or customer-stated figures.'
             if estimated else 'Capture the scope: sites, devices and visit frequency.'),
        item('quotation', 'Current quotation approved', quote_is_current(deal), f"Version {(deal.quote or {}).get('version')} approved.",
             'Build the quotation and have it approved by someone other than the deal owner.'),
        item('next_step', 'Next step scheduled', bool(open_tasks), open_tasks[0].title if open_tasks else '', 'Schedule the next action with a date.'),
    ]
    return {'items': items, 'done': sum(i['status'] == 'done' for i in items), 'total': len(items)}


# ---------------------------------------------------------------- empirical probability

def _comparable(target: DealRecord, pool: list[DealRecord]) -> list[DealRecord]:
    services = set(target.services)
    return [d for d in pool if d.id != target.id and services & set(d.services) and (not target.work_type or d.work_type == target.work_type)]


def _rate(wins: int, n: int) -> float:
    return (wins + 1) / (n + 2)  # Laplace-smoothed, so a small cohort is pulled towards one half


def _wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = wins / n
    centre, spread = (p + z * z / (2 * n)) / (1 + z * z / n), z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - spread), min(1.0, centre + spread)


def validate(closed: list[DealRecord]) -> dict | None:
    """Time-ordered backtest: predict each recent closed deal only from deals that closed before it."""
    ordered = sorted(closed, key=lambda d: d.updated_at)
    holdout = max(MIN_HOLDOUT, int(len(ordered) * HOLDOUT_SHARE))
    if len(ordered) - holdout < MIN_COMPARABLE // 2:
        return None
    method, baseline = [], []
    for i in range(len(ordered) - holdout, len(ordered)):
        deal, earlier = ordered[i], ordered[:i]
        cohort = _comparable(deal, earlier)
        if not cohort:
            continue
        actual = 1.0 if deal.stage == 'won' else 0.0
        method.append((_rate(sum(d.stage == 'won' for d in cohort), len(cohort)) - actual) ** 2)
        baseline.append((_rate(sum(d.stage == 'won' for d in earlier), len(earlier)) - actual) ** 2)
    if len(method) < MIN_HOLDOUT:
        return None
    return {'holdout_deals': len(method), 'brier': round(sum(method) / len(method), 4), 'baseline_brier': round(sum(baseline) / len(baseline), 4)}


def win_probability(db: Session, deal: DealRecord) -> dict:
    closed = db.scalars(select(DealRecord).where(DealRecord.stage.in_(['won', 'lost']))).all()
    cohort = _comparable(deal, closed)
    wins = sum(d.stage == 'won' for d in cohort)
    base = {'available': False, 'message': INSUFFICIENT, 'comparable_outcomes': len(cohort), 'wins': wins, 'losses': len(cohort) - wins,
            'required': MIN_COMPARABLE, 'comparable_rule': 'Closed deals in this workspace sharing a service and the same type of work.'}
    if len(cohort) < MIN_COMPARABLE or min(wins, len(cohort) - wins) < MIN_EACH_OUTCOME:
        return base | {'reason': f'{len(cohort)} comparable closed deal(s); at least {MIN_COMPARABLE}, with {MIN_EACH_OUTCOME} wins and {MIN_EACH_OUTCOME} losses, are needed.'}
    check = validate(closed)
    if check is None:
        return base | {'reason': 'Not enough recent closed deals to test the method against outcomes.'}
    if check['brier'] >= check['baseline_brier']:
        return base | {'reason': "On this workspace's recent deals, comparable-deal rates predicted outcomes no better than the overall win rate.", 'validation': check}
    low, high = _wilson(wins, len(cohort))
    return {'available': True, 'estimate': round(wins / len(cohort), 3), 'interval': [round(low, 3), round(high, 3)], 'comparable_outcomes': len(cohort),
            'wins': wins, 'losses': len(cohort) - wins, 'validation': check,
            'method': 'Win rate of comparable closed deals in this workspace, with a 95% Wilson interval. Validated by predicting the most recent closed deals '
                      'from earlier ones and comparing the Brier score with the overall win rate.',
            'limitations': ['Describes how similar deals ended for this team, not what this customer will decide.',
                            'Comparable means sharing a service and the type of work; size, sector and relationship are not controlled for.',
                            'Recorded outcomes only: deals never logged as won or lost are not counted.']}


def assessment(db: Session, deal_id: int) -> dict:
    deal = db.get(DealRecord, deal_id)
    if deal is None:
        raise LookupError('Deal not found')
    labels = {'low': 'Low', 'medium': 'Medium', 'high': 'High'}
    return {'deal_id': deal.id, 'commercial_fit': commercial_fit(db, deal), 'win_readiness': win_readiness(db, deal),
            'seller_confidence': {'value': deal.seller_confidence, 'label': labels.get(deal.seller_confidence or ''), 'basis': "The salesperson's own judgement."},
            'win_probability': win_probability(db, deal)}
