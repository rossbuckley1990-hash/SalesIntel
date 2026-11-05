"""Private-sector prospects: start research, review results, add to the pipeline."""
from datetime import UTC, datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import MarketSignal, Opportunity
from app.models.prospect import Prospect, ProspectSearch
from app.services.market_signal_conversion import convert_market_signal_to_opportunity
from app.services.prospect_research import SIGNALS, list_prospects, search_dict, start_search, view

router = APIRouter(prefix='/api/prospects', tags=['prospects'])
FAMILY_LABELS = {'fire_alarm': 'Fire alarm', 'cctv': 'CCTV', 'access_control': 'Access control', 'intruder': 'Intruder alarm',
                 'emergency_lighting': 'Emergency lighting', 'sprinkler': 'Sprinklers', 'general': 'Fire and security'}


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=3, max_length=1000)
    mode: Literal['discover', 'company'] = 'discover'
    prospect_id: int | None = None


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['new', 'watching', 'dismissed']


@router.get('')
def prospects(status: Literal['new', 'watching', 'pipeline', 'dismissed'] | None = None, db: Session = Depends(get_db)):
    return {'items': list_prospects(db, status)}


@router.get('/signals')
def signal_types():
    return {'signals': [{'type': k, 'label': v[0], 'group': v[1]} for k, v in SIGNALS.items()]}


@router.post('/searches')
def create_search(payload: SearchRequest, db: Session = Depends(get_db)):
    if db.scalar(select(ProspectSearch).where(ProspectSearch.status == 'running', ProspectSearch.query == payload.query.strip())):
        raise HTTPException(status_code=409, detail='This research is already running.')
    if payload.prospect_id is not None and not db.get(Prospect, payload.prospect_id):
        raise HTTPException(status_code=404, detail='Prospect not found')
    return search_dict(start_search(db, payload.query, 'company' if payload.prospect_id else payload.mode, target_prospect_id=payload.prospect_id))


@router.get('/searches')
def searches(db: Session = Depends(get_db)):
    rows = db.scalars(select(ProspectSearch).order_by(ProspectSearch.id.desc()).limit(12)).all()
    return {'items': [search_dict(r) for r in rows]}


@router.get('/searches/{search_id}')
def search(search_id: int, db: Session = Depends(get_db)):
    row = db.get(ProspectSearch, search_id)
    if not row:
        raise HTTPException(status_code=404, detail='Search not found')
    return search_dict(row)


@router.get('/{prospect_id}')
def prospect(prospect_id: int, db: Session = Depends(get_db)):
    row = db.get(Prospect, prospect_id)
    if not row:
        raise HTTPException(status_code=404, detail='Prospect not found')
    return view(row)


@router.patch('/{prospect_id}')
def update(prospect_id: int, payload: StatusUpdate, db: Session = Depends(get_db)):
    row = db.get(Prospect, prospect_id)
    if not row:
        raise HTTPException(status_code=404, detail='Prospect not found')
    row.status, row.updated_at = payload.status, datetime.now(UTC)
    db.commit()
    return view(row)


@router.post('/{prospect_id}/promote')
def promote(prospect_id: int, db: Session = Depends(get_db)):
    """Add a prospect to the pipeline once; a person qualifies it from there."""
    row = db.get(Prospect, prospect_id)
    if not row:
        raise HTTPException(status_code=404, detail='Prospect not found')
    data = row.data
    title = (data.get('headline') or f'Fire and security opportunity at {row.name}')[:255]
    if row.opportunity_id and db.get(Opportunity, row.opportunity_id):
        return {'opportunity_id': row.opportunity_id, 'created': False}
    known = db.scalar(select(Opportunity).where(Opportunity.buyer_name == row.name[:255], Opportunity.name == title))
    if known:
        row.opportunity_id, row.status = known.id, 'pipeline'
        db.commit()
        return {'opportunity_id': known.id, 'created': False}
    timing = view(row)['timing']
    source = next((s['source_url'] for s in data.get('signals') or [] if s.get('source_url')), None)
    signal = MarketSignal(title=title, buyer_name=row.name[:255], sector=(data.get('sector') or 'Private sector')[:120],
                          region=(data.get('location') or 'United Kingdom')[:120], estimated_value=None, expected_tender_date=None,
                          source_type='Prospect research', source_url=source, source_attribution='SalesIntel prospect research from public sources',
                          confidence_score=0, suggested_action=(data.get('approach') or {}).get('angle') or 'Qualify the signals and approach the decision maker.',
                          likely_mitie_fit='Medium', potential_disciplines=[FAMILY_LABELS.get(s, s) for s in data.get('services') or []],
                          ai_rationale=f"{timing['label']}. " + ' '.join(timing['reasons'][:2]))
    db.add(signal)
    db.flush()
    converted = convert_market_signal_to_opportunity(signal, db=db)
    row.opportunity_id, row.status, row.updated_at = converted.opportunity.id, 'pipeline', datetime.now(UTC)
    db.commit()
    return {'opportunity_id': converted.opportunity.id, 'created': converted.created_opportunity}
