from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import SessionLocal
from app.models import DocumentMetadata


CATEGORY_FOLDER_MAP = {
    "audit_reports": "03_audit_reports",
    "contracts": "02_contracts",
    "emails": "05_emails",
    "investigation_reports": "04_investigation_reports",
    "meeting_minutes": "07_meeting_minutes",
    "policies": "01_policies",
    "sop_documents": "06_sop_documents",
}

FILE_PREFIX_CATEGORY_MAP = {
    "AR-": "audit_reports",
    "CON-": "contracts",
    "EML-": "emails",
    "INV-": "investigation_reports",
    "MIN-": "meeting_minutes",
    "POL-": "policies",
    "SOP-": "sop_documents",
}

DOCUMENT_TYPE_CATEGORY_MAP = {
    "AUDIT_REPORT": "audit_reports",
    "CONTRACT": "contracts",
    "INVESTIGATION_REPORT": "investigation_reports",
    "MEETING_MINUTES": "meeting_minutes",
    "POLICY": "policies",
    "SOP": "sop_documents",
}

REQUIRED_COLUMNS = {
    "document_id",
    "document_type",
    "creation_date",
    "file_name",
}


@dataclass
class MetadataLoadReport:
    source_files: int = 0
    source_rows: int = 0
    unique_rows: int = 0
    loadable_rows: int = 0
    upserted_rows: int = 0
    duplicate_document_ids: list[str] = field(default_factory=list)
    malformed_rows: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    invalid_categories: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_files": self.source_files,
            "source_rows": self.source_rows,
            "unique_rows": self.unique_rows,
            "loadable_rows": self.loadable_rows,
            "upserted_rows": self.upserted_rows,
            "duplicate_document_ids": self.duplicate_document_ids,
            "malformed_rows": self.malformed_rows,
            "missing_files": self.missing_files,
            "invalid_categories": self.invalid_categories,
        }


def discover_metadata_files(metadata_dir: Path) -> list[Path]:
    files = sorted(metadata_dir.glob("metadata*.csv"), key=lambda path: (path.name != "metadata.csv", path.name))
    return [path for path in files if path.is_file()]


