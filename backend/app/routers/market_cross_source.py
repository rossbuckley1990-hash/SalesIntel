"""Cross-source context for one exact legal supplier."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.market_cross_source import company_award_context

router = APIRouter(prefix='/api/market-network/companies', tags=['market network'])

@router.get('/{entity_id}/award-context')
def award_context(entity_id: int, limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    try:
        items = company_award_context(db, entity_id, limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail='Company not found') from exc
    return {'items': items, 'limitations': [
        'The procurement record and control filing report different facts; this is not independent corroboration of either claim.',
        'Only the exact supplier named in an award is linked. The controller is not treated as an awarded supplier.',
        'A filing may be cached and Companies House does not verify submitted information.',
        'Neither an award nor a control filing proves present contract delivery, ownership or intent to bid.',
        'Results are a bounded projection of captured records, not a complete contract portfolio.'
    ]}
