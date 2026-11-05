"""Daily AI spending limits per workspace and per person, enforced atomically.

A job reserves its estimated maximum cost before it may call a provider. The reservation is a
conditional UPDATE (`... WHERE reserved + spent + :amount <= limit`) on both the workspace row and
the person's row, in one short transaction of its own, so concurrent requests cannot both pass a
limit that only one fits. When the job finishes, the actual measured cost is settled and the rest
of the reservation released.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.acquisition import SpendBudget
from app.services.si_core import uk_today

WORKSPACE = 0  # user_id of the workspace-wide row


class SpendLimitReached(Exception):
    pass


def limits() -> tuple[int, int]:
    s = get_settings()
    if s.ai_daily_limit_cents_per_workspace is not None:
        return s.ai_daily_limit_cents_per_workspace, s.ai_daily_limit_cents_per_user if s.ai_daily_limit_cents_per_user is not None else s.ai_daily_limit_cents_per_workspace
    if s.app_env in {'demo', 'test'}:
        return 1000, 600
    if s.auth_mode == 'local':
        return 1000, 1000  # $10 a day for a single-user install
    return 0, 0  # hosted: off until set


def _ensure_rows(db: Session, org: int, user: int, day: date) -> None:
    ws_limit, user_limit = limits()
    insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
    for uid, limit in ((WORKSPACE, ws_limit), (user, user_limit)):
        db.execute(insert(SpendBudget.__table__).values(organisation_id=org, user_id=uid, day=day, limit_cents=limit, reserved_cents=0, spent_cents=0)
                   .on_conflict_do_nothing(index_elements=['organisation_id', 'user_id', 'day']))
        db.execute(update(SpendBudget).where(SpendBudget.user_id == uid, SpendBudget.day == day).values(limit_cents=limit),
                   execution_options={'synchronize_session': False})  # a changed setting applies today


def reserve(db: Session, org: int, user: int | None, cents: int, day: date | None = None) -> None:
    """Hold `cents` against today's workspace and personal limits, or raise SpendLimitReached.

    Both conditional updates run in the caller's transaction; a refusal rolls back with it.
    """
    day = day or uk_today()
    uid = user or WORKSPACE
    _ensure_rows(db, org, uid, day)
    for target in sorted({WORKSPACE, uid}):  # a fixed order, so two requests cannot lock the rows in opposite orders
        done = db.execute(update(SpendBudget)
                          .where(SpendBudget.user_id == target, SpendBudget.day == day,
                                 SpendBudget.reserved_cents + SpendBudget.spent_cents + cents <= SpendBudget.limit_cents)
                          .values(reserved_cents=SpendBudget.reserved_cents + cents), execution_options={'synchronize_session': False})
        if done.rowcount != 1:
            raise SpendLimitReached('workspace' if target == WORKSPACE else 'person')


def settle(db: Session, user: int | None, reserved: int, actual: int, day: date) -> None:
    """Replace a reservation with what was actually spent. Spending is recorded even above the estimate."""
    for target in sorted({WORKSPACE, user or WORKSPACE}):
        db.execute(update(SpendBudget).where(SpendBudget.user_id == target, SpendBudget.day == day)
                   .values(reserved_cents=SpendBudget.reserved_cents - reserved, spent_cents=SpendBudget.spent_cents + actual),
                   execution_options={'synchronize_session': False})


def today(db: Session, user: int | None) -> dict:
    day = uk_today()
    rows = {r.user_id: r for r in db.scalars(select(SpendBudget).where(SpendBudget.day == day, SpendBudget.user_id.in_([WORKSPACE, user or WORKSPACE])))}
    ws_limit, user_limit = limits()

    def view(r, limit):
        return {'limit_cents': r.limit_cents if r else limit, 'reserved_cents': r.reserved_cents if r else 0, 'spent_cents': r.spent_cents if r else 0}
    return {'day': day.isoformat(), 'currency': 'USD', 'basis': 'Provider list prices, measured from reported usage',
            'workspace': view(rows.get(WORKSPACE), ws_limit), 'me': view(rows.get(user or WORKSPACE), user_limit)}
