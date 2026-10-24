from typing import Annotated

from fastapi import Query
from sqlalchemy import String, cast, or_
from sqlalchemy.sql.elements import ColumnElement

Limit = Annotated[int, Query(ge=1, le=500)]


def contains_text(*columns: object, search: str | None) -> ColumnElement[bool] | None:
    if not search:
        return None
    pattern = f"%{search.strip()}%"
    return or_(*(cast(column, String).ilike(pattern) for column in columns))