def normalize_slug(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def infer_document_category(row: dict[str, str], source_file: Path) -> str | None:
    explicit_category = normalize_slug(row.get("document_category"))
    if explicit_category in CATEGORY_FOLDER_MAP:
        return explicit_category

    source_stem = source_file.stem.lower()
    if source_stem.startswith("metadata_"):
        candidate = normalize_slug(source_stem.removeprefix("metadata_"))
        if candidate in CATEGORY_FOLDER_MAP:
            return candidate

    document_type = normalize_slug(row.get("document_type")).upper()
    if document_type in DOCUMENT_TYPE_CATEGORY_MAP:
        return DOCUMENT_TYPE_CATEGORY_MAP[document_type]

    file_name = (row.get("file_name") or "").strip().upper()
    for prefix, category in FILE_PREFIX_CATEGORY_MAP.items():
        if file_name.startswith(prefix):
            return category

    return None


def resolve_file_path(documents_dir: Path, category: str, file_name: str) -> str | None:
    folder_name = CATEGORY_FOLDER_MAP.get(category)
    if not folder_name:
        return None
    return str((documents_dir / folder_name / file_name).resolve())


def _clean_row(row: dict[str, str]) -> dict[str, str]:
    return {key.strip(): (value.strip() if isinstance(value, str) else value) for key, value in row.items()}


def normalize_row(row: dict[str, str], source_file: Path, documents_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    cleaned = _clean_row(row)

    missing_required = [column for column in REQUIRED_COLUMNS if not cleaned.get(column)]
    if missing_required:
        return None, f"{source_file.name}: missing required columns {', '.join(sorted(missing_required))}"

    category = infer_document_category(cleaned, source_file)
    if not category:
        return None, f"{source_file.name}: unable to infer document_category for {cleaned.get('document_id')}"

    file_path = resolve_file_path(documents_dir, category, cleaned["file_name"])
    if not file_path:
        return None, f"{source_file.name}: unable to resolve file path for {cleaned.get('document_id')}"

    try:
        creation_date = date.fromisoformat(cleaned["creation_date"])
    except ValueError:
        return None, f"{source_file.name}: invalid creation_date for {cleaned.get('document_id')}"

    normalized = {
        "document_id": cleaned["document_id"],
        "document_type": cleaned["document_type"],
        "document_category": category,
        "related_vendor_id": cleaned.get("related_vendor_id") or None,
        "related_employee_id": cleaned.get("related_employee_id") or None,
        "related_transaction_id": cleaned.get("related_transaction_id") or None,
        "related_contract_id": cleaned.get("related_contract_id") or None,
        "related_investigation_id": cleaned.get("related_investigation_id") or None,
        "creation_date": creation_date,
        "file_name": cleaned["file_name"],
        "file_path": file_path,
        "source_metadata_file": source_file.name,
    }
    return normalized, None


def collect_metadata_rows(settings=None) -> tuple[list[dict[str, Any]], MetadataLoadReport]:
    settings = settings or get_settings()
    metadata_dir = Path(settings.rag_metadata_dir)
    documents_dir = Path(settings.rag_documents_dir)

    report = MetadataLoadReport()
    selected_files = discover_metadata_files(metadata_dir)
    report.source_files = len(selected_files)

    deduped: dict[str, dict[str, Any]] = {}
    seen_duplicates: set[str] = set()

    for source_file in selected_files:
        with source_file.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw_row in reader:
                report.source_rows += 1
                normalized, error = normalize_row(raw_row, source_file, documents_dir)
                if error:
                    report.malformed_rows.append(error)
                    continue

                document_id = normalized["document_id"]
                if document_id in deduped:
                    if document_id not in seen_duplicates:
                        report.duplicate_document_ids.append(document_id)
                        seen_duplicates.add(document_id)
                    continue

                if not Path(normalized["file_path"]).exists():
                    report.missing_files.append(document_id)
                    continue

                deduped[document_id] = normalized

    report.unique_rows = len(deduped)
    report.loadable_rows = len(deduped)
    return list(deduped.values()), report


def upsert_metadata_rows(db: Session, rows: list[dict[str, Any]], batch_size: int = 500) -> int:
    if not rows:
        return 0

    upserted = 0
    insert_stmt = pg_insert(DocumentMetadata)
    update_columns = {
        column.name: getattr(insert_stmt.excluded, column.name)
        for column in DocumentMetadata.__table__.columns
        if column.name not in {"document_id", "created_at", "updated_at"}
    }

    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        stmt = insert_stmt.values(batch).on_conflict_do_update(
            index_elements=[DocumentMetadata.document_id],
            set_=update_columns,
        )
        db.execute(stmt)
        upserted += len(batch)

    return upserted


def load_document_metadata(batch_size: int = 500) -> dict[str, Any]:
    settings = get_settings()
    rows, report = collect_metadata_rows(settings)

    with SessionLocal() as db:
        with db.begin():
            report.upserted_rows = upsert_metadata_rows(db, rows, batch_size=batch_size)

    with SessionLocal() as db:
        report_db_count = db.query(DocumentMetadata).count()

    result = report.as_dict()
    result["database_row_count"] = report_db_count
    return result


def print_report(report: dict[str, Any]) -> None:
    print("DOCUMENT METADATA LOAD REPORT")
    print(f"source_files: {report['source_files']}")
    print(f"source_rows: {report['source_rows']}")
    print(f"unique_rows: {report['unique_rows']}")
    print(f"loadable_rows: {report['loadable_rows']}")
    print(f"upserted_rows: {report['upserted_rows']}")
    print(f"database_row_count: {report['database_row_count']}")
    print(f"duplicate_document_ids: {len(report['duplicate_document_ids'])}")
    print(f"malformed_rows: {len(report['malformed_rows'])}")
    print(f"missing_files: {len(report['missing_files'])}")
    print(f"invalid_categories: {len(report['invalid_categories'])}")

    if report["duplicate_document_ids"]:
        print("duplicate ids:", ", ".join(report["duplicate_document_ids"][:10]))
    if report["malformed_rows"]:
        print("malformed samples:", "; ".join(report["malformed_rows"][:5]))
    if report["missing_files"]:
        print("missing file document ids:", ", ".join(report["missing_files"][:10]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Load document metadata into PostgreSQL.")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    report = load_document_metadata(batch_size=args.batch_size)
    print_report(report)


if __name__ == "__main__":
    main()
