-- Agentic AI-Powered Audit Assistant
-- PostgreSQL 17.5 data load script for the 11 finalized canonical CSVs.
--
-- Usage:
--   psql -d <database_name> -f database/load_data.sql
--
-- Notes:
-- - This script uses server-side COPY commands.
-- - PostgreSQL server-side COPY resolves paths on the database server, not from
--   psql's current working directory. The paths below are absolute for this
--   workspace; change them if the project is moved.
-- - The load is wrapped in one transaction and psql stops on the first error.
-- - The department/employee circular FK is handled by deferred constraints.

\set ON_ERROR_STOP on

-- CSV file locations. The finalized CSVs currently live under datasets/synthetic.
\set department_master_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Department_Master.csv'
\set employee_master_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Employee_Master.csv'
\set vendor_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Vendor.csv'
\set contract_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Contract.csv'
\set compliance_record_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Compliance_Record.csv'
\set transaction_master_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Transaction_Master.csv'
\set expense_claim_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Expense_Claim.csv'
\set approval_workflow_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Approval_Workflow.csv'
\set audit_investigation_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Audit_Investigation.csv'
\set audit_finding_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Audit_Finding.csv'
\set evidence_csv 'C:/Users/KIIT0001/Desktop/AuditAssistance/datasets/synthetic/Evidence.csv'

BEGIN;

SET CONSTRAINTS ALL DEFERRED;

-- =========================================================
-- 1. ORGANISATIONAL LAYER
-- =========================================================

-- Loaded before employees; head_employee_id FK is deferred until commit.
COPY department_master (
    department_id,
    department_name,
    cost_center,
    head_employee_id
)
FROM :'department_master_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

COPY employee_master (
    employee_id,
    employee_name,
    department_id,
    manager_id,
    designation,
    email,
    location,
    joining_date,
    employment_status
)
FROM :'employee_master_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

-- =========================================================
-- 2. VENDOR AND OPERATIONAL MASTER DATA
-- =========================================================

COPY vendor (
    vendor_id,
    vendor_name,
    vendor_type,
    country,
    registration_no,
    risk_rating,
    onboarding_date,
    status
)
FROM :'vendor_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

COPY contract (
    contract_id,
    vendor_id,
    contract_value,
    currency,
    start_date,
    end_date,
    contract_type,
    status,
    created_by_employee_id
)
FROM :'contract_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

COPY compliance_record (
    compliance_id,
    vendor_id,
    framework,
    status,
    assessment_date,
    expiry_date,
    assessed_by,
    findings_summary,
    document_ref
)
FROM :'compliance_record_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

COPY transaction_master (
    transaction_id,
    transaction_date,
    vendor_id,
    amount,
    currency,
    transaction_type,
    risk_score,
    status
)
FROM :'transaction_master_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

-- =========================================================
-- 3. EXPENSE AND APPROVAL WORKFLOWS
-- =========================================================

COPY expense_claim (
    claim_id,
    employee_id,
    amount,
    expense_category,
    claim_date,
    submission_date,
    receipt_attached,
    policy_id,
    approval_status,
    approved_by
)
FROM :'expense_claim_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

COPY approval_workflow (
    approval_id,
    transaction_id,
    transaction_amount,
    approver_employee_id,
    approval_level,
    approval_limit,
    approval_status,
    approval_date,
    rejection_reason,
    delegation_ref
)
FROM :'approval_workflow_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

-- =========================================================
-- 4. AUDIT LAYER
-- =========================================================

COPY audit_investigation (
    investigation_id,
    audit_question,
    investigation_type,
    status,
    created_date,
    completed_date,
    scope_period_start,
    scope_period_end,
    created_by_employee_id
)
FROM :'audit_investigation_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

COPY audit_finding (
    finding_id,
    investigation_id,
    severity,
    category,
    description,
    confidence_score,
    status,
    created_at,
    validated_at
)
FROM :'audit_finding_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

COPY evidence (
    evidence_id,
    finding_id,
    source_type,
    source_table,
    source_record_id,
    evidence_text,
    alignment_score,
    citation_reference,
    retrieved_at
)
FROM :'evidence_csv'
WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'UTF8');

COMMIT;
