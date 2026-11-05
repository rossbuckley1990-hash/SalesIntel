"""Blind review of the opportunity-quality evaluation.

Reviewers see only the source records and record their own judgement, in the app or in an offline review pack that an
administrator imports. The server keeps the seal:
- results stay closed until every item has two complete independent reviews and every disagreement on a primary
  question is adjudicated;
- then the set is locked, so no answer can change after the close;
- then an administrator supplies the private key, which is accepted only if it matches the commitment published before
  the review.
Nothing here can reveal which method found an item before that."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Context, current_context, tenant_db
from app.intelligence import opportunity_review as review
from app.intelligence import review_pack
from app.models.review import ReviewAdjudication, ReviewDecision, ReviewState
from app.routers.salesintel import permitted, run
from app.tenancy import can

router = APIRouter(prefix='/api/si/review', tags=['evaluation'], dependencies=[Depends(permitted)])
DIR = Path(__file__).parents[2] / 'reference_data' / 'evaluation'
SET_KEY = re.compile(r'[a-z0-9][a-z0-9-]{2,63}')


def _load(set_key: str) -> tuple[dict, dict]:
    """The served set and its public commitment. A set whose contents no longer match its commitment is refused."""
    if not SET_KEY.fullmatch(set_key):
        raise LookupError('Review set not found')
    data_file, commit_file = DIR / f'{set_key}.json', DIR / f'{set_key}.commitment.json'
    if not data_file.exists() or not commit_file.exists():
        raise LookupError('Review set not found')
    data, commitment = json.loads(data_file.read_text()), json.loads(commit_file.read_text())
    if review.digest(data) != commitment.get('dataset_sha256'):
        raise PermissionError('This review set does not match its published commitment, so it cannot be used.')
    return data, commitment


def _state(db: Session, set_key: str) -> ReviewState | None:
    return db.scalar(select(ReviewState).where(ReviewState.set_key == set_key))


def _open(db: Session, set_key: str) -> None:
    state = _state(db, set_key)
    if state is not None and state.status != 'open':
        raise PermissionError('This review is closed: answers can no longer change.')


def _decisions(db: Session, set_key: str) -> list[dict]:
    return [{'item_id': d.item_id, 'reviewer': d.reviewer, 'reviewer_name': d.reviewer_name, 'answers': d.answers, 'minutes': d.minutes}
            for d in db.scalars(select(ReviewDecision).where(ReviewDecision.set_key == set_key).order_by(ReviewDecision.id))]


def _rulings(db: Session, set_key: str) -> list[dict]:
    return [{'item_id': a.item_id, 'question': a.question, 'answer': a.answer, 'method': a.method, 'adjudicator': a.adjudicator, 'rationale': a.rationale}
            for a in db.scalars(select(ReviewAdjudication).where(ReviewAdjudication.set_key == set_key).order_by(ReviewAdjudication.id))]


def _upsert(db: Session, set_key: str, item_id: str, reviewer: int, name: str, answers: dict, minutes: int | None, note: str,
            channel: str = 'app', submission: str | None = None) -> None:
    row = db.scalar(select(ReviewDecision).where(ReviewDecision.set_key == set_key, ReviewDecision.item_id == item_id, ReviewDecision.reviewer == reviewer))
    moment = datetime.now(UTC)
    if row is None:
        db.add(ReviewDecision(set_key=set_key, item_id=item_id, reviewer=reviewer, reviewer_name=name[:120], channel=channel, submission_sha256=submission,
                              answers=answers, minutes=minutes, note=note, created_at=moment, updated_at=moment))
    else:
        row.answers, row.minutes, row.note, row.reviewer_name, row.updated_at = answers, minutes, note, name[:120], moment
        row.channel, row.submission_sha256 = channel, submission


@router.get('')
def sets():
    return {'items': sorted(p.stem for p in DIR.glob('*.json') if not p.name.endswith('.commitment.json') and p.with_name(p.stem + '.commitment.json').exists())}


@router.get('/{set_key}')
def review_set(set_key: str, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    def work():
        data, commitment = _load(set_key)
        mine = {d.item_id: {'answers': d.answers, 'minutes': d.minutes, 'note': d.note}
                for d in db.scalars(select(ReviewDecision).where(ReviewDecision.set_key == set_key, ReviewDecision.reviewer == ctx.user_id))}
        state = _state(db, set_key)
        return {**{k: v for k, v in data.items() if k != 'items'}, 'items': data['items'], 'mine': mine, 'state': state.status if state else 'open',
                'fingerprint': commitment['dataset_sha256'][:12], 'progress': {'done': sum(1 for v in mine.values() if review.complete_answers(v['answers'])),
                                                                               'total': len(data['items'])}}
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
        _open(db, set_key)
        _upsert(db, set_key, item_id, ctx.user_id or 0, ctx.name or '', review.validate(payload.answers), payload.minutes, payload.note)
        return {'saved': True, 'item_id': item_id}
    return run(db, work)


def _admin(ctx: Context) -> None:
    ctx.require('members.manage')  # these views and actions are for whoever runs the evaluation


@router.get('/{set_key}/status')
def progress(set_key: str, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Progress, agreement and disagreements, without anything that unblinds the methods."""
    _admin(ctx)

    def work():
        data, commitment = _load(set_key)
        state = _state(db, set_key)
        s = review.status(data, _decisions(db, set_key), _rulings(db, set_key))
        status = state.status if state else 'open'
        return {**s, 'state': status, 'ready_to_lock': status == 'open' and s['complete'], 'fingerprint': commitment['dataset_sha256'][:12],
                'rulings': _rulings(db, set_key)}
    return run(db, work)


