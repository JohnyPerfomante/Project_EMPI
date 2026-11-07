from typing import Annotated

from fastapi import Query
from sqlalchemy import func, select

from app.schemas.common import ErrorResponse

Offset = Annotated[int, Query(ge=0, le=100_000)]
Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str | None, Query(max_length=160)]
COMMON_ERRORS = {status: {"model": ErrorResponse} for status in (400, 401, 403, 404, 409, 422, 429, 500)}


def paginate(db, query, offset, limit, transform=None, *, rows=False):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    records = (
        db.execute(query.offset(offset).limit(limit))
        if rows
        else db.scalars(query.offset(offset).limit(limit))
    )
    return {
        "items": [transform(record) if transform else record for record in records],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def search_text(column, query):
    return column.icontains(query, autoescape=True)
