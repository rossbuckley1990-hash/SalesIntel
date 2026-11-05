"""Inspect an operator-configured RightClick X runtime and approved sources."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from app.config import get_settings
from app.intelligence.rightclick_x import DISCOVERY_TOPICS, RightClickClient, RightClickError, planning_identifier

router = APIRouter(prefix="/api/rightclick", tags=["public source discovery"])


@router.get("/status")
def status() -> dict:
    settings = get_settings()
    if not settings.rightclick_x_url:
        return {"available": False, "configured": False, "version": None, "capabilities": None,
                "message": "Configure a local discovery endpoint to enable source discovery."}
    try:
        return RightClickClient(settings).status()
    except RightClickError:
        return {"available": False, "configured": True, "version": None, "capabilities": None,
                "message": "The configured local discovery runtime is unavailable or unsupported."}


@router.get("/capabilities")
def capabilities(query: str = Query(default="planning", max_length=200)) -> dict:
    try:
        return RightClickClient().search(query)
    except RightClickError as exc:
        raise HTTPException(503, detail="Public-source discovery is unavailable.") from exc


@router.get("/candidates")
def candidates(topic: str = Query(default="planning", min_length=1, max_length=40)) -> dict:
    if topic not in DISCOVERY_TOPICS:
        raise HTTPException(422, detail="Select a supported public discovery topic.")
    try:
        return RightClickClient().candidates(topic)
    except RightClickError as exc:
        raise HTTPException(503, detail="Public directory discovery is unavailable on the dedicated runtime.") from exc


@router.get("/capabilities/explain")
def explain(id: str = Query(min_length=1, max_length=300)) -> dict:
    try:
        return RightClickClient().explain(id)
    except RightClickError as exc:
        raise HTTPException(503, detail="The requested approved capability cannot be inspected.") from exc


class PlanningQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    identifier: str = Field(min_length=1, max_length=20)
    dataset: Literal["planning-application", "brownfield-land", "conservation-area"] = "planning-application"
    limit: int = Field(default=5, ge=1, le=10, strict=True)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return planning_identifier(value)


@router.post("/planning-query")
def planning_query(request: PlanningQuery) -> dict:
    try:
        return RightClickClient().planning_query(request.identifier, request.dataset, request.limit)
    except RightClickError as exc:
        raise HTTPException(503, detail="The approved planning source is unavailable or could not be verified.") from exc
