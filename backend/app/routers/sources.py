from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.routers.query import Limit
from app.schemas import MarketDataRefreshResponse, SourceRunRead
from app.services.market_data_refresh import list_source_runs, refresh_market_data

router = APIRouter(prefix="/api", tags=["sources"])


@router.post("/refresh-market-data", response_model=MarketDataRefreshResponse)
def refresh_market_data_endpoint(db: Session = Depends(get_db)) -> MarketDataRefreshResponse:
    return refresh_market_data(db)


@router.get("/source-runs", response_model=list[SourceRunRead])
def list_source_runs_endpoint(
    db: Session = Depends(get_db),
    limit: Limit = 100,
) -> list[SourceRunRead]:
    return list_source_runs(db, limit=limit)
