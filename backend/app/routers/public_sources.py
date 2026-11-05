"""User-triggered public-source refresh; no network request occurs at startup."""
from datetime import UTC, datetime, timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingestion.find_a_tender import fetch_batch
from app.routers.evidence_observations import import_evidence
from app.schemas.evidence_observation import EvidenceImportRequest

router = APIRouter(prefix='/api/public-sources', tags=['public sources'])


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    updated_from: datetime | None = None
    updated_to: datetime | None = None
    cursor: str | None = Field(default=None, max_length=300, pattern=r'^[A-Za-z0-9=]+$')
    max_pages: int = Field(default=2, ge=1, le=10)
    keywords: list[str] | None = Field(default=None, min_length=1, max_length=10)

    @field_validator('updated_from', 'updated_to')
    @classmethod
    def utc_dates(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError('Dates must include a timezone')
        return value.astimezone(UTC) if value else value

    @field_validator('keywords')
    @classmethod
    def clean_keywords(cls, values):
        if values is None:
            return values
        words = [v.strip() for v in values]
        if any(not word or len(word) > 100 for word in words):
            raise ValueError('Keywords must contain 1–100 characters')
        return words

    @model_validator(mode='after')
    def check_cursor_window(self):
        if self.cursor and (not self.updated_from or not self.updated_to):
            raise ValueError('A pagination cursor requires the original updated_from and updated_to')
        return self


@router.post('/find-a-tender/refresh')
def refresh_find_a_tender(request: RefreshRequest, db: Session = Depends(get_db)):
    now = datetime.now(UTC).replace(microsecond=0)
    end = (request.updated_to or now).replace(microsecond=0)
    start = (request.updated_from or end - timedelta(days=7)).replace(microsecond=0)
    if start >= end or end - start > timedelta(days=31) or end > now + timedelta(minutes=1):
        raise HTTPException(422, 'Choose a past update window of at most 31 days with start before end.')
    try:
        observations, scanned, pages, next_cursor = fetch_batch(
            updated_from=start, updated_to=end, cursor=request.cursor,
            max_pages=request.max_pages, keywords=request.keywords)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(502, 'Find a Tender could not be read safely; no observations were imported. Try again later.') from exc
    result = import_evidence(EvidenceImportRequest(observations=observations), db) if observations else None
    return {'imported': result.imported if result else 0, 'duplicates': result.duplicates if result else 0,
            'scanned': scanned, 'matched': len(observations), 'pages': pages,
            'updated_from': start.isoformat(), 'updated_to': end.isoformat(), 'next_cursor': next_cursor,
            'warnings': ['Find a Tender covers public-sector notices, not the whole market. Historical awards are context, not evidence of an active opportunity or supplier failure.',
                         'Only notices with an identified buyer and matching title or description are imported; buyer location may differ from the service site.',
                         'The update window and keywords must be kept unchanged when continuing a cursor.']}
