"""Blind review of the opportunity-quality evaluation set: reviewers see neutral evidence only and record their own
judgement; results (which unblind the arms) are for administrators."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Context, current_context, tenant_db
from app.intelligence import opportunity_review as review
from app.models.review import ReviewDecision
from app.routers.salesintel import permitted, run
from app.tenancy import can

router = APIRouter(prefix='/api/si/review', tags=['evaluation'], dependencies=[Depends(permitted)])
DIR = Path(__file__).parents[2] / 'reference_data' / 'evaluation'


@lru_cache(maxsize=8)
def _load(set_key: str) -> tuple[dict, dict]:
    if not set_key.replace('-', '').isalnum():
        raise LookupError('Review set not found')
    review_file, key_file = DIR / f'{set_key}.json', DIR / f'{set_key}.key.json'
    if not review_file.exists() or not key_file.exists():
        raise LookupError('Review set not found')
    return json.loads(review_file.read_text()), json.loads(key_file.read_text())


@router.get('')
def sets():
    return {'items': sorted(p.stem for p in DIR.glob('*.json') if not p.stem.endswith('.key'))}


@router.get('/{set_key}')
def review_set(set_key: str, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    def work():
        data, _ = _load(set_key)
        mine = {d.item_id: {'answers': d.answers, 'minutes': d.minutes, 'note': d.note}
                for d in db.scalars(select(ReviewDecision).where(ReviewDecision.set_key == set_key, ReviewDecision.reviewer == ctx.user_id))}
        return {**{k: v for k, v in data.items() if k != 'items'}, 'items': data['items'], 'mine': mine,
                'progress': {'done': len(mine), 'total': len(data['items'])}}  # the sealed key is never part of this response
    return run(db, work)


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answers: dict[str, str]
    minutes: int | None = Field(None, ge=0, le=240)
    note: str = Field('', max_length=2000)


@router.put('/{set_key}/{item_id}')
def decide(set_key: str, item_id: str, payload: Decision, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    def work():
        data, _ = _load(set_key)
        if item_id not in {i['id'] for i in data['items']}:
            raise LookupError('Item not found')
        answers = review.validate(payload.answers)
        row = db.scalar(select(ReviewDecision).where(ReviewDecision.set_key == set_key, ReviewDecision.item_id == item_id, ReviewDecision.reviewer == ctx.user_id))
        moment = datetime.now(UTC)
        if row is None:
            row = ReviewDecision(set_key=set_key, item_id=item_id, reviewer=ctx.user_id or 0, answers=answers, minutes=payload.minutes, note=payload.note,
                                 created_at=moment, updated_at=moment)
            db.add(row)
        else:
            row.answers, row.minutes, row.note, row.updated_at = answers, payload.minutes, payload.note, moment
        return {'saved': True, 'item_id': item_id}
    return run(db, work)


@router.get('/{set_key}/results')
def results(set_key: str, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Unblinds the arms, so only administrators see it, and reviewers should finish first."""
    if not can(ctx.role, 'members.manage'):
        raise HTTPException(status_code=403, detail='Results unblind the review, so only an administrator can see them.')

    def work():
        data, key = _load(set_key)
        decisions = [{'item_id': d.item_id, 'reviewer': d.reviewer, 'answers': d.answers, 'minutes': d.minutes}
                     for d in db.scalars(select(ReviewDecision).where(ReviewDecision.set_key == set_key).order_by(ReviewDecision.id))]
        return review.results(data, key, decisions)
    return run(db, work)
