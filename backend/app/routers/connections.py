from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user, require_connection_access
from app.dependencies.database import get_db
from app.schemas.auth import AuthUser
from app.schemas.database_connection import (
    DatabaseConnectionActivationResponse,
    DatabaseConnectionCreate,
    DatabaseConnectionDetailResponse,
    DatabaseConnectionListResponse,
    DatabaseConnectionMutationResponse,
    DatabaseConnectionResponse,
    DatabaseConnectionSchemaInfo,
    DatabaseConnectionTableDetailResponse,
    DatabaseConnectionSelectionUpdate,
    DatabaseConnectionTableInfo,
    DocumentMetadataListResponse,
    DocumentMetadataRecord,
    DocumentUploadResponse,
    DatabaseConnectionTestRequest,
    DatabaseConnectionTestResponse,
)
from app.services.database_connector_service import DatabaseConnectorService
from app.services.document_metadata_service import DocumentMetadataService
from app.services.document_upload_service import DocumentUploadService


router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("", response_model=DatabaseConnectionListResponse)
def list_connections(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> dict:
    svc = DatabaseConnectorService(db)
    return {"connections": svc.list_connections(current_user.user_id)}


@router.post("/test", response_model=DatabaseConnectionTestResponse)
def test_connection(
    payload: DatabaseConnectionTestRequest,
    db: Session = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
) -> dict:
    svc = DatabaseConnectorService(db)
    result = svc.test_connection(payload.model_dump())
    return {
        "success": result.success,
        "message": result.message,
        "schemas": [DatabaseConnectionSchemaInfo(**schema) for schema in result.schemas],
        "tables": [DatabaseConnectionTableInfo(**table) for table in result.tables],
    }


@router.post("", response_model=DatabaseConnectionMutationResponse)
def create_connection(
    payload: DatabaseConnectionCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> dict:
    svc = DatabaseConnectorService(db)
    result = svc.create_connection(user_id=current_user.user_id, payload=payload.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message", "Unable to save connection."))
    return {
        "success": True,
        "message": result.get("message"),
        "connection": DatabaseConnectionResponse(**result["connection"]),
    }


@router.get("/{connection_id}", response_model=DatabaseConnectionDetailResponse)
def get_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_connection_access),
) -> dict:
    svc = DatabaseConnectorService(db)
    connection = svc.get_connection(current_user.user_id, connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    schema_overview = svc.list_schema_overview(user_id=current_user.user_id, connection_id=connection_id)
    table_overview = svc.list_table_overview(user_id=current_user.user_id, connection_id=connection_id)
    payload = svc.serialize_connection(connection)
    return {
        **payload,
        "schema_overview": [DatabaseConnectionSchemaInfo(**schema) for schema in schema_overview],
        "selected_tables_detail": [DatabaseConnectionTableInfo(**table) for table in table_overview],
    }


@router.get("/{connection_id}/schemas", response_model=list[DatabaseConnectionSchemaInfo])
def list_schemas(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_connection_access),
) -> list[DatabaseConnectionSchemaInfo]:
    svc = DatabaseConnectorService(db)
    schemas = svc.list_schema_overview(user_id=current_user.user_id, connection_id=connection_id)
    return [DatabaseConnectionSchemaInfo(**schema) for schema in schemas]


@router.get("/{connection_id}/tables", response_model=list[DatabaseConnectionTableInfo])
def list_tables(
    connection_id: str,
    schema_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_connection_access),
) -> list[DatabaseConnectionTableInfo]:
    svc = DatabaseConnectorService(db)
    tables = svc.list_table_overview(user_id=current_user.user_id, connection_id=connection_id, schema_name=schema_name)
    return [DatabaseConnectionTableInfo(**table) for table in tables]


@router.get("/{connection_id}/tables/{schema_name}/{table_name}", response_model=DatabaseConnectionTableDetailResponse)
def get_table_detail(
    connection_id: str,
    schema_name: str,
    table_name: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_connection_access),
) -> DatabaseConnectionTableDetailResponse:
    svc = DatabaseConnectorService(db)
    detail = svc.get_table_detail(
        user_id=current_user.user_id,
        connection_id=connection_id,
        schema_name=schema_name,
        table_name=table_name,
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
    return DatabaseConnectionTableDetailResponse(**detail)


@router.get("/documents", response_model=DocumentMetadataListResponse)
def list_documents(
    search: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    document_category: str | None = Query(default=None),
    related_vendor_id: str | None = Query(default=None),
    related_employee_id: str | None = Query(default=None),
    related_transaction_id: str | None = Query(default=None),
    related_contract_id: str | None = Query(default=None),
    related_investigation_id: str | None = Query(default=None),
    uploaded_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> DocumentMetadataListResponse:
    svc = DocumentMetadataService(db)
    documents = svc.list_documents(
        search=search,
        document_type=document_type,
        document_category=document_category,
        related_vendor_id=related_vendor_id,
        related_employee_id=related_employee_id,
        related_transaction_id=related_transaction_id,
        related_contract_id=related_contract_id,
        related_investigation_id=related_investigation_id,
        uploaded_only=uploaded_only,
    )
    return {"documents": [DocumentMetadataRecord(**document) for document in documents]}


@router.patch("/{connection_id}/selection", response_model=DatabaseConnectionMutationResponse)
def update_selection(
    connection_id: str,
    payload: DatabaseConnectionSelectionUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_connection_access),
) -> dict:
    svc = DatabaseConnectorService(db)
    result = svc.update_selection(
        user_id=current_user.user_id,
        connection_id=connection_id,
        selected_schemas=payload.selected_schemas,
        selected_tables=payload.selected_tables,
        is_default=payload.is_default,
    )
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message", "Connection not found."))
    return {
        "success": True,
        "message": result.get("message"),
        "connection": DatabaseConnectionResponse(**result["connection"]),
    }


@router.post("/{connection_id}/activate", response_model=DatabaseConnectionActivationResponse)
def activate_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_connection_access),
) -> dict:
    svc = DatabaseConnectorService(db)
    result = svc.activate_connection(user_id=current_user.user_id, connection_id=connection_id)
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message", "Connection not found."))
    return {
        "success": True,
        "connection": DatabaseConnectionResponse(**result["connection"]),
    }


@router.delete("/{connection_id}")
def delete_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_connection_access),
) -> dict:
    svc = DatabaseConnectorService(db)
    result = svc.delete_connection(user_id=current_user.user_id, connection_id=connection_id)
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message", "Connection not found."))
    return {"success": True}


@router.post("/documents/upload", response_model=DocumentUploadResponse)
def upload_document(
    file: UploadFile = File(...),
    document_type: str | None = Form(default=None),
    document_category: str | None = Form(default=None),
    related_vendor_id: str | None = Form(default=None),
    related_employee_id: str | None = Form(default=None),
    related_transaction_id: str | None = Form(default=None),
    related_contract_id: str | None = Form(default=None),
    related_investigation_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> DocumentUploadResponse:
    svc = DocumentUploadService(db)
    result = svc.upload_document(
        user_id=current_user.user_id,
        actor_name=current_user.full_name or current_user.email,
        file=file,
        document_type=document_type,
        document_category=document_category,
        related_vendor_id=related_vendor_id,
        related_employee_id=related_employee_id,
        related_transaction_id=related_transaction_id,
        related_contract_id=related_contract_id,
        related_investigation_id=related_investigation_id,
    )
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message", "Unable to upload document."))
    return DocumentUploadResponse(**result)
