from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ExecutiveAction
from app.routers.query import Limit, contains_text
from app.schemas import ExecutiveActionRead

router = APIRouter(prefix="/api/executive-actions", tags=["executive actions"])


@router.get("", response_model=list[ExecutiveActionRead])
def list_executive_actions(
    db: Session = Depends(get_db),
    limit: Limit = 100,
    owner: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[ExecutiveAction]:
    statement = select(ExecutiveAction).order_by(ExecutiveAction.id)

    if owner:
        statement = statement.where(ExecutiveAction.owner == owner)
    if priority:
        statement = statement.where(ExecutiveAction.priority == priority)
    if status:
        statement = statement.where(ExecutiveAction.status == status)

    search_clause = contains_text(
        ExecutiveAction.category,
        ExecutiveAction.owner,
        ExecutiveAction.reason,
        ExecutiveAction.recommended_action,
        search=search,
    )
    if search_clause is not None:
        statement = statement.where(search_clause)

    return list(db.scalars(statement.limit(limit)))

