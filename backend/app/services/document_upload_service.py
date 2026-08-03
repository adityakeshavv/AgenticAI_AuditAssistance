from __future__ import annotations

import json
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import document_metadata_crud, user_crud
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_metadata_service import serialize_document_metadata
from app.services.semantic_retrieval_service import SemanticRetrievalService
from app.services.governance_audit_service import GovernanceAuditService


class DocumentUploadService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.processing_service = DocumentProcessingService()
        self.semantic_service = SemanticRetrievalService(db)

    def upload_document(
        self,
        *,
        user_id: str,
        actor_name: str | None,
        file: UploadFile,
        document_type: str | None = None,
        document_category: str | None = None,
        related_vendor_id: str | None = None,
        related_employee_id: str | None = None,
        related_transaction_id: str | None = None,
        related_contract_id: str | None = None,
        related_investigation_id: str | None = None,
    ) -> dict[str, Any]:
        original_name = Path(file.filename or "uploaded-document").name
        suffix = Path(original_name).suffix.lower()
        resolved_type = self._slugify(document_type or suffix.lstrip(".") or "document")
        resolved_category = self._slugify(document_category or document_type or suffix.lstrip(".") or "uploaded")

        upload_dir = Path(self.settings.document_uploads_dir) / resolved_category
        upload_dir.mkdir(parents=True, exist_ok=True)

        document_id = f"UPL-{uuid.uuid4().hex[:12].upper()}"
        safe_name = f"{document_id}_{original_name}"
        file_path = upload_dir / safe_name

        with file_path.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)

        processing = self.processing_service.process_document(
            file_path=str(file_path.resolve()),
            file_name=original_name,
            document_type=resolved_type,
            document_category=resolved_category,
        )
        indexed_chunks = self.semantic_service.build_document_index(
            {
                "document_id": document_id,
                "document_type": resolved_type,
                "document_category": resolved_category,
                "file_name": original_name,
                "file_path": str(file_path.resolve()),
                "source_metadata_file": f"uploaded:{original_name}",
                "related_vendor_id": related_vendor_id or None,
                "related_employee_id": related_employee_id or None,
                "related_transaction_id": related_transaction_id or None,
                "related_contract_id": related_contract_id or None,
                "related_investigation_id": related_investigation_id or None,
                "creation_date": date.today().isoformat(),
            }
        )
        processing_artifact = {
            **processing,
            "indexed_chunk_count": len(indexed_chunks),
            "index_status": "indexed" if indexed_chunks else "stored_only",
            "chunks": indexed_chunks,
        }
        processing_response = {
            **processing,
            "indexed_chunk_count": len(indexed_chunks),
            "index_status": "indexed" if indexed_chunks else "stored_only",
        }
        self._write_processing_artifact(
            file_path=file_path,
            document_id=document_id,
            file_name=original_name,
            document_type=resolved_type,
            document_category=resolved_category,
            processing=processing_artifact,
        )

        document = document_metadata_crud.create_document_metadata(
            self.db,
            document_id=document_id,
            document_type=resolved_type,
            document_category=resolved_category,
            creation_date=date.today(),
            file_name=original_name,
            file_path=str(file_path.resolve()),
            source_metadata_file=f"uploaded:{original_name}",
            related_vendor_id=related_vendor_id or None,
            related_employee_id=related_employee_id or None,
            related_transaction_id=related_transaction_id or None,
            related_contract_id=related_contract_id or None,
            related_investigation_id=related_investigation_id or None,
        )
        self.db.commit()

        GovernanceAuditService(self.db).record_event(
            actor_user_id=user_id,
            actor_name=actor_name,
            action_type="document_uploaded",
            entity_type="document_metadata",
            entity_id=document.document_id,
            severity="info",
            summary=f"Document '{document.file_name}' was uploaded and registered.",
            after_state={
                **serialize_document_metadata(document),
                "processing": processing_response,
            },
        )
        self.db.commit()
        return {
            "success": True,
            "message": "Document uploaded successfully.",
            "document": serialize_document_metadata(document),
            "processing": processing_response,
        }

    def _slugify(self, value: str) -> str:
        return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_") or "document"

    def _write_processing_artifact(
        self,
        *,
        file_path: Path,
        document_id: str,
        file_name: str,
        document_type: str,
        document_category: str,
        processing: dict[str, Any],
    ) -> None:
        artifact_path = file_path.with_suffix(f"{file_path.suffix}.meta.json")
        artifact = {
            "document_id": document_id,
            "file_name": file_name,
            "document_type": document_type,
            "document_category": document_category,
            "processing": processing,
        }
        try:
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            return
