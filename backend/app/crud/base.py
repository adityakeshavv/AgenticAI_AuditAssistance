from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def apply_pagination(statement: Select[Any], page: int, page_size: int) -> Select[Any]:
    return statement.offset((page - 1) * page_size).limit(page_size)


def count_statement(db: Session, statement: Select[Any]) -> int:
    subquery = statement.order_by(None).subquery()
    return db.scalar(select(func.count()).select_from(subquery)) or 0