class Ruling(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_id: str = Field(max_length=16)
    question: Literal['relevance', 'reason', 'pursue']
    answer: str = Field(max_length=24)
    method: Literal['consensus', 'third_reviewer']
    adjudicator: str = Field(max_length=120)
    rationale: str = Field(max_length=2000)


@router.post('/{set_key}/adjudications')
def adjudicate(set_key: str, payload: Ruling, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    _admin(ctx)

    def work():
        data, _ = _load(set_key)
        _open(db, set_key)
        ruling = payload.model_dump()
        review.check_adjudication(review.status(data, _decisions(db, set_key), _rulings(db, set_key)), ruling)
        row = db.scalar(select(ReviewAdjudication).where(ReviewAdjudication.set_key == set_key, ReviewAdjudication.item_id == payload.item_id,
                                                         ReviewAdjudication.question == payload.question))
        if row is None:
            db.add(ReviewAdjudication(set_key=set_key, recorded_by=ctx.user_id, created_at=datetime.now(UTC), **ruling))
        else:
            row.answer, row.method, row.adjudicator, row.rationale, row.recorded_by = payload.answer, payload.method, payload.adjudicator, payload.rationale, ctx.user_id
        return {'saved': True}
    return run(db, work)


class PackDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_id: str = Field(max_length=16)
    answers: dict[str, str]
    seconds: int = Field(0, ge=0, le=36000)
    note: str = Field('', max_length=2000)


class PackReviewer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str = Field('', max_length=40)
    name: str = Field(min_length=2, max_length=120)


class Submission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format: Literal['salesintel-review/1']
    kind: Literal['review']
    set_key: str = Field(max_length=64)
    dataset_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: PackReviewer
    attested: bool
    started_at: str = Field('', max_length=40)
    finished_at: str = Field('', max_length=40)
    decisions: list[PackDecision] = Field(max_length=500)


@router.get('/{set_key}/pack')
def pack(set_key: str, reviewer: str = Query(..., pattern=r'^[A-Za-z0-9 ._-]{1,40}$'), db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """An offline review pack for one reviewer: the blinded items only, no network access, no key."""
    _admin(ctx)
    data, commitment = run(db, lambda: _load(set_key))
    name = re.sub(r'[^a-z0-9]+', '-', reviewer.lower()).strip('-') or 'reviewer'
    return Response(review_pack.render(data, commitment, reviewer=reviewer), media_type='text/html; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="opportunity-review-{set_key}-{name}.html"', 'Cache-Control': 'no-store'})


def pack_reviewer_id(name: str) -> int:
    """A stable id for a reviewer who used an offline pack: negative, so it can never be a user's id."""
    return -(int(hashlib.sha256(' '.join(name.lower().split()).encode()).hexdigest()[:7], 16) + 1)


@router.post('/{set_key}/import')
def import_pack(set_key: str, payload: Submission, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Import a reviewer's answers from an offline review pack. Checked in full before anything is stored."""
    _admin(ctx)

    def work():
        data, commitment = _load(set_key)
        _open(db, set_key)
        if payload.set_key != set_key or payload.dataset_sha256 != commitment['dataset_sha256']:
            raise ValueError('These answers are for a different review set, or a different version of it.')
        if not payload.attested:
            raise ValueError('The reviewer has not confirmed they worked alone and did not look for how items were found.')
        ids = {i['id'] for i in data['items']}
        clean = []
        for d in payload.decisions:
            if d.item_id not in ids:
                raise ValueError(f'{d.item_id} is not an item in this review set.')
            clean.append((d, review.validate(d.answers)))
        name = ' '.join(payload.reviewer.name.split())
        reviewer, fingerprint = pack_reviewer_id(name), review.digest(payload.model_dump())
        for d, answers in clean:
            _upsert(db, set_key, d.item_id, reviewer, name, answers, round(d.seconds / 60), d.note, 'pack', fingerprint)
        return {'imported': len(clean), 'complete': sum(1 for _, a in clean if review.complete_answers(a)), 'reviewer': name, 'submission_sha256': fingerprint}
    return run(db, work)


@router.post('/{set_key}/lock')
def lock(set_key: str, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    _admin(ctx)

    def work():
        data, _ = _load(set_key)
        _open(db, set_key)
        s = review.status(data, _decisions(db, set_key), _rulings(db, set_key))
        if not s['complete']:
            raise PermissionError(f"Not complete: {s['items_with_two_reviews']} of {s['items']} items have two independent reviews, "
                                  f"and {len(s['pending'])} disagreement(s) need adjudicating.")
        state = _state(db, set_key) or ReviewState(set_key=set_key)
        state.status, state.locked_at, state.locked_by = 'locked', datetime.now(UTC), ctx.user_id
        db.add(state)
        return {'state': 'locked'}
    return run(db, work)


@router.post('/{set_key}/reveal')
def reveal(set_key: str, key: dict[str, Any] = Body(...), db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Accept the private key, only after the close, and only if it matches the commitment published before the review."""
    _admin(ctx)

    def work():
        data, commitment = _load(set_key)
        state = _state(db, set_key)
        if state is None or state.status == 'open':
            raise PermissionError('Lock the completed review before revealing its key.')
        try:
            review.verify_key(commitment, key)
        except ValueError as exc:
            raise PermissionError(str(exc)) from exc
        if set(key.get('items') or {}) != {i['id'] for i in data['items']}:
            raise PermissionError('This key does not cover exactly the items that were reviewed.')
        state.status, state.key, state.key_sha256 = 'revealed', key, commitment['key_sha256']
        state.revealed_at, state.revealed_by = datetime.now(UTC), ctx.user_id
        return {'state': 'revealed'}
    return run(db, work)


@router.get('/{set_key}/results')
def results(set_key: str, db: Session = Depends(tenant_db), ctx: Context = Depends(current_context)):
    """Unblinds the methods, so only for an administrator, and only once the key has been revealed after the close."""
    if not can(ctx.role, 'members.manage'):
        raise HTTPException(status_code=403, detail='Results unblind the review, so only an administrator can see them.')

    def work():
        data, _ = _load(set_key)
        state = _state(db, set_key)
        if state is None or state.status != 'revealed' or not state.key:
            raise PermissionError('Results stay sealed until the review is complete, locked and its key has been revealed and verified.')
        return review.results(data, state.key, _decisions(db, set_key), _rulings(db, set_key))
    return run(db, work)
