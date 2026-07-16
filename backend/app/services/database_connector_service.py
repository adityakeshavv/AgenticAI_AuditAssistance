from __future__ import annotations

import base64
import hashlib
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from cryptography.fernet import Fernet
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.exceptions import format_human_error
from app.crud import audit_workspace_crud, database_connection_crud, user_crud
from app.models.database_connection import DatabaseConnection
from app.services.connectors import ConnectionTestResult, get_connector, supported_database_types
from app.services.governance_audit_service import GovernanceAuditService


logger = logging.getLogger(__name__)


class DatabaseConnectorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self._engine_cache: dict[str, Engine] = {}

    def list_connections(self, user_id: str) -> list[dict[str, Any]]:
        return [self.serialize_connection(connection) for connection in database_connection_crud.list_connections_for_user(self.db, user_id)]

    def list_all_connections(self) -> list[dict[str, Any]]:
        return [self.serialize_connection(connection) for connection in database_connection_crud.list_all_connections(self.db)]

    def list_supported_database_types(self) -> list[dict[str, str]]:
        return supported_database_types()

    def get_connection(self, user_id: str, connection_id: str) -> DatabaseConnection | None:
        return database_connection_crud.get_connection_by_id(self.db, connection_id, user_id=user_id)

    def create_connection(self, *, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        test_result = self._perform_connection_test(payload)
        if not test_result.success:
            GovernanceAuditService(self.db).record_event(
                actor_user_id=user_id,
                action_type="connection_create_failed",
                entity_type="database_connection",
                severity="warning",
                summary=test_result.message,
                after_state={
                    "connection_name": str(payload.get("connection_name", "")).strip(),
                    "database_type": str(payload.get("database_type", "postgresql")).strip().lower(),
                    "host": str(payload.get("host", "")).strip(),
                    "port": int(payload.get("port", 5432)),
                    "database_name": str(payload.get("database_name", "")).strip(),
                },
                actor_name=self._actor_name(user_id),
            )
            self.db.commit()
            return {
                "success": False,
                "message": test_result.message,
                "schemas": test_result.schemas,
                "tables": test_result.tables,
            }

        password_ciphertext = self.encrypt_secret(str(payload.get("password", "")))
        existing_connections = database_connection_crud.list_connections_for_user(self.db, user_id)
        is_default = not existing_connections or not any(connection.is_default for connection in existing_connections)
        connection = database_connection_crud.create_connection(
            self.db,
            owner_user_id=user_id,
            connection_name=str(payload.get("connection_name", "")).strip(),
            database_type=str(payload.get("database_type", "postgresql")).strip().lower(),
            host=str(payload.get("host", "")).strip(),
            port=int(payload.get("port", 5432)),
            database_name=str(payload.get("database_name", "")).strip(),
            username=str(payload.get("username", "")).strip(),
            password_ciphertext=password_ciphertext,
            selected_schemas=list(payload.get("selected_schemas") or []),
            selected_tables=list(payload.get("selected_tables") or []),
            is_default=is_default,
            is_active=True,
        )
        database_connection_crud.update_connection_test_result(
            self.db,
            connection,
            status="passed",
            message="Connection validated successfully.",
        )
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            action_type="connection_created",
            entity_type="database_connection",
            entity_id=connection.connection_id,
            connection_id=connection.connection_id,
            severity="info",
            summary=f"Database connection '{connection.connection_name}' was created and validated.",
            after_state=self.serialize_connection(connection),
            actor_name=self._actor_name(user_id),
        )
        self.db.commit()
        self._reset_engine_cache()
        return {
            "success": True,
            "message": "Database connection saved successfully.",
            "connection": self.serialize_connection(connection),
            "schemas": test_result.schemas,
            "tables": test_result.tables,
        }

    def test_connection(self, payload: dict[str, Any]) -> ConnectionTestResult:
        result = self._perform_connection_test(payload)
        try:
            actor_user_id = self._resolve_actor_user_id(payload)
            GovernanceAuditService(self.db).record_event(
                actor_user_id=actor_user_id,
                action_type="connection_tested",
                entity_type="database_connection",
                severity="info" if result.success else "warning",
                summary=result.message,
                actor_name=self._actor_name(actor_user_id),
                after_state={
                    "connection_name": str(payload.get("connection_name", "")).strip(),
                    "database_type": str(payload.get("database_type", "postgresql")).strip().lower(),
                    "host": str(payload.get("host", "")).strip(),
                    "port": int(payload.get("port", 5432)),
                    "database_name": str(payload.get("database_name", "")).strip(),
                },
            )
            self.db.commit()
        except Exception:
            pass
        return result

    def _perform_connection_test(self, payload: dict[str, Any]) -> ConnectionTestResult:
        database_type = str(payload.get("database_type", "postgresql")).strip().lower()
        try:
            connector = get_connector(database_type)
            return connector.test_connection(payload)
        except Exception as exc:
            logger.warning("Database connection test failed: %s", exc)
            message = format_human_error(
                exc,
                "Database connection failed. Please verify the host, port, database name, username, and password.",
            )
            return ConnectionTestResult(
                success=False,
                message=message,
                schemas=[],
                tables=[],
            )

    def update_selection(
        self,
        *,
        user_id: str,
        connection_id: str,
        selected_schemas: list[str] | None = None,
        selected_tables: list[str] | None = None,
        is_default: bool | None = None,
    ) -> dict[str, Any]:
        connection = self.get_connection(user_id, connection_id)
        if connection is None:
            return {"success": False, "message": "Connection not found."}

        database_connection_crud.update_connection_selection(
            self.db,
            connection,
            selected_schemas=selected_schemas,
            selected_tables=selected_tables,
        )
        if is_default is True:
            database_connection_crud.set_default_connection(self.db, user_id=user_id, connection_id=connection_id)
        elif is_default is False and connection.is_default:
            connection.is_default = False
            connection.updated_at = self._now()
            self.db.add(connection)
            self.db.flush()

        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            action_type="connection_updated",
            entity_type="database_connection",
            entity_id=connection.connection_id,
            connection_id=connection.connection_id,
            severity="info",
            summary=f"Connection '{connection.connection_name}' selection was updated.",
            after_state=self.serialize_connection(connection),
            actor_name=self._actor_name(user_id),
        )
        self.db.commit()
        self._reset_engine_cache()
        return {"success": True, "connection": self.serialize_connection(connection)}

    def activate_connection(self, *, user_id: str, connection_id: str) -> dict[str, Any]:
        connection = database_connection_crud.set_default_connection(self.db, user_id=user_id, connection_id=connection_id)
        if connection is None:
            return {"success": False, "message": "Connection not found."}
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            action_type="connection_activated",
            entity_type="database_connection",
            entity_id=connection.connection_id,
            connection_id=connection.connection_id,
            severity="info",
            summary=f"Connection '{connection.connection_name}' was activated.",
            after_state=self.serialize_connection(connection),
            actor_name=self._actor_name(user_id),
        )
        self.db.commit()
        self._reset_engine_cache()
        return {"success": True, "connection": self.serialize_connection(connection)}

    def delete_connection(self, *, user_id: str, connection_id: str) -> dict[str, Any]:
        connection = self.get_connection(user_id, connection_id)
        if connection is None:
            return {"success": False, "message": "Connection not found."}
        was_default = connection.is_default
        before_state = self.serialize_connection(connection)
        database_connection_crud.delete_connection(self.db, connection)
        if was_default:
            remaining = database_connection_crud.list_connections_for_user(self.db, user_id)
            if remaining:
                database_connection_crud.set_default_connection(self.db, user_id=user_id, connection_id=remaining[0].connection_id)
        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            action_type="connection_deleted",
            entity_type="database_connection",
            entity_id=connection_id,
            connection_id=connection_id,
            severity="warning",
            summary=f"Connection '{before_state['connection_name']}' was deleted.",
            before_state=before_state,
            actor_name=self._actor_name(user_id),
        )
        self.db.commit()
        self._reset_engine_cache()
        return {"success": True}

    def list_schema_overview(self, *, user_id: str, connection_id: str | None = None, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with self.open_session(user_id=user_id, connection_id=connection_id, workspace_id=workspace_id) as session:
            connection = self._resolve_connection(user_id=user_id, connection_id=connection_id, workspace_id=workspace_id)
            inspector = inspect(session.get_bind())
            if connection is None:
                return self._schema_overview(inspector)
            connector = get_connector(connection.database_type)
            return connector.schema_overview(inspector)

    def list_table_overview(self, *, user_id: str, connection_id: str | None = None, workspace_id: str | None = None, schema_name: str | None = None) -> list[dict[str, Any]]:
        with self.open_session(user_id=user_id, connection_id=connection_id, workspace_id=workspace_id) as session:
            connection = self._resolve_connection(user_id=user_id, connection_id=connection_id, workspace_id=workspace_id)
            inspector = inspect(session.get_bind())
            if connection is None:
                return self._table_overview(inspector, schema_name=schema_name)
            connector = get_connector(connection.database_type)
            return connector.table_overview(inspector, schema_name=schema_name)

    def get_table_detail(
        self,
        *,
        user_id: str,
        connection_id: str | None = None,
        workspace_id: str | None = None,
        schema_name: str,
        table_name: str,
        preview_limit: int = 5,
    ) -> dict[str, Any] | None:
        with self.open_session(user_id=user_id, connection_id=connection_id, workspace_id=workspace_id) as session:
            connection = self._resolve_connection(user_id=user_id, connection_id=connection_id, workspace_id=workspace_id)
            if connection is None:
                return None
            inspector = inspect(session.get_bind())
            table_columns = inspector.get_columns(table_name, schema=schema_name)
            primary_key = inspector.get_pk_constraint(table_name, schema=schema_name) or {}
            column_details = [
                {
                    "name": column.get("name"),
                    "data_type": str(column.get("type")) if column.get("type") is not None else None,
                    "nullable": bool(column.get("nullable", True)),
                    "default": str(column.get("default")) if column.get("default") is not None else None,
                }
                for column in table_columns
            ]
            column_names = [column.get("name") for column in table_columns if column.get("name")]
            quoted_table = self._qualified_table_name(schema_name, table_name)
            row_count = 0
            sample_rows: list[dict[str, Any]] = []
            try:
                row_count = int(session.execute(text(f"SELECT COUNT(*) AS row_count FROM {quoted_table}")).scalar_one())
            except Exception as exc:
                logger.debug("Table row count failed for %s.%s: %s", schema_name, table_name, exc)
            try:
                sample_rows = [dict(row) for row in session.execute(text(f"SELECT * FROM {quoted_table} LIMIT :limit"), {"limit": preview_limit}).mappings().all()]
            except Exception as exc:
                logger.debug("Table preview failed for %s.%s: %s", schema_name, table_name, exc)
            return {
                "table_name": table_name,
                "schema_name": schema_name,
                "columns": column_names,
                "column_count": len(column_names),
                "column_details": column_details,
                "row_count": row_count,
                "primary_key_columns": list(primary_key.get("constrained_columns") or []),
                "sample_rows": sample_rows,
                "summary": self._table_summary(table_name=table_name, schema_name=schema_name, row_count=row_count, column_count=len(column_names)),
            }

    @contextmanager
    def open_session(self, *, user_id: str, connection_id: str | None = None, workspace_id: str | None = None) -> Iterator[Session]:
        connection = self._resolve_connection(user_id=user_id, connection_id=connection_id, workspace_id=workspace_id)
        if connection is None:
            yield self.db
            return

        engine = self._engine_for_connection(connection)
        SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
        session = SessionFactory()
        try:
            yield session
        finally:
            session.close()

    def serialize_connection(self, connection: DatabaseConnection) -> dict[str, Any]:
        return {
            "connection_id": connection.connection_id,
            "connection_name": connection.connection_name,
            "database_type": connection.database_type,
            "host": connection.host,
            "port": connection.port,
            "database_name": connection.database_name,
            "username": connection.username,
            "is_default": connection.is_default,
            "is_active": connection.is_active,
            "selected_schemas": list(connection.selected_schemas or []),
            "selected_tables": list(connection.selected_tables or []),
            "last_test_status": connection.last_test_status,
            "last_test_message": connection.last_test_message,
            "last_tested_at": connection.last_tested_at.isoformat() if connection.last_tested_at else None,
            "created_at": connection.created_at.isoformat() if connection.created_at else None,
            "updated_at": connection.updated_at.isoformat() if connection.updated_at else None,
        }

    def encrypt_secret(self, value: str) -> str:
        return self._fernet().encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_secret(self, value: str) -> str:
        return self._fernet().decrypt(value.encode("utf-8")).decode("utf-8")

    def _resolve_connection(self, *, user_id: str, connection_id: str | None, workspace_id: str | None = None) -> DatabaseConnection | None:
        if workspace_id:
            workspace = audit_workspace_crud.get_workspace_by_id(self.db, workspace_id, user_id=user_id)
            if workspace is not None:
                active_connection_id = workspace.active_connection_id or (workspace.selected_connection_ids[0] if workspace.selected_connection_ids else None)
                if active_connection_id:
                    workspace_connection = database_connection_crud.get_connection_by_id(self.db, active_connection_id, user_id=user_id)
                    if workspace_connection is not None:
                        return workspace_connection
        if connection_id:
            direct_connection = database_connection_crud.get_connection_by_id(self.db, connection_id, user_id=user_id)
            if direct_connection is not None:
                return direct_connection
        return database_connection_crud.get_default_connection_for_user(self.db, user_id)

    def _engine_for_connection(self, connection: DatabaseConnection) -> Engine:
        cache_key = connection.connection_id
        if cache_key in self._engine_cache:
            return self._engine_cache[cache_key]

        password = self.decrypt_secret(connection.password_ciphertext)
        connector = get_connector(connection.database_type)
        engine = connector.build_engine_from_connection(
            {
                "database_type": connection.database_type,
                "username": connection.username,
                "password": password,
                "host": connection.host,
                "port": connection.port,
                "database_name": connection.database_name,
            }
        )
        self._engine_cache[cache_key] = engine
        return engine

    def _schema_overview(self, inspector: Any) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        try:
            for schema_name in sorted(inspector.get_schema_names()):
                if schema_name in {"information_schema", "pg_catalog"}:
                    continue
                tables = sorted(inspector.get_table_names(schema=schema_name))
                schemas.append({
                    "schema_name": schema_name,
                    "tables": tables,
                    "table_count": len(tables),
                })
        except Exception as exc:
            logger.debug("Schema inspection failed: %s", exc)
        return schemas

    def _table_overview(self, inspector: Any, *, schema_name: str | None = None) -> list[dict[str, Any]]:
        tables: list[dict[str, Any]] = []
        try:
            schema_names = [schema_name] if schema_name else [s for s in inspector.get_schema_names() if s not in {"information_schema", "pg_catalog"}]
            for schema in schema_names:
                for table_name in sorted(inspector.get_table_names(schema=schema)):
                    columns = [column["name"] for column in inspector.get_columns(table_name, schema=schema)]
                    tables.append({
                        "table_name": table_name,
                        "schema_name": schema,
                        "columns": columns,
                        "column_count": len(columns),
                    })
        except Exception as exc:
            logger.debug("Table inspection failed: %s", exc)
        return tables

    def _qualified_table_name(self, schema_name: str, table_name: str) -> str:
        return f'{self._quote_identifier(schema_name)}.{self._quote_identifier(table_name)}'

    def _quote_identifier(self, value: str) -> str:
        escaped = value.replace('"', '""')
        return f'"{escaped}"'

    def _table_summary(self, *, table_name: str, schema_name: str, row_count: int, column_count: int) -> str:
        return f'Table "{schema_name}.{table_name}" contains {row_count} row{"s" if row_count != 1 else ""} across {column_count} column{"s" if column_count != 1 else ""}.'

    def _fernet(self) -> Fernet:
        key = self.settings.database_connection_encryption_key.strip()
        if key:
            return Fernet(key.encode("utf-8"))

        secret = self.settings.auth_token_secret or self.settings.app_name
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def _reset_engine_cache(self) -> None:
        for engine in self._engine_cache.values():
            try:
                engine.dispose()
            except Exception:
                pass
        self._engine_cache.clear()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _resolve_actor_user_id(self, payload: dict[str, Any]) -> str | None:
        raw_user_id = payload.get("owner_user_id") or payload.get("user_id")
        return str(raw_user_id).strip() or None

    def _actor_name(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        user = user_crud.get_user_by_id(self.db, user_id)
        if user is None:
            return None
        return user.full_name or user.email
