from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BuyerProfile
from app.routers.query import Limit, contains_text
from app.schemas import BuyerProfileRead

router = APIRouter(prefix="/api/buyers", tags=["buyers"])


@router.get("", response_model=list[BuyerProfileRead])
def list_buyers(
    db: Session = Depends(get_db),
    limit: Limit = 100,
    sector: str | None = None,
    region: str | None = None,
    search: str | None = None,
) -> list[BuyerProfile]:
    statement = select(BuyerProfile).order_by(BuyerProfile.id)

    if sector:
        statement = statement.where(BuyerProfile.sector == sector)
    if region:
        statement = statement.where(BuyerProfile.region == region)

    search_clause = contains_text(
        BuyerProfile.buyer_name,
        BuyerProfile.sector,
        BuyerProfile.region,
        BuyerProfile.procurement_drivers,
        BuyerProfile.pain_points,
        search=search,
    )
    if search_clause is not None:
        statement = statement.where(search_clause)

    return list(db.scalars(statement.limit(limit)))


@router.get("/{buyer_id}", response_model=BuyerProfileRead)
def get_buyer(buyer_id: int, db: Session = Depends(get_db)) -> BuyerProfile:
    buyer = db.get(BuyerProfile, buyer_id)
    if buyer is None:
        raise HTTPException(status_code=404, detail="Buyer profile not found")
    return buyer

