"""Public-source research outputs. Linked sources and claims remain unverified."""
from typing import Literal
from pydantic import Field
from app.schemas.common import MisiSchema


class UniversalResearchRequest(MisiSchema):
    brief: str = Field(min_length=8, max_length=1200)
    max_searches: int = Field(default=6, ge=1, le=12)
    include_inbox: bool = False
    include_rightclick: bool = False
    rightclick_identifier: str = Field(default="", max_length=20)
    rightclick_dataset: Literal["planning-application", "brownfield-land", "conservation-area"] = "planning-application"
    include_estate_lookup: bool = False
    estate_postcode: str = Field(default="", max_length=12)


class ResearchSearch(MisiSchema):
    query: str
    status: Literal["completed", "failed"]
    detail: str
    web_queries: list[str] = Field(default_factory=list)
    web_sources: list[str] = Field(default_factory=list)
    stage: Literal["initial", "follow_up", "planned_fallback"] = "initial"


class ResearchObservation(MisiSchema):
    id: str
    source_url: str
    source_title: str
    published_date: str
    fact: str
    origin: Literal["web_search", "evidence_inbox", "public_api", "rightclick_x"] = "web_search"
    organisation_name: str | None = None
    organisation_id: str | None = None
    site: str | None = None
    category: str | None = None
    source_reference: str | None = None
    observed_date: str | None = None
    retrieved_at: str | None = None


class ResearchOpportunity(MisiSchema):
    organisation: str
    location: str
    headline: str
    thesis: str
    supporting_observation_ids: list[str]
    counter_observation_ids: list[str]
    unknowns: list[str]
    contact_name: str
    contact_role: str
    contact_observation_ids: list[str]
    engagement: str
    verification_action: str
    potential_solution: str = ""


class UniversalResearchResult(MisiSchema):
    brief: str
    model: str
    include_inbox: bool = False
    source_discovery: dict | None = None
    estate_lookup: dict | None = None
    searches: list[ResearchSearch]
    observations: list[ResearchObservation]
    opportunities: list[ResearchOpportunity]
    limitations: list[str]
