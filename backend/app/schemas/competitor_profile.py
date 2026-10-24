from pydantic import Field

from app.schemas.common import MisiSchema


class CompetitorProfileBase(MisiSchema):
    name: str
    sectors: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    pricing_behaviour: str = ""
    threat_level: str = "unknown"
    counter_strategy: str = ""


class CompetitorProfileCreate(CompetitorProfileBase):
    pass


class CompetitorProfileRead(CompetitorProfileBase):
    id: int

