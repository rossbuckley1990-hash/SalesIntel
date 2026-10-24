from datetime import date

from app.schemas.common import MisiSchema


class ExecutiveActionBase(MisiSchema):
    priority: str
    category: str
    owner: str
    due_date: date | None = None
    related_opportunity_id: int | None = None
    commercial_value: float | None = None
    reason: str = ""
    recommended_action: str = ""
    status: str = "open"


class ExecutiveActionCreate(ExecutiveActionBase):
    pass


class ExecutiveActionRead(ExecutiveActionBase):
    id: int

