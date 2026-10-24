"""Schemas for the Cross-entity 360 intelligence endpoints.

A 360 view joins buyers, opportunities, market signals and competitors into one
server-authored intelligence pack. Every aggregate is paired with an evidence
trail so leadership can trust-but-verify the synthesis.
"""

from pydantic import Field

from app.schemas.buyer_profile import BuyerProfileRead
from app.schemas.common import MisiSchema
from app.schemas.competitor_profile import CompetitorProfileRead
from app.schemas.opportunity import OpportunityRead


class EvidenceItem(MisiSchema):
    source_entity_type: str
    source_entity_id: int
    source_entity_label: str
    claim: str
    match_method: str | None = None
    confidence: float = 1.0


class MarginSummary(MisiSchema):
    average_margin_percentage: float = 0
    lowest_margin_percentage: float = 0
    highest_margin_percentage: float = 0
    below_threshold_count: int = 0
    threshold_percentage: float = 25.0


class RiskDistribution(MisiSchema):
    red: int = 0
    amber: int = 0
    green: int = 0


class IncumbentCompetitor(MisiSchema):
    competitor: CompetitorProfileRead
    threat_level: str
    pressure_label: str
    match_method: str


class RenewalWindow(MisiSchema):
    label: str
    month: str | None = None
    date_value: str | None = None
    value: float | None = None
    source_entity_type: str
    source_entity_id: int


class Buyer360(MisiSchema):
    buyer: BuyerProfileRead
    opportunity_count: int = 0
    active_tender_count: int = 0
    pipeline_exposure: float = 0
    weighted_exposure: float = 0
    active_tender_value: float = 0
    margin_summary: MarginSummary = Field(default_factory=MarginSummary)
    risk_distribution: RiskDistribution = Field(default_factory=RiskDistribution)
    incumbent_competitors: list[IncumbentCompetitor] = Field(default_factory=list)
    renewal_windows: list[RenewalWindow] = Field(default_factory=list)
    linked_opportunities: list[OpportunityRead] = Field(default_factory=list)
    commercial_synthesis: str = ""
    recommended_next_action: str = ""
    risk_level: str = "Green"
    confidence: float = 0
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ContestedBuyer(MisiSchema):
    buyer: BuyerProfileRead
    opportunity_count: int = 0
    contested_value: float = 0
    match_method: str


class Competitor360(MisiSchema):
    competitor: CompetitorProfileRead
    contested_opportunity_count: int = 0
    contested_value: float = 0
    affected_buyer_count: int = 0
    sectors_present: list[str] = Field(default_factory=list)
    contested_opportunities: list[OpportunityRead] = Field(default_factory=list)
    affected_buyers: list[ContestedBuyer] = Field(default_factory=list)
    commercial_synthesis: str = ""
    recommended_next_action: str = ""
    threat_level: str = "unknown"
    confidence: float = 0
    evidence: list[EvidenceItem] = Field(default_factory=list)
