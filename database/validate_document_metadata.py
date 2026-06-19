from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models import DocumentMetadata

from load_document_metadata import collect_metadata_rows


def validate_document_metadata() -> dict[str, Any]:
    rows, report = collect_metadata_rows()

    with SessionLocal() as db:
        database_row_count = db.query(DocumentMetadata).count()

    return {
        "source_files": report.source_files,
        "source_rows": report.source_rows,
        "unique_rows": report.unique_rows,
        "loadable_rows": len(rows),
        "database_row_count": database_row_count,
        "duplicate_document_ids": report.duplicate_document_ids,
        "malformed_rows": report.malformed_rows,
        "missing_files": report.missing_files,
    }


def print_report(report: dict[str, Any]) -> None:
    print("DOCUMENT METADATA VALIDATION REPORT")
    print(f"source_files: {report['source_files']}")
    print(f"source_rows: {report['source_rows']}")
    print(f"unique_rows: {report['unique_rows']}")
    print(f"loadable_rows: {report['loadable_rows']}")
    print(f"database_row_count: {report['database_row_count']}")
    print(f"duplicate_document_ids: {len(report['duplicate_document_ids'])}")
    print(f"malformed_rows: {len(report['malformed_rows'])}")
    print(f"missing_files: {len(report['missing_files'])}")

    if report["duplicate_document_ids"]:
        print("duplicate ids:", ", ".join(report["duplicate_document_ids"][:10]))
    if report["malformed_rows"]:
        print("malformed samples:", "; ".join(report["malformed_rows"][:5]))
    if report["missing_files"]:
        print("missing file document ids:", ", ".join(report["missing_files"][:10]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate document metadata loaded into PostgreSQL.")
    parser.parse_args()
    print_report(validate_document_metadata())


if __name__ == "__main__":
    main()
