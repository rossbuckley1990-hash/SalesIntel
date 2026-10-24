from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MarketSignal
from app.routers.query import Limit, contains_text
from app.schemas import MarketSignalConversionResponse, MarketSignalRead
from app.services.market_signal_conversion import (
    convert_market_signal_to_opportunity,
    enrich_market_signal,
)

router = APIRouter(prefix="/api/market-signals", tags=["market signals"])


@router.get("", response_model=list[MarketSignalRead])
def list_market_signals(
    db: Session = Depends(get_db),
    limit: Limit = 100,
    sector: str | None = None,
    region: str | None = None,
    search: str | None = None,
) -> list[MarketSignal]:
    statement = select(MarketSignal).order_by(MarketSignal.id)

    if sector:
        statement = statement.where(MarketSignal.sector == sector)
    if region:
        statement = statement.where(MarketSignal.region == region)

    search_clause = contains_text(
        MarketSignal.title,
        MarketSignal.buyer_name,
        MarketSignal.sector,
        MarketSignal.region,
        MarketSignal.source_type,
        MarketSignal.source_attribution,
        search=search,
    )
    if search_clause is not None:
        statement = statement.where(search_clause)

    signals = list(db.scalars(statement.limit(limit)))
    for signal in signals:
        enrich_market_signal(signal)
    db.commit()
    return signals


@router.post("/{signal_id}/convert", response_model=MarketSignalConversionResponse)
def convert_market_signal(
    signal_id: int,
    db: Session = Depends(get_db),
) -> MarketSignalConversionResponse:
    signal = db.get(MarketSignal, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Market signal not found")
    return convert_market_signal_to_opportunity(signal, db=db)
