"""Persist source-linked completion evidence and validated action prerequisites."""

from fastapi import HTTPException
from sqlalchemy import select
from app.models import ExecutiveAction
from app.models.living import ActionDetails
from app.services.living.audit import change, record


def action_records(db, opportunity_id=None):
    details = {d.action_id: d for d in db.scalars(select(ActionDetails))}
    actions = list(
        db.scalars(
            select(ExecutiveAction).order_by(
                ExecutiveAction.due_date, ExecutiveAction.id
            )
        )
    )
    statuses = {a.id: a.status for a in actions}
    result = []
    for action in actions:
        if (
            opportunity_id is not None
            and action.related_opportunity_id != opportunity_id
        ):
            continue
        extra = details.get(action.id)
        dependencies = extra.depends_on if extra else []
        result.append(
            {
                **record(action),
                "depends_on": dependencies,
                "blocked_by": [
                    i for i in dependencies if statuses.get(i) != "completed"
                ],
                "completion_evidence": extra.completion_evidence if extra else "",
            }
        )
    return result


def save_details(db, action, dependencies, evidence=""):
    dependencies = list(dict.fromkeys(dependencies))
    details = {d.action_id: d for d in db.scalars(select(ActionDetails))}
    graph = {key: value.depends_on for key, value in details.items()}
    graph[action.id] = dependencies
    for prerequisite in dependencies:
        parent = db.get(ExecutiveAction, prerequisite)
        if (
            parent is None
            or parent.related_opportunity_id != action.related_opportunity_id
        ):
            raise HTTPException(
                422, "Prerequisites must be existing actions on the same opportunity."
            )
        pending, seen = [prerequisite], set()
        while pending:
            current = pending.pop()
            if current == action.id:
                raise HTTPException(422, "Action dependencies cannot contain a cycle.")
            if current not in seen:
                seen.add(current)
                pending.extend(graph.get(current, []))
        if action.status == "completed" and parent.status != "completed":
            raise HTTPException(
                422,
                f"Complete prerequisite action {prerequisite} before closing this action.",
            )
    extra = details.get(action.id)
    before = record(extra) if extra else None
    if extra is None:
        extra = ActionDetails(action_id=action.id)
        db.add(extra)
    extra.depends_on = dependencies
    if evidence:
        extra.completion_evidence = evidence
    return change(db, extra, before)
