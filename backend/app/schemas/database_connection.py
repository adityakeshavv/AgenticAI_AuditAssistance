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
    column_count: int = 0


class DatabaseTableColumnInfo(BaseModel):
    name: str
    data_type: str | None = None
    nullable: bool | None = None
    default: str | None = None


class DatabaseConnectionTableDetailResponse(DatabaseConnectionTableInfo):
    summary: str = ""
    row_count: int = 0
    primary_key_columns: list[str] = Field(default_factory=list)
    column_details: list[DatabaseTableColumnInfo] = Field(default_factory=list)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


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


class DocumentUploadResponse(BaseModel):
    success: bool
    message: str
    document: dict[str, Any] = Field(default_factory=dict)
    processing: dict[str, Any] = Field(default_factory=dict)


class DocumentMetadataRecord(BaseModel):
    document_id: str
    document_type: str
    document_category: str
    related_vendor_id: str | None = None
    related_employee_id: str | None = None
    related_transaction_id: str | None = None
    related_contract_id: str | None = None
    related_investigation_id: str | None = None
    creation_date: str
    file_name: str
    file_path: str
    source_uri: str
    source_metadata_file: str
    created_at: str | None = None
    updated_at: str | None = None


class DocumentMetadataListResponse(BaseModel):
    documents: list[DocumentMetadataRecord] = Field(default_factory=list)
