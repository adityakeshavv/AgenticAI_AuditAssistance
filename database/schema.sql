-- Agentic AI-Powered Audit Assistant
-- PostgreSQL 17.5 schema for the 11 finalized structured datasets plus the
-- document_metadata bridge table for unstructured audit documents.
--
-- Design notes:
-- 1. The finalized CSV datasets are the canonical source of truth.
-- 2. All database identifiers use lowercase snake_case.
-- 3. Dataset IDs are meaningful business identifiers, so primary keys use VARCHAR
--    instead of generated surrogate keys.
-- 4. evidence.source_table and evidence.source_record_id are intentional
--    polymorphic references and therefore do not have foreign key constraints.
-- 5. document_metadata stores only metadata and soft links to structured rows;
--    related_* columns intentionally do not enforce foreign keys.
-- 6. The department/employee circular relationship is resolved by creating
--    department_master first without its head_employee_id FK, then adding that FK
--    with ALTER TABLE after employee_master exists.
-- 7. employee_master.email is not UNIQUE because the accepted dataset contains
--    duplicate email values.

BEGIN;

CREATE TYPE vendor_type_enum AS ENUM (
    'CONSULTANT',
    'CONTRACTOR',
    'DISTRIBUTOR',
    'LOGISTICS',
    'MANUFACTURER',
    'SERVICE_PROVIDER',
    'SUPPLIER'
);

CREATE TYPE vendor_risk_rating_enum AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE vendor_status_enum AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'BLACKLISTED'
);

CREATE TYPE currency_code_enum AS ENUM (
    'AUD',
    'CAD',
    'EUR',
    'GBP',
    'INR',
    'SGD',
    'USD'
);

CREATE TYPE employee_status_enum AS ENUM (
    'ACTIVE'
);

CREATE TYPE contract_type_enum AS ENUM (
    'FIXED_PRICE',
    'FRAMEWORK',
    'MASTER_SERVICE',
    'PURCHASE_ORDER',
    'RETAINER',
    'SLA',
    'TIME_AND_MATERIAL'
);

CREATE TYPE contract_status_enum AS ENUM (
    'ACTIVE',
    'DRAFT',
    'EXPIRED',
    'SUSPENDED',
    'TERMINATED'
);

CREATE TYPE compliance_framework_enum AS ENUM (
    'CIS Controls',
    'CMMC',
    'GDPR',
    'HIPAA',
    'ISO 27001',
    'ISO 9001',
    'NIST CSF',
    'PCI-DSS',
    'SOC 2 Type II',
    'SOX'
);

CREATE TYPE compliance_status_enum AS ENUM (
    'COMPLIANT',
    'EXPIRED',
    'NON_COMPLIANT',
    'PENDING'
);

CREATE TYPE transaction_type_enum AS ENUM (
    'ADVANCE',
    'INVOICE',
    'PAYMENT',
    'PURCHASE',
    'REFUND',
    'REIMBURSEMENT',
    'SETTLEMENT',
    'TRANSFER'
);

CREATE TYPE transaction_status_enum AS ENUM (
    'COMPLETED',
    'FLAGGED',
    'PENDING',
    'REVERSED'
);

CREATE TYPE expense_category_enum AS ENUM (
    'Accommodation',
    'Consulting',
    'Entertainment',
    'Equipment',
    'Marketing',
    'Meals',
    'Office Supplies',
    'Software',
    'Training',
    'Travel'
);

CREATE TYPE expense_approval_status_enum AS ENUM (
    'APPROVED',
    'FLAGGED',
    'PENDING',
    'REJECTED'
);

CREATE TYPE workflow_approval_status_enum AS ENUM (
    'APPROVED',
    'ESCALATED',
    'REJECTED'
);

CREATE TYPE investigation_type_enum AS ENUM (
    'APPROVAL_LIMIT_REVIEW',
    'COMPLIANCE_REVIEW',
    'CONTRACT_AUDIT',
    'EXPENSE_AUDIT',
    'FINANCIAL_INVESTIGATION',
    'FRAUD_INVESTIGATION',
    'POLICY_BREACH_REVIEW',
    'VENDOR_RISK_ASSESSMENT'
);

CREATE TYPE investigation_status_enum AS ENUM (
    'COMPLETED',
    'IN_PROGRESS',
    'ON_HOLD',
    'OPEN'
);

CREATE TYPE finding_severity_enum AS ENUM (
    'CRITICAL',
    'HIGH',
    'LOW',
    'MEDIUM'
);

CREATE TYPE finding_category_enum AS ENUM (
    'APPROVAL_LIMIT',
    'EXPIRED_COMPLIANCE',
    'FRAUD_PATTERN',
    'MISSING_RECEIPT',
    'POLICY_BREACH',
    'VENDOR_RISK'
);

