"""Idempotent writes: a retried request with the same Idempotency-Key gets the first response, not a second action.

The key is recorded in the same transaction as the write it protects. A concurrent duplicate
waits on the unique key and then replays the stored response; a refused or failed write rolls
the key back with it, so it can be retried. The same key with a different request is refused.
"""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any, Callable

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.acquisition import IdempotencyRecord


def idempotent(db: Session, key: str | None, endpoint: str, request: Any, fn: Callable[[], Any]) -> Any:
    if not key:
        return fn()
    key = key.strip()
    if not 8 <= len(key) <= 80:
        raise HTTPException(status_code=422, detail='Idempotency-Key must be 8 to 80 characters.')
    digest = hashlib.sha256(json.dumps([endpoint, jsonable_encoder(request)], sort_keys=True, default=str).encode()).hexdigest()

    def replay(row: IdempotencyRecord) -> Any:
        if row.request_hash != digest or row.endpoint != endpoint:
            raise HTTPException(status_code=422, detail='This Idempotency-Key was already used for a different request.')
        if row.status != 'done':
            raise HTTPException(status_code=409, detail='The same request is still being processed.')
        return row.response

    found = db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.key == key))
    if found is not None:
        return replay(found)
    record = IdempotencyRecord(key=key, endpoint=endpoint, request_hash=digest, status='pending', created_at=datetime.now(UTC))
    db.add(record)
    try:
        db.flush()  # a concurrent duplicate blocks here until the first commits, then fails on the unique key
    except IntegrityError:
        db.rollback()
        return replay(db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.key == key)))
    result = jsonable_encoder(fn())
    record.status, record.status_code, record.response = 'done', 200, result
    db.flush()
    return result
