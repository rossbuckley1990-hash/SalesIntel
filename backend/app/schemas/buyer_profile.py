from pydantic import Field

from app.schemas.common import MisiSchema


class BuyerProfileBase(MisiSchema):
    buyer_name: str
    sector: str
    region: str
    estate_size: str | None = None
    procurement_drivers: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    decision_criteria: list[str] = Field(default_factory=list)
    relationship_status: str = "unknown"
    next_best_action: str = ""


class BuyerProfileCreate(BuyerProfileBase):
    pass


class BuyerProfileRead(BuyerProfileBase):
    id: int

