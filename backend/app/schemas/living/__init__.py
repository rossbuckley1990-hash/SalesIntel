from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[
    Decimal, Field(ge=0, le=Decimal("1000000000000"), max_digits=16, decimal_places=2)
]
Ratio = Annotated[Decimal, Field(ge=0, le=1, max_digits=7, decimal_places=6)]
Name = Annotated[str, Field(min_length=2, max_length=120)]


class Request(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class DiscoverRequest(Request):
    query: str = Field(min_length=4, max_length=600)
    create_draft: bool = False
    owner: Name = "Unassigned"
    buyer: str = Field(default="Unconfirmed buyer", min_length=2, max_length=255)
    sector: str = Field(default="Unknown", min_length=2, max_length=120)
    region: str = Field(default="Unknown", min_length=2, max_length=120)


class DecisionRequest(Request):
    choice: Literal["pursue", "investigate", "hold", "no_bid"]
    rationale: str = Field(min_length=10, max_length=3000)
    reviewer: Name
    owner: Name
    due_date: date
    action: str = Field(min_length=5, max_length=2000)


class ActionRequest(Request):
    depends_on: list[Annotated[int, Field(gt=0)]] = Field(
        default_factory=list, max_length=30
    )
    opportunity_id: int = Field(gt=0)
    owner: Name
    due_date: date
    action: str = Field(min_length=5, max_length=2000)
    reason: str = Field(min_length=5, max_length=2000)
    priority: Literal["high", "medium", "low"] = "medium"


class ActionUpdate(Request):
    depends_on: list[Annotated[int, Field(gt=0)]] | None = Field(
        default=None, max_length=30
    )
    owner: Name
    due_date: date
    status: Literal["open", "in_progress", "blocked", "completed"]
    action: str = Field(min_length=5, max_length=2000)
    completion_evidence: str = Field(default="", max_length=3000)
    expected_status: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def require_evidence(self):
        if self.status == "completed" and len(self.completion_evidence) < 10:
            raise ValueError(
                "Completion requires an evidence reference and explanation."
            )
        return self


class ReviewRequest(Request):
    disposition: Literal["acknowledged", "challenged"]
    reviewer: Name
    note: str = Field(min_length=10, max_length=3000)


class ScenarioInput(Request):
    annual_revenue: Money
    baseline_share: Ratio = Decimal("0.40")
    proposed_share: Ratio = Decimal("0.70")
    inhouse_cost_ratio: Ratio = Decimal("0.62")
    subcontract_cost_ratio: Ratio = Decimal("0.84")
    probability: Ratio
    bid_cost: Money = Decimal("0")
    mobilisation_cost: Money = Decimal("0")
    payment_delay_days: int = Field(default=30, ge=0, le=365)
    start_month: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    financial_year_start: int = Field(ge=2020, le=2099)
    assumption_note: str = Field(min_length=10, max_length=4000)
    source_references: list[str] = Field(default_factory=list, max_length=30)


class SaveScenario(Request):
    opportunity_id: int = Field(gt=0)
    name: str = Field(min_length=3, max_length=160)
    owner: Name
    inputs: ScenarioInput


AssetKind = Literal[
    "dossier",
    "bid_decision",
    "pursuit_plan",
    "battlecard",
    "self_delivery",
    "forecast",
    "leadership",
    "tender",
]


class AssetRequest(Request):
    kind: AssetKind = "dossier"
    opportunity_id: int | None = Field(default=None, gt=0)
    scenario_id: int | None = Field(default=None, gt=0)
    notes: str = Field(default="", max_length=6000)


class AssetReview(Request):
    status: Literal["draft", "reviewed"]
    reviewer: Name


class SnapshotRequest(Request):
    label: str = Field(min_length=3, max_length=160)
    reviewer: Name


class OutcomeUpdate(Request):
    stage: Literal["identified", "investigating", "approved", "won", "realised"]
    owner: Name
    due_date: date | None = None
    expected_impact: Money | None = None
    actual_value: Money | None = None
    assumptions: str = Field(min_length=10, max_length=4000)
    completion_evidence: str = Field(default="", max_length=4000)
    verified_by: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def validate_realisation(self):
        if self.stage in {"won", "realised"} and (
            len(self.completion_evidence) < 10 or len(self.verified_by) < 2
        ):
            raise ValueError(
                "Won/realised value requires completion evidence and a named local reviewer."
            )
        if self.stage == "realised" and self.actual_value is None:
            raise ValueError(
                "Realised value must be explicitly recorded, including zero."
            )
        if self.stage != "realised" and self.actual_value is not None:
            raise ValueError("Actual value is only recorded in the realised stage.")
        return self


class RequirementInput(Request):
    requirement: str = Field(min_length=10, max_length=4000)
    source_reference: str = Field(min_length=5, max_length=1500)
    compliance: Literal["unassessed", "gap", "evidenced"] = "unassessed"
    evidence: str = Field(default="", max_length=4000)
    owner: Name = "Unassigned"

    @model_validator(mode="after")
    def require_compliance_evidence(self):
        if self.compliance == "evidenced" and len(self.evidence) < 10:
            raise ValueError(
                "A compliance claim needs a supporting evidence reference."
            )
        return self


class TenderExtract(Request):
    text: str = Field(min_length=10, max_length=100000)
    source_reference: str = Field(min_length=5, max_length=1300)


class TenderCapture(Request):
    requirements: list[RequirementInput] = Field(min_length=1, max_length=100)
