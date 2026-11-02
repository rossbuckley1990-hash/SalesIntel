"""Review generated market signals without asserting a confirmed opportunity."""
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import MarketSignal, Opportunity
from app.models.market_contract import MarketContract, MarketContractLink
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityRevision
from app.services.market_opportunities import refresh_market_opportunities
from app.services.market_signal_conversion import convert_market_signal_to_opportunity
from app.services.renewal_radar import export_csv, radar_summary, source_health

router = APIRouter(prefix='/api/market-network/opportunities', tags=['market suggestions'])

LIMITATIONS = ['Suggestions are deterministic leads for review, not confirmed buying intent or probability.',
               'Only captured records are considered. Links and claims require independent review.',
               'No automatic current contract, supplier underperformance, or confirmed bid is inferred.']
FIT_TO_MITIE = {'core': 'High', 'framework': 'Medium', 'bundled': 'Medium'}


class Review(BaseModel):
    model_config = ConfigDict(extra='forbid')
    review_state: Literal['unreviewed', 'investigate', 'defer', 'dismiss']


def _matches(result: dict, category, nation, tier, text) -> bool:
    haystack = ' '.join(str(result.get(k) or '') for k in ('customer', 'title', 'supplier')).lower()
    return ((not category or result.get('category') == category) and (not nation or result.get('nation') == nation)
            and (tier is None or result.get('priority', {}).get('tier') == tier) and (not text or text.lower() in haystack))


@router.get('')
def list_opportunities(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                       state: Literal['suggested', 'withdrawn', 'all'] = 'suggested', category: str | None = Query(None, max_length=32),
                       nation: str | None = Query(None, max_length=32), tier: int | None = Query(None, ge=1, le=3), q: str = Query('', max_length=100),
                       db: Session = Depends(get_db)):
    query = select(MarketOpportunity, MarketOpportunityRevision).join(
        MarketOpportunityRevision, MarketOpportunity.current_revision_id == MarketOpportunityRevision.id)
    if state != 'all':
        query = query.where(MarketOpportunity.state == state)
    rows = [(item, version) for item, version in db.execute(query).all() if _matches(version.result, category, nation, tier, q.strip())]
    rows.sort(key=lambda x: (x[1].result.get('priority', {}).get('sort') or [9], -x[0].id))
    return {'items': [{'id': item.id, 'state': item.state, 'review_state': item.review_state,
                       'first_seen': item.first_seen, 'last_evaluated': item.last_evaluated,
                       'withdrawal_reason': item.withdrawal_reason, 'revision_id': version.id,
                       'suggestion': version.result} for item, version in rows[offset:offset + limit]],
            'total': len(rows), 'limitations': LIMITATIONS}


@router.get('/summary')
def summary(db: Session = Depends(get_db)):
    return radar_summary(db)


@router.get('/health')
def health(db: Session = Depends(get_db)):
    return {'sources': source_health(db)}


@router.get('/export.csv', response_class=PlainTextResponse)
def export(db: Session = Depends(get_db)):
    return PlainTextResponse(export_csv(db), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="uk-renewal-radar.csv"'})


@router.post('/refresh')
def refresh(db: Session = Depends(get_db)):
    try:
        result = refresh_market_opportunities(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.patch('/{opportunity_id}/review')
def review(opportunity_id: int, payload: Review, db: Session = Depends(get_db)):
    item = db.get(MarketOpportunity, opportunity_id)
    if not item:
        raise HTTPException(status_code=404, detail='Market suggestion not found')
    item.review_state = payload.review_state
    db.commit()
    return {'id': item.id, 'review_state': item.review_state,
            'note': 'Review is a user preference, not a verified market outcome.'}


@router.post('/{opportunity_id}/promote')
def promote(opportunity_id: int, db: Session = Depends(get_db)):
    """Add a reviewed lead to pursuits through MiSi's own signal conversion, once only."""
    item = db.get(MarketOpportunity, opportunity_id)
    version = db.get(MarketOpportunityRevision, item.current_revision_id) if item and item.current_revision_id else None
    if not version or item.state != 'suggested':
        raise HTTPException(status_code=404, detail='Market suggestion not found')
    result = version.result
    title, buyer = result['title'][:255], result['customer'][:255]
    item.review_state = 'investigate'
    known = db.scalar(select(Opportunity).where(Opportunity.name == title, Opportunity.buyer_name == buyer))
    if known:
        db.commit()
        return {'opportunity_id': known.id, 'created': False}
    value = result['value'].get('published_total') or result['value'].get('framework_ceiling')
    evidence = result['evidence'][0] if result['evidence'] else {}
    expected = result.get('timing') if result.get('category') in {'official_early_signal', 'live_procurement'} else None
    # Confidence stays at zero: a person qualifies a pursuit, the radar does not.
    signal = MarketSignal(title=title, buyer_name=buyer, sector='Fire and security', region=result.get('nation') or 'United Kingdom', estimated_value=value,
                          expected_tender_date=date.fromisoformat(expected) if expected else None, source_type='Renewal radar', source_url=evidence.get('source_url'),
                          source_attribution=f"{evidence.get('source', 'Public notice')} record {evidence.get('record_key', '')}", confidence_score=0, suggested_action=result['next_action'],
                          likely_mitie_fit=FIT_TO_MITIE.get(result.get('fit'), 'Low'), potential_disciplines=[], ai_rationale='; '.join(result['priority']['reasons']))
    db.add(signal)
    db.flush()
    converted = convert_market_signal_to_opportunity(signal, db=db)
    return {'opportunity_id': converted.opportunity.id, 'created': converted.created_opportunity}


@router.get('/{opportunity_id}/history')
def history(opportunity_id: int, db: Session = Depends(get_db)):
    if not db.get(MarketOpportunity, opportunity_id):
        raise HTTPException(status_code=404, detail='Market suggestion not found')
    versions = db.scalars(select(MarketOpportunityRevision).where(MarketOpportunityRevision.opportunity_id == opportunity_id)
                          .order_by(MarketOpportunityRevision.id.desc()).limit(100)).all()
    return {'items': [{'id': v.id, 'created_at': v.created_at, 'suggestion': v.result} for v in versions]}


@router.get('/contracts/{contract_id}')
def contract(contract_id: int, db: Session = Depends(get_db)):
    item = db.get(MarketContract, contract_id)
    if not item:
        raise HTTPException(status_code=404, detail='Contract not found')
    links = db.scalars(select(MarketContractLink).where(MarketContractLink.contract_id == contract_id)).all()
    return {'id': item.id, 'canonical_key': item.canonical_key, 'buyer': item.buyer, 'supplier': item.supplier, 'title': item.title, 'fit': item.fit, 'nation': item.nation,
            'lifecycle_status': item.lifecycle_status, 'category': item.category, 'end_date': item.end_date, 'end_estimated': item.end_estimated, 'last_verified': item.last_verified, 'facts': item.facts,
            'links': [{'source_key': x.source_key, 'ocid': x.ocid, 'lot': x.lot, 'method': x.method, 'confidence': x.confidence} for x in links]}
