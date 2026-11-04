"""Bounded public premises context; no purchaser or risk is inferred."""
from fastapi import APIRouter, HTTPException, Query
from app.intelligence.public_estates import PublicEstateError, normalise_postcode, search_establishments

router = APIRouter(prefix="/api/public-estates", tags=["public estate sources"])


@router.get("/food-establishments")
def food_establishments(postcode: str = Query(min_length=5, max_length=12), limit: int = Query(default=10, ge=1, le=10)) -> dict:
    try:
        normalised = normalise_postcode(postcode)
    except ValueError as exc:
        raise HTTPException(422, "Enter a full UK postcode.") from exc
    try:
        return search_establishments(normalised, limit)
    except PublicEstateError as exc:
        raise HTTPException(502, "The public establishment register could not be read. Try again later.") from exc
