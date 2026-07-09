from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL

from .base import BaseDatabaseConnector


def _field(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


class PostgreSQLConnector(BaseDatabaseConnector):
    database_type = "postgresql"
    display_name = "PostgreSQL"

    def build_engine_from_payload(self, payload: dict[str, Any]) -> Engine:
        database_type = str(payload.get("database_type", self.database_type)).strip().lower()
        if database_type != self.database_type:
            raise ValueError("Only PostgreSQL connections are supported in this sprint.")

        url = URL.create(
            "postgresql+psycopg",
            username=str(payload.get("username", "")).strip() or None,
            password=str(payload.get("password", "")).strip() or None,
            host=str(payload.get("host", "")).strip() or None,
            port=int(payload.get("port", 5432)),
            database=str(payload.get("database_name", "")).strip() or None,
        )
        return create_engine(url, pool_pre_ping=True)

    def build_engine_from_connection(self, connection: Any) -> Engine:
        database_type = str(_field(connection, "database_type", self.database_type)).strip().lower()
        if database_type != self.database_type:
            raise ValueError("Only PostgreSQL connections are supported in this sprint.")

        url = URL.create(
            "postgresql+psycopg",
            username=str(_field(connection, "username", "")).strip() or None,
            password=str(_field(connection, "password", "")).strip() or None,
            host=str(_field(connection, "host", "")).strip() or None,
            port=int(_field(connection, "port", 5432)),
            database=str(_field(connection, "database_name", "")).strip() or None,
        )
        return create_engine(url, pool_pre_ping=True)
