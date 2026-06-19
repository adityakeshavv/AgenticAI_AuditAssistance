-- Agentic AI-Powered Audit Assistant
-- Standalone PostgreSQL 17.5 DDL for the document_metadata bridge table.
--
-- Safe to run on the populated audit_assitance_db database.
-- Creates only:
--   - document_metadata table
--   - document_metadata indexes
--   - document_metadata trigger
--
-- Reuses the existing set_updated_at() function already present in the database.

BEGIN;

CREATE TABLE IF NOT EXISTS document_metadata (
    document_id VARCHAR(50) PRIMARY KEY,
    document_type VARCHAR(100) NOT NULL,
    document_category VARCHAR(100) NOT NULL,
    related_vendor_id VARCHAR(20),
    related_employee_id VARCHAR(30),
    related_transaction_id VARCHAR(50),
    related_contract_id VARCHAR(20),
    related_investigation_id VARCHAR(20),
    creation_date DATE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    source_metadata_file VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE document_metadata IS
    'Bridge table linking unstructured audit documents to structured audit entities using soft references only.';
COMMENT ON COLUMN document_metadata.related_vendor_id IS
    'Soft reference to vendor.vendor_id. Intentionally not enforced with a foreign key.';
COMMENT ON COLUMN document_metadata.related_employee_id IS
    'Soft reference to employee_master.employee_id. Intentionally not enforced with a foreign key.';
COMMENT ON COLUMN document_metadata.related_transaction_id IS
    'Soft reference to transaction_master.transaction_id. Intentionally not enforced with a foreign key.';
COMMENT ON COLUMN document_metadata.related_contract_id IS
    'Soft reference to contract.contract_id. Intentionally not enforced with a foreign key.';
COMMENT ON COLUMN document_metadata.related_investigation_id IS
    'Soft reference to audit_investigation.investigation_id. Intentionally not enforced with a foreign key.';
COMMENT ON COLUMN document_metadata.file_path IS
    'Resolved file-system path generated during ingestion from the configured rag/documents directory, category, and file name.';
COMMENT ON COLUMN document_metadata.source_metadata_file IS
    'Origin metadata CSV used to ingest this row.';

CREATE INDEX IF NOT EXISTS idx_document_metadata_document_id
    ON document_metadata (document_id);

CREATE INDEX IF NOT EXISTS idx_document_metadata_document_type
    ON document_metadata (document_type);

CREATE INDEX IF NOT EXISTS idx_document_metadata_document_category
    ON document_metadata (document_category);

CREATE INDEX IF NOT EXISTS idx_document_metadata_related_vendor_id
    ON document_metadata (related_vendor_id);

CREATE INDEX IF NOT EXISTS idx_document_metadata_related_employee_id
    ON document_metadata (related_employee_id);

CREATE INDEX IF NOT EXISTS idx_document_metadata_related_transaction_id
    ON document_metadata (related_transaction_id);

CREATE INDEX IF NOT EXISTS idx_document_metadata_related_contract_id
    ON document_metadata (related_contract_id);

CREATE INDEX IF NOT EXISTS idx_document_metadata_related_investigation_id
    ON document_metadata (related_investigation_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_document_metadata_set_updated_at'
          AND tgrelid = 'document_metadata'::regclass
    ) THEN
        CREATE TRIGGER trg_document_metadata_set_updated_at
            BEFORE UPDATE ON document_metadata
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END;
$$;

-- Verification queries
-- 1. Confirm table exists
-- SELECT to_regclass('public.document_metadata');
--
-- 2. Confirm row count after load
-- SELECT COUNT(*) FROM document_metadata;
--
-- 3. Confirm indexes exist
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'document_metadata'
-- ORDER BY indexname;
--
-- 4. Confirm trigger exists
-- SELECT tgname
-- FROM pg_trigger
-- WHERE tgrelid = 'document_metadata'::regclass
--   AND NOT tgisinternal;
--
-- 5. Confirm soft references and file paths
-- SELECT document_id, document_category, file_path, source_metadata_file
-- FROM document_metadata
-- ORDER BY document_id
-- LIMIT 20;

COMMIT;
