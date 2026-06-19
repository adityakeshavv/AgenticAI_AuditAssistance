# Document Metadata Bridge

This project now includes a PostgreSQL-backed bridge for unstructured audit documents.
Only metadata is stored in the database. The actual PDFs, DOCX files, emails, and
reports remain in the `rag/documents` repository.

## Table Design

`document_metadata` stores:

- `document_id`
- `document_type`
- `document_category`
- soft references to structured audit records
- `creation_date`
- `file_name`
- `file_path`
- `source_metadata_file`
- `created_at`
- `updated_at`

Soft references are intentionally not enforced with foreign keys. This follows the
same pattern used by `evidence.source_table` and `evidence.source_record_id`.

## Ingestion Flow

1. Read every CSV under `rag/metadata`.
2. Normalize columns into a single document metadata shape.
3. Infer `document_category` when it is not present in the source CSV.
4. Generate `file_path` from the configured `rag/documents` directory, category,
   and file name.
5. Validate file existence and record shape.
6. Upsert records into PostgreSQL safely so reruns do not create duplicates.

## Database Bridge

The table is meant to connect structured audit data with unstructured sources:

- transactions
- vendors
- employees
- contracts
- investigations

It prepares the project for future document lookup, hybrid retrieval, and a
Document Agent without storing the raw documents in PostgreSQL.

## Utilities

- `database/load_document_metadata.py` loads the metadata into PostgreSQL.
- `database/validate_document_metadata.py` summarizes duplicates, missing files,
  malformed rows, and database counts.
- `backend/app/services/document_metadata_service.py` provides retrieval helpers
  for future API or agent use.
