from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database_connection import DatabaseConnection


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_connections_for_user(db: Session, user_id: str) -> list[DatabaseConnection]:
    stmt = select(DatabaseConnection).where(DatabaseConnection.owner_user_id == user_id).order_by(
        DatabaseConnection.is_default.desc(),
        DatabaseConnection.created_at.desc(),
    )
    return list(db.scalars(stmt).all())


def list_all_connections(db: Session) -> list[DatabaseConnection]:
    stmt = select(DatabaseConnection).order_by(
        DatabaseConnection.is_default.desc(),
        DatabaseConnection.created_at.desc(),
    )
    return list(db.scalars(stmt).all())


def get_connection_by_id(db: Session, connection_id: str, *, user_id: str | None = None) -> DatabaseConnection | None:
    stmt = select(DatabaseConnection).where(DatabaseConnection.connection_id == connection_id)
    if user_id:
        stmt = stmt.where(DatabaseConnection.owner_user_id == user_id)
    return db.scalar(stmt)


def get_default_connection_for_user(db: Session, user_id: str) -> DatabaseConnection | None:
    stmt = (
        select(DatabaseConnection)
        .where(DatabaseConnection.owner_user_id == user_id, DatabaseConnection.is_default.is_(True), DatabaseConnection.is_active.is_(True))
        .order_by(DatabaseConnection.created_at.desc())
    )
    return db.scalar(stmt)


def create_connection(
    db: Session,
    *,
    owner_user_id: str,
    connection_name: str,
    database_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password_ciphertext: str,
    selected_schemas: list[str] | None = None,
    selected_tables: list[str] | None = None,
    is_default: bool = False,
    is_active: bool = True,
) -> DatabaseConnection:
    connection = DatabaseConnection(
        connection_id=str(uuid4()),
        owner_user_id=owner_user_id,
        connection_name=connection_name.strip(),
        database_type=database_type.strip().lower(),
        host=host.strip(),
        port=port,
        database_name=database_name.strip(),
        username=username.strip(),
        password_ciphertext=password_ciphertext,
        is_default=is_default,
        is_active=is_active,
        selected_schemas=selected_schemas or [],
        selected_tables=selected_tables or [],
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(connection)
    db.flush()
    return connection


def update_connection_selection(
    db: Session,
    connection: DatabaseConnection,
    *,
    selected_schemas: list[str] | None = None,
    selected_tables: list[str] | None = None,
) -> DatabaseConnection:
    if selected_schemas is not None:
        connection.selected_schemas = selected_schemas
    if selected_tables is not None:
        connection.selected_tables = selected_tables
    connection.updated_at = _now()
    db.add(connection)
    db.flush()
    return connection


def set_default_connection(db: Session, *, user_id: str, connection_id: str) -> DatabaseConnection | None:
    connections = list_connections_for_user(db, user_id)
    target = next((connection for connection in connections if connection.connection_id == connection_id), None)
    if target is None:
        return None

    for connection in connections:
        connection.is_default = connection.connection_id == connection_id
        connection.updated_at = _now()
        db.add(connection)
    db.flush()
    return target


def update_connection_test_result(
    db: Session,
    connection: DatabaseConnection,
    *,
    status: str,
    message: str | None = None,
) -> DatabaseConnection:
    connection.last_test_status = status
    connection.last_test_message = message
    connection.last_tested_at = _now()
    connection.updated_at = _now()
    db.add(connection)
    db.flush()
    return connection


def delete_connection(db: Session, connection: DatabaseConnection) -> None:
    db.delete(connection)
    db.flush()
