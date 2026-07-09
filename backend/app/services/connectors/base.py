from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class ConnectionTestResult:
    success: bool
    message: str
    schemas: list[dict[str, Any]]
    tables: list[dict[str, Any]]


class BaseDatabaseConnector(ABC):
    database_type: str = ""
    display_name: str = ""

    def test_connection(self, payload: dict[str, Any]) -> ConnectionTestResult:
        try:
            engine = self.build_engine_from_payload(payload)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                inspector = inspect(connection)
                schemas = self.schema_overview(inspector)
                tables = self.table_overview(inspector)
            return ConnectionTestResult(
                success=True,
                message="Connection successful.",
                schemas=schemas,
                tables=tables,
            )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message=str(exc),
                schemas=[],
                tables=[],
            )

    @abstractmethod
    def build_engine_from_payload(self, payload: dict[str, Any]) -> Engine:
        raise NotImplementedError

    @abstractmethod
    def build_engine_from_connection(self, connection: Any) -> Engine:
        raise NotImplementedError

    def schema_overview(self, inspector: Any) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        try:
            for schema_name in sorted(inspector.get_schema_names()):
                if schema_name in {"information_schema", "pg_catalog"}:
                    continue
                tables = sorted(inspector.get_table_names(schema=schema_name))
                schemas.append(
                    {
                        "schema_name": schema_name,
                        "tables": tables,
                        "table_count": len(tables),
                    }
                )
        except Exception:
            return []
        return schemas

    def table_overview(self, inspector: Any, *, schema_name: str | None = None) -> list[dict[str, Any]]:
        tables: list[dict[str, Any]] = []
        try:
            schema_names = (
                [schema_name]
                if schema_name
                else [item for item in inspector.get_schema_names() if item not in {"information_schema", "pg_catalog"}]
            )
            for schema in schema_names:
                for table_name in sorted(inspector.get_table_names(schema=schema)):
                    columns = [column["name"] for column in inspector.get_columns(table_name, schema=schema)]
                    tables.append(
                        {
                            "table_name": table_name,
                            "schema_name": schema,
                            "columns": columns,
                        }
                    )
        except Exception:
            return []
        return tables
