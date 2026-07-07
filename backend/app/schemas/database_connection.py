from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatabaseConnectionCreate(BaseModel):
    connection_name: str
    database_type: str = "postgresql"
    host: str
    port: int = 5432
    database_name: str
    username: str
    password: str
    selected_schemas: list[str] = Field(default_factory=list)
    selected_tables: list[str] = Field(default_factory=list)


class DatabaseConnectionTestRequest(DatabaseConnectionCreate):
    pass


class DatabaseConnectionSelectionUpdate(BaseModel):
    selected_schemas: list[str] = Field(default_factory=list)
    selected_tables: list[str] = Field(default_factory=list)
    is_default: bool | None = None


class DatabaseConnectionResponse(BaseModel):
    connection_id: str
    connection_name: str
    database_type: str
    host: str
    port: int
    database_name: str
    username: str
    is_default: bool
    is_active: bool
    selected_schemas: list[str] = Field(default_factory=list)
    selected_tables: list[str] = Field(default_factory=list)
    last_test_status: str | None = None
    last_test_message: str | None = None
    last_tested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatabaseConnectionSchemaInfo(BaseModel):
    schema_name: str
    tables: list[str] = Field(default_factory=list)
    table_count: int = 0


class DatabaseConnectionTableInfo(BaseModel):
    table_name: str
    schema_name: str
    columns: list[str] = Field(default_factory=list)


class DatabaseConnectionTestResponse(BaseModel):
    success: bool
    message: str
    schemas: list[DatabaseConnectionSchemaInfo] = Field(default_factory=list)
    tables: list[DatabaseConnectionTableInfo] = Field(default_factory=list)


class DatabaseConnectionDetailResponse(DatabaseConnectionResponse):
    schema_overview: list[DatabaseConnectionSchemaInfo] = Field(default_factory=list)
    selected_tables_detail: list[DatabaseConnectionTableInfo] = Field(default_factory=list)


class DatabaseConnectionListResponse(BaseModel):
    connections: list[DatabaseConnectionResponse] = Field(default_factory=list)


class DatabaseConnectionActivationResponse(BaseModel):
    success: bool
    connection: DatabaseConnectionResponse


class DatabaseConnectionMutationResponse(BaseModel):
    success: bool
    connection: DatabaseConnectionResponse
    message: str | None = None
