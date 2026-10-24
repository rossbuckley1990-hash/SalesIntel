from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import Date, DateTime, Numeric, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models.living import AuditEvent


def json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def record(obj) -> dict:
    return {
        column.name: json_value(getattr(obj, column.name))
        for column in obj.__table__.columns
    }


def change(db: Session, obj, before: dict | None = None) -> dict:
    db.flush()
    db.refresh(obj)
    return {
        "table": obj.__tablename__,
        "id": obj.id,
        "before": before,
        "after": record(obj),
    }


def commit_event(
    db: Session, action: str, actor: str, changes: list[dict], reason: str = ""
) -> AuditEvent:
    event = AuditEvent(action=action, actor=actor, changes=changes, reason=reason)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def undo_latest(db: Session, event_id: int) -> dict:
    latest = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.undone.is_(False), AuditEvent.action != "undo")
        .order_by(AuditEvent.id.desc())
    )
    if latest is None or latest.id != event_id:
        raise HTTPException(
            409,
            "Only the latest remaining workspace change can be undone. Refresh to review the current change.",
        )
    models = {
        mapper.class_.__tablename__: mapper.class_ for mapper in Base.registry.mappers
    }
    pairs = []
    for entry in latest.changes:
        cls = models[entry["table"]]
        obj = db.get(cls, entry["id"])
        if obj is None or record(obj) != entry["after"]:
            raise HTTPException(
                409,
                "A source record changed after this action. Undo would overwrite newer work.",
            )
        pairs.append((entry, obj))
    # Child rows were added after parents. Reverse order respects foreign keys.
    for entry, obj in reversed(pairs):
        if entry["before"] is None:
            db.delete(obj)
            db.flush()
        else:
            for column in obj.__table__.columns:
                value = entry["before"][column.name]
                if value is not None:
                    if isinstance(column.type, DateTime):
                        value = datetime.fromisoformat(value)
                    elif isinstance(column.type, Date):
                        value = date.fromisoformat(value)
                    elif isinstance(column.type, Numeric):
                        value = Decimal(value)
                setattr(obj, column.name, value)
            db.flush()
    latest.undone = True
    db.add(
        AuditEvent(
            action="undo",
            actor="Local reviewer",
            reason=f"Reversed event {event_id}: {latest.action}",
            changes=[],
        )
    )
    db.commit()
    return {"undone_event_id": event_id}
