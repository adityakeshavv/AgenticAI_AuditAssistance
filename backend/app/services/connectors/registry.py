from __future__ import annotations

from functools import lru_cache

from .base import BaseDatabaseConnector
from .postgresql import PostgreSQLConnector


@lru_cache(maxsize=1)
def _connector_map() -> dict[str, BaseDatabaseConnector]:
    connectors = [PostgreSQLConnector()]
    return {connector.database_type: connector for connector in connectors}


def get_connector(database_type: str | None) -> BaseDatabaseConnector:
    key = (database_type or "postgresql").strip().lower()
    connector = _connector_map().get(key)
    if connector is None:
        raise ValueError(f"Unsupported database type: {database_type or 'unknown'}")
    return connector


def supported_database_types() -> list[dict[str, str]]:
    return [
        {
            "value": connector.database_type,
            "label": connector.display_name,
        }
        for connector in _connector_map().values()
    ]
