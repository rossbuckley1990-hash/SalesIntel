"""The Living Opportunity API: one source-backed brief per lead or account, and when someone last reviewed it."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Context, current_context, tenant_db
from app.models.brief import BriefReview
from app.routers.salesintel import permitted, run
from app.services import brief

router = APIRouter(prefix='/api/si/brief', tags=['brief'], dependencies=[Depends(permitted)])


def _last(db: Session, key: str, user_id: int | None) -> BriefReview | None:
    return db.scalar(select(BriefReview).where(BriefReview.key == key, BriefReview.user_id.is_(None) if user_id is None else BriefReview.user_id == user_id))


@router.get('/digest')
def digest(db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """For Today: accounts whose evidence or story changed since you last reviewed them, and the ones you are watching,
    each with its one next move. Built from the same briefs every other screen shows."""
    from app.models.crm import Account

    def work():
        reviews = {r.key: r.reviewed_at for r in db.scalars(select(BriefReview).where(
            BriefReview.user_id.is_(None) if ctx.user_id is None else BriefReview.user_id == ctx.user_id))}
        changed, watching = [], []
        for account in db.scalars(select(Account).order_by(Account.updated_at.desc()).limit(40)):
            key = f'acct:{account.id}'
            seen = reviews.get(key)
            if seen is None and not account.watched:
                continue
            try:
                b = brief.build(db, key, last_review=seen)
            except Exception:  # one unreadable record never hides the rest of the briefing
                continue
            row = {'account_id': account.id, 'name': account.name, 'headline': b['reveal']['headline'], 'next': b['next']['label'],
                   'new_events': b['since_last_review']['new_events'], 'since': b['since_last_review']['since'],
                   'latest': next((e['title'] for e in b['evidence'] if e['new']), '')}
            if seen is not None and row['new_events']:
                changed.append(row)
            if account.watched:
                watching.append(row)
        return {'changed': changed[:8], 'watching': watching[:8]}
    return run(db, work)


@router.get('/{key}')
def get_brief(key: str, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    def work():
        seen = _last(db, key, ctx.user_id)
        return brief.build(db, key, last_review=seen.reviewed_at if seen else None)
    return run(db, work)


@router.post('/{key}/reviewed')
def reviewed(key: str, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Mark the brief as reviewed now, so the next visit shows only what is new."""
    def work():
        brief.build(db, key)  # refuse a key that does not exist in this workspace
        row = _last(db, key, ctx.user_id)
        moment = datetime.now(UTC)
        if row is None:
            db.add(BriefReview(key=key[:40], user_id=ctx.user_id, reviewed_at=moment))
        else:
            row.reviewed_at = moment
        return {'key': key, 'reviewed_at': moment.isoformat()}
    return run(db, work)
