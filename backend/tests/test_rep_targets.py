"""Each rep's own sales target, on fictional records.

- A target belongs to one rep: their amount, what it counts, the period and its start. No figure or period is built in.
- Progress is what that rep signed in the period, and what they have open. A deal without a value of the counted kind is a
  deal, never £0 and never guessed.
- What the target implies comes from the rep's planning figures, then from their own results once they have five closed deals,
  and says which. It is a plan, never a forecast.
- A deal belongs to the rep whose patch was on screen when it was created, unless another rep is chosen; a won deal keeps its owner."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base, get_db
from app.main import create_app
from app.models.crm import Account, DealRecord, FunnelEvent
from app.services import living_fixtures, patch, targets
from app.services import si_engage as engage

TODAY = date(2026, 11, 16)
SAM = {'amount': '300000', 'basis': 'annual_contract_value', 'start': '2026-11-01', 'months': 12, 'average_value': '50000', 'qualified_per_win': 4}


@pytest.fixture
def local(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'targets.db'}", connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    db = Session(engine)
    keys = living_fixtures.load(db, date.today())
    db.commit()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db, keys
    db.close()
    engine.dispose()


def account(db, name: str = 'Example Homes Ltd') -> Account:
    a = Account(name=name, key=name.lower(), kind='private', status='prospect', watched=False, notes='', created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(a)
    db.flush()
    return a


def deal(db, owner: str | None, stage: str, *, annual: float | None = None, total: float | None = None, won_on: date | None = None) -> DealRecord:
    d = DealRecord(account_id=account(db, f'Example {owner} {stage} {annual} {total} {won_on}').id, title='Fire alarm maintenance', stage=stage, origin={}, services=[],
                   qualification={}, value_annual=annual, value_total=total, value_basis='user_estimate', scope={}, quote={}, handover={}, outcome_reason='',
                   owner_rep=owner, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(d)
    db.flush()
    if won_on:
        db.add(FunnelEvent(event='deal_won', day=won_on, deal_id=d.id))
    db.flush()
    return d


def test_a_target_is_what_the_rep_entered_and_nothing_is_built_in():
    assert targets.clean(None) is None and targets.clean({'amount': ''}) is None  # no target set is allowed
    assert targets.clean({'amount': '£250,000', 'start': '2027-04-01'}) == {'amount': '250000', 'basis': 'annual_contract_value', 'start': '2027-04-01', 'months': 12,
                                                                           'average_value': None, 'qualified_per_win': None}
    assert targets.clean({**SAM, 'months': 3})['months'] == 3
    for bad, message in (({'amount': '0', 'start': '2026-11-01'}, 'above zero'), ({'amount': '100', 'start': ''}, 'period starts'),
                         ({'amount': '100', 'start': '2026-11-01', 'months': 7}, '12, 6, 3 or 1'), ({'amount': '100', 'start': '2026-11-01', 'basis': 'gross_margin'}, 'what it counts'),
                         ({'amount': '100', 'start': '2026-11-01', 'qualified_per_win': 0}, 'between 1 and 50'), ({'amount': '-5', 'start': '2026-11-01'}, 'negative')):
        with pytest.raises(ValueError, match=message):
            targets.clean(bad)
    assert targets.add_months(date(2026, 11, 1), 12) == date(2027, 11, 1) and targets.add_months(date(2027, 1, 31), 1) == date(2027, 2, 28)


def test_progress_counts_the_reps_own_deals_signed_in_the_period(local):
    _client, db, _keys = local
    rep = {'name': 'Sam North', 'sales_target': SAM}
    deal(db, 'Sam North', 'won', annual=60000, won_on=date(2026, 11, 10))           # counts
    deal(db, 'Sam North', 'won', total=180000, won_on=date(2026, 11, 12))           # counts as a deal; its annual value is not recorded
    deal(db, 'Sam North', 'won', annual=90000, won_on=date(2026, 10, 30))           # before the period
    deal(db, 'Jo West', 'won', annual=500000, won_on=date(2026, 11, 11))            # another rep's
    deal(db, 'Sam North', 'proposal', annual=40000)
    deal(db, 'Sam North', 'qualify')
    deal(db, 'Sam North', 'lost', annual=30000)
    db.commit()
    p = targets.progress(db, rep, TODAY)
    assert (p['start'], p['end'], p['status'], p['weeks_left']) == ('2026-11-01', '2027-10-31', 'running', 50)
    assert p['signed'] == {'value': 60000.0, 'deals': 2, 'unvalued': 1} and p['open'] == {'value': 40000.0, 'deals': 2, 'unvalued': 1}
    assert p['remaining'] == 240000.0 and not p['reached'] and p['basis_label'] == 'new annual contract value'
    # from the planning figures: £240k at £50k a win is 5 wins; at 4 qualified for each win, 20; 2 are already open, so 18 to find over 50 weeks
    assert p['needed'] == {'wins': 5, 'qualified': 20, 'to_find': 18, 'per_week': 0.4} and p['figures']['source'] == 'planning'
    # counting total contract value instead
    tcv = targets.progress(db, {**rep, 'sales_target': {**SAM, 'basis': 'total_contract_value'}}, TODAY)
    assert tcv['signed'] == {'value': 180000.0, 'deals': 2, 'unvalued': 1} and tcv['remaining'] == 120000.0
    assert targets.progress(db, {'name': 'Sam North', 'sales_target': None}, TODAY) is None


def test_the_reps_own_results_replace_the_planning_figures_once_there_are_enough(local):
    _client, db, _keys = local
    rep = {'name': 'Ana Reid', 'sales_target': {**SAM, 'start': '2026-04-01'}}
    for annual in (20000, 40000):
        deal(db, 'Ana Reid', 'won', annual=annual, won_on=date(2026, 6, 1))
    for _ in range(3):
        deal(db, 'Ana Reid', 'lost', annual=10000)
    db.commit()
    p = targets.progress(db, rep, TODAY)
    # five closed, two won: an average won value of £30k, and 2.5 qualified for each win
    assert p['figures'] == {'source': 'results', 'average_value': 30000.0, 'qualified_per_win': 2.5, 'closed': 5, 'won': 2, 'enough': 5}
    assert p['needed']['wins'] == 8 and p['needed']['qualified'] == 20  # £240k still to sign at £30k a win; 8 wins at 2.5 each


def test_before_and_after_the_period_and_a_reached_target(local):
    _client, db, _keys = local
    early = targets.progress(db, {'name': 'X', 'sales_target': {**SAM, 'start': '2027-01-01'}}, TODAY)
    assert early['status'] == 'not_started' and early['weeks_left'] == 53
    late = targets.progress(db, {'name': 'X', 'sales_target': {**SAM, 'start': '2025-01-01'}}, TODAY)
    assert late['status'] == 'ended' and late['weeks_left'] == 0 and late['needed'] is None
    deal(db, 'Lee', 'won', annual=320000, won_on=date(2026, 11, 2))
    db.commit()
    done = targets.progress(db, {'name': 'Lee', 'sales_target': SAM}, TODAY)
    assert done['reached'] and done['remaining'] == 0 and done['needed'] is None


def test_a_reps_target_is_saved_with_their_patch_and_shown_on_the_brief(local):
    client, _db, _keys = local
    saved = client.put('/api/si/patch/reps', json={'name': 'Sam North', 'regions': [], 'services': [], 'sectors': [], 'targets': [], 'sales_target': SAM})
    v = saved.json()
    assert saved.status_code == 200 and v['rep']['sales_target'] == {**SAM, 'months': 12}
    assert v['target']['amount'] == 300000.0 and v['target']['signed']['value'] == 0 and v['target']['needed']['wins'] == 6
    assert '%' not in str(v['target'])
    line = next(l for l in v['text'].splitlines() if l.startswith('Your target:'))
    assert line.startswith('Your target: £300,000 new annual contract value, 1 November 2026 to 31 October 2027. Signed so far: £0 from 0 deals.')
    assert 'a plan, not a forecast' in line and 'from your planning figures' in line
    bad = client.put('/api/si/patch/reps', json={'name': 'Sam North', 'sales_target': {**SAM, 'amount': 'lots'}})
    assert bad.status_code in (400, 422)
    # another rep keeps their own target, or none
    other = client.put('/api/si/patch/reps', json={'name': 'Jo West', 'regions': [], 'services': [], 'sectors': [], 'targets': []}).json()
    assert other['target'] is None and other['rep']['sales_target'] is None
    assert client.get('/api/si/patch', params={'rep': 'Sam North'}).json()['target']['amount'] == 300000.0


def test_a_deal_belongs_to_the_rep_on_screen_unless_another_is_chosen(local):
    client, db, keys = local
    client.put('/api/si/patch/reps', json={'name': 'Jo West', 'regions': [], 'services': [], 'sectors': [], 'targets': []})
    client.put('/api/si/patch/reps', json={'name': 'Sam North', 'regions': [], 'services': [], 'sectors': [], 'targets': []})  # now on screen
    a = account(db, 'Example Owner Homes')
    db.commit()
    made = engage.create_deal(db, a.id, {'qualification': {'requirement': 'Annual servicing at 12 sites'}})
    db.commit()
    assert made.owner_rep == 'Sam North'
    moved = client.patch(f'/api/si/deals/{made.id}', json={'owner_rep': 'Jo West', 'value_annual': '48000'})
    assert moved.status_code == 200 and moved.json()['owner_rep'] == 'Jo West' and moved.json()['value_annual'] == 48000.0
    assert client.patch(f'/api/si/deals/{made.id}', json={'owner_rep': 'Nobody'}).status_code in (400, 422)
    assert next(d for d in client.get('/api/si/deals').json()['items'] if d['id'] == made.id)['owner_rep'] == 'Jo West'
    made.stage = 'won'
    db.commit()
    assert client.patch(f'/api/si/deals/{made.id}', json={'owner_rep': 'Sam North'}).status_code in (400, 422)  # a won deal keeps its owner
    assert patch.reps(db)['active'] == 'Sam North'