CREATE TYPE finding_status_enum AS ENUM (
    'ESCALATED',
    'FALSE_POSITIVE',
    'OPEN',
    'RESOLVED',
    'VALIDATED'
);

CREATE TYPE evidence_source_type_enum AS ENUM (
    'APPROVAL_RECORD',
    'AUDIT_REPORT',
    'COMPLIANCE_RECORD',
    'CONTRACT_RECORD',
    'DNS_LOG',
    'EXPENSE_CLAIM',
    'HR_RECORD',
    'POLICY_DOCUMENT',
    'TRANSACTION_RECORD',
    'VENDOR_RECORD'
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TABLE department_master (
    department_id VARCHAR(20) PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL,
    cost_center VARCHAR(20) NOT NULL,
    head_employee_id VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_department_master_cost_center UNIQUE (cost_center)
);

CREATE TABLE employee_master (
    employee_id VARCHAR(30) PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    department_id VARCHAR(20) NOT NULL,
    manager_id VARCHAR(30),
    designation VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    location VARCHAR(100) NOT NULL,
    joining_date DATE NOT NULL,
    employment_status employee_status_enum NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_employee_master_email_format
        CHECK (position('@' IN email) > 1),
    CONSTRAINT fk_employee_master_department
        FOREIGN KEY (department_id)
        REFERENCES department_master (department_id)
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_employee_master_manager
        FOREIGN KEY (manager_id)
        REFERENCES employee_master (employee_id)
        DEFERRABLE INITIALLY DEFERRED
);

ALTER TABLE department_master
    ADD CONSTRAINT fk_department_master_head_employee
    FOREIGN KEY (head_employee_id)
    REFERENCES employee_master (employee_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE vendor (
    vendor_id VARCHAR(20) PRIMARY KEY,
    vendor_name VARCHAR(200) NOT NULL,
    vendor_type vendor_type_enum NOT NULL,
    country VARCHAR(100) NOT NULL,
    registration_no VARCHAR(50) NOT NULL,
    risk_rating vendor_risk_rating_enum NOT NULL,
    onboarding_date DATE NOT NULL,
    status vendor_status_enum NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_vendor_registration_no UNIQUE (registration_no)
);

CREATE TABLE contract (
    contract_id VARCHAR(20) PRIMARY KEY,
    vendor_id VARCHAR(20) NOT NULL,
    contract_value NUMERIC(18,2) NOT NULL,
    currency currency_code_enum NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    contract_type contract_type_enum NOT NULL,
    status contract_status_enum NOT NULL,
    created_by_employee_id VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_contract_value_positive
        CHECK (contract_value > 0),
    CONSTRAINT chk_contract_date_order
        CHECK (end_date >= start_date),
    CONSTRAINT fk_contract_vendor
        FOREIGN KEY (vendor_id)
        REFERENCES vendor (vendor_id),
    CONSTRAINT fk_contract_created_by_employee
        FOREIGN KEY (created_by_employee_id)
        REFERENCES employee_master (employee_id)
);

CREATE TABLE compliance_record (
    compliance_id VARCHAR(20) PRIMARY KEY,
    vendor_id VARCHAR(20) NOT NULL,
    framework compliance_framework_enum NOT NULL,
    status compliance_status_enum NOT NULL,
    assessment_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    assessed_by VARCHAR(200) NOT NULL,
    findings_summary TEXT NOT NULL,
    document_ref VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_compliance_record_vendor
        FOREIGN KEY (vendor_id)
        REFERENCES vendor (vendor_id)
);

CREATE TABLE transaction_master (
    transaction_id VARCHAR(50) PRIMARY KEY,
    transaction_date DATE NOT NULL,
    vendor_id VARCHAR(20) NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    currency currency_code_enum NOT NULL,
    transaction_type transaction_type_enum NOT NULL,
    risk_score NUMERIC(5,3) NOT NULL,
    status transaction_status_enum NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_transaction_master_amount_positive
        CHECK (amount > 0),
    CONSTRAINT chk_transaction_master_risk_score_range
        CHECK (risk_score >= 0 AND risk_score <= 1),
    CONSTRAINT fk_transaction_master_vendor
        FOREIGN KEY (vendor_id)
        REFERENCES vendor (vendor_id)
);

CREATE TABLE expense_claim (
    claim_id VARCHAR(30) PRIMARY KEY,
    employee_id VARCHAR(30) NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    expense_category expense_category_enum NOT NULL,
    claim_date DATE NOT NULL,
    submission_date DATE NOT NULL,
    receipt_attached BOOLEAN NOT NULL,
    policy_id VARCHAR(20) NOT NULL,
    approval_status expense_approval_status_enum NOT NULL,
    approved_by VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_expense_claim_amount_positive
        CHECK (amount > 0),
    CONSTRAINT chk_expense_claim_submission_date_order
        CHECK (submission_date >= claim_date),
    CONSTRAINT fk_expense_claim_employee
        FOREIGN KEY (employee_id)
        REFERENCES employee_master (employee_id),
    CONSTRAINT fk_expense_claim_approved_by
        FOREIGN KEY (approved_by)
        REFERENCES employee_master (employee_id)
);

CREATE TABLE approval_workflow (
    approval_id VARCHAR(20) PRIMARY KEY,
    transaction_id VARCHAR(50) NOT NULL,
    transaction_amount NUMERIC(18,2) NOT NULL,
    approver_employee_id VARCHAR(30) NOT NULL,
    approval_level INTEGER NOT NULL,
    approval_limit NUMERIC(18,2) NOT NULL,
    approval_status workflow_approval_status_enum NOT NULL,
    approval_date DATE NOT NULL,
    rejection_reason TEXT,
    delegation_ref VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_approval_workflow_transaction_amount_positive
        CHECK (transaction_amount > 0),
    CONSTRAINT chk_approval_workflow_approval_limit_positive
        CHECK (approval_limit > 0),
    CONSTRAINT chk_approval_workflow_level_range
        CHECK (approval_level BETWEEN 1 AND 5),
    CONSTRAINT chk_approval_workflow_rejection_reason
        CHECK (
            (approval_status = 'REJECTED' AND rejection_reason IS NOT NULL)
            OR (approval_status <> 'REJECTED' AND rejection_reason IS NULL)
        ),
    CONSTRAINT chk_approval_workflow_delegation_ref
        CHECK (
            (approval_status = 'ESCALATED' AND delegation_ref IS NOT NULL)
            OR (approval_status <> 'ESCALATED' AND delegation_ref IS NULL)
        ),
    CONSTRAINT fk_approval_workflow_transaction
        FOREIGN KEY (transaction_id)
        REFERENCES transaction_master (transaction_id),
    CONSTRAINT fk_approval_workflow_approver_employee
        FOREIGN KEY (approver_employee_id)
        REFERENCES employee_master (employee_id)
);

CREATE TABLE audit_investigation (
    investigation_id VARCHAR(20) PRIMARY KEY,
    audit_question TEXT NOT NULL,
    investigation_type investigation_type_enum NOT NULL,
    status investigation_status_enum NOT NULL,
    created_date DATE NOT NULL,
    completed_date DATE,
    scope_period_start DATE NOT NULL,
    scope_period_end DATE NOT NULL,
    created_by_employee_id VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_audit_investigation_scope_date_order
        CHECK (scope_period_end >= scope_period_start),
    CONSTRAINT chk_audit_investigation_completion_date_order
        CHECK (completed_date IS NULL OR completed_date >= created_date),
    CONSTRAINT fk_audit_investigation_created_by_employee
        FOREIGN KEY (created_by_employee_id)
        REFERENCES employee_master (employee_id)
);

CREATE TABLE audit_finding (
    finding_id VARCHAR(20) PRIMARY KEY,
    investigation_id VARCHAR(20) NOT NULL,
    severity finding_severity_enum NOT NULL,
    category finding_category_enum NOT NULL,
    description TEXT NOT NULL,
    confidence_score NUMERIC(5,3) NOT NULL,
    status finding_status_enum NOT NULL,
    created_at DATE NOT NULL,
    validated_at DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_audit_finding_confidence_score_range
        CHECK (confidence_score >= 0 AND confidence_score <= 1),
    CONSTRAINT chk_audit_finding_validation_date_order
        CHECK (validated_at IS NULL OR validated_at >= created_at),
    CONSTRAINT fk_audit_finding_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES audit_investigation (investigation_id)
);

COMMENT ON COLUMN audit_finding.created_at IS
    'Dataset finding creation date from the canonical CSV.';
COMMENT ON COLUMN audit_finding.updated_at IS
    'Database row update timestamp. audit_finding.created_at is retained as the canonical finding creation date.';

CREATE TABLE evidence (
    evidence_id VARCHAR(30) PRIMARY KEY,
    finding_id VARCHAR(20) NOT NULL,
    source_type evidence_source_type_enum NOT NULL,
    source_table VARCHAR(100) NOT NULL,
    source_record_id VARCHAR(100) NOT NULL,
    evidence_text TEXT NOT NULL,
    alignment_score NUMERIC(5,3) NOT NULL,
    citation_reference VARCHAR(50) NOT NULL,
    retrieved_at DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_evidence_alignment_score_range
        CHECK (alignment_score >= 0 AND alignment_score <= 1),
    CONSTRAINT fk_evidence_finding
        FOREIGN KEY (finding_id)
        REFERENCES audit_finding (finding_id)
);

COMMENT ON COLUMN evidence.source_table IS
    'Polymorphic source table reference. This is intentionally not enforced with a foreign key.';
COMMENT ON COLUMN evidence.source_record_id IS
    'Polymorphic source record identifier. This is intentionally not enforced with a foreign key.';

CREATE TABLE document_metadata (
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
    'Bridge table linking unstructured document assets to structured audit entities using soft references only.';
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

CREATE INDEX idx_employee_master_department_id
    ON employee_master (department_id);
CREATE INDEX idx_employee_master_manager_id
    ON employee_master (manager_id);
CREATE INDEX idx_department_master_head_employee_id
    ON department_master (head_employee_id);

CREATE INDEX idx_contract_vendor_id
    ON contract (vendor_id);
CREATE INDEX idx_contract_created_by_employee_id
    ON contract (created_by_employee_id);

CREATE INDEX idx_compliance_record_vendor_id
    ON compliance_record (vendor_id);

CREATE INDEX idx_transaction_master_vendor_id
    ON transaction_master (vendor_id);

CREATE INDEX idx_expense_claim_employee_id
    ON expense_claim (employee_id);
CREATE INDEX idx_expense_claim_approved_by
    ON expense_claim (approved_by);

CREATE INDEX idx_approval_workflow_transaction_id
    ON approval_workflow (transaction_id);
CREATE INDEX idx_approval_workflow_approver_employee_id
    ON approval_workflow (approver_employee_id);

CREATE INDEX idx_audit_investigation_created_by_employee_id
    ON audit_investigation (created_by_employee_id);

CREATE INDEX idx_audit_finding_investigation_id
    ON audit_finding (investigation_id);

CREATE INDEX idx_evidence_finding_id
    ON evidence (finding_id);

CREATE INDEX idx_document_metadata_document_id
    ON document_metadata (document_id);
CREATE INDEX idx_document_metadata_document_type
    ON document_metadata (document_type);
CREATE INDEX idx_document_metadata_document_category
    ON document_metadata (document_category);
CREATE INDEX idx_document_metadata_related_vendor_id
    ON document_metadata (related_vendor_id);
CREATE INDEX idx_document_metadata_related_employee_id
    ON document_metadata (related_employee_id);
CREATE INDEX idx_document_metadata_related_transaction_id
    ON document_metadata (related_transaction_id);
CREATE INDEX idx_document_metadata_related_contract_id
    ON document_metadata (related_contract_id);
CREATE INDEX idx_document_metadata_related_investigation_id
    ON document_metadata (related_investigation_id);

CREATE INDEX idx_vendor_risk_status
    ON vendor (risk_rating, status);
CREATE INDEX idx_contract_vendor_status_end_date
    ON contract (vendor_id, status, end_date);
CREATE INDEX idx_compliance_record_vendor_status_expiry
    ON compliance_record (vendor_id, status, expiry_date);
CREATE INDEX idx_transaction_master_vendor_date_risk_status
    ON transaction_master (vendor_id, transaction_date, risk_score, status);
CREATE INDEX idx_expense_claim_employee_status_claim_date
    ON expense_claim (employee_id, approval_status, claim_date);
CREATE INDEX idx_approval_workflow_transaction_status_approver
    ON approval_workflow (transaction_id, approval_status, approver_employee_id);
CREATE INDEX idx_audit_finding_investigation_severity_status_category
    ON audit_finding (investigation_id, severity, status, category);
CREATE INDEX idx_evidence_finding_source
    ON evidence (finding_id, source_type, source_table);

CREATE INDEX idx_audit_investigation_question_fts
    ON audit_investigation
    USING GIN (to_tsvector('english', audit_question));
CREATE INDEX idx_audit_finding_description_fts
    ON audit_finding
    USING GIN (to_tsvector('english', description));
CREATE INDEX idx_evidence_text_fts
    ON evidence
    USING GIN (to_tsvector('english', evidence_text));

CREATE TRIGGER trg_department_master_set_updated_at
    BEFORE UPDATE ON department_master
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_employee_master_set_updated_at
    BEFORE UPDATE ON employee_master
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_vendor_set_updated_at
    BEFORE UPDATE ON vendor
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_contract_set_updated_at
    BEFORE UPDATE ON contract
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_compliance_record_set_updated_at
    BEFORE UPDATE ON compliance_record
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_transaction_master_set_updated_at
    BEFORE UPDATE ON transaction_master
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_expense_claim_set_updated_at
    BEFORE UPDATE ON expense_claim
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_approval_workflow_set_updated_at
    BEFORE UPDATE ON approval_workflow
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_audit_investigation_set_updated_at
    BEFORE UPDATE ON audit_investigation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_audit_finding_set_updated_at
    BEFORE UPDATE ON audit_finding
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_evidence_set_updated_at
    BEFORE UPDATE ON evidence
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_document_metadata_set_updated_at
    BEFORE UPDATE ON document_metadata
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
