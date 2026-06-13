-- Agentic AI-Powered Audit Assistant
-- PostgreSQL 17.5 validation queries for the 11 finalized canonical tables.
--
-- Usage:
-- - Each SELECT statement is executable independently.
-- - Expected row counts are based on the finalized synthetic CSV datasets.
-- - evidence.source_table and evidence.source_record_id are intentionally
--   polymorphic; validation checks allowed source names but does not expect FK
--   enforcement to source records.

-- =========================================================
-- 1. ROW COUNT VALIDATION
-- =========================================================

SELECT
    expected.table_name,
    expected.expected_rows,
    actual.actual_rows,
    CASE
        WHEN actual.actual_rows = expected.expected_rows THEN 'PASS'
        ELSE 'FAIL'
    END AS status
FROM (
    VALUES
        ('department_master', 12),
        ('employee_master', 61761),
        ('vendor', 5000),
        ('contract', 10000),
        ('compliance_record', 15000),
        ('transaction_master', 36710),
        ('expense_claim', 20806),
        ('approval_workflow', 50000),
        ('audit_investigation', 500),
        ('audit_finding', 5000),
        ('evidence', 20000)
) AS expected(table_name, expected_rows)
JOIN LATERAL (
    SELECT CASE expected.table_name
        WHEN 'department_master' THEN (SELECT count(*) FROM department_master)
        WHEN 'employee_master' THEN (SELECT count(*) FROM employee_master)
        WHEN 'vendor' THEN (SELECT count(*) FROM vendor)
        WHEN 'contract' THEN (SELECT count(*) FROM contract)
        WHEN 'compliance_record' THEN (SELECT count(*) FROM compliance_record)
        WHEN 'transaction_master' THEN (SELECT count(*) FROM transaction_master)
        WHEN 'expense_claim' THEN (SELECT count(*) FROM expense_claim)
        WHEN 'approval_workflow' THEN (SELECT count(*) FROM approval_workflow)
        WHEN 'audit_investigation' THEN (SELECT count(*) FROM audit_investigation)
        WHEN 'audit_finding' THEN (SELECT count(*) FROM audit_finding)
        WHEN 'evidence' THEN (SELECT count(*) FROM evidence)
    END AS actual_rows
) AS actual ON true
ORDER BY expected.table_name;

-- =========================================================
-- 2. PRIMARY KEY AND DUPLICATE DETECTION
-- =========================================================

SELECT 'department_master.department_id' AS check_name, department_id AS duplicate_value, count(*) AS duplicate_count
FROM department_master
GROUP BY department_id
HAVING count(*) > 1;

SELECT 'employee_master.employee_id' AS check_name, employee_id AS duplicate_value, count(*) AS duplicate_count
FROM employee_master
GROUP BY employee_id
HAVING count(*) > 1;

SELECT 'vendor.vendor_id' AS check_name, vendor_id AS duplicate_value, count(*) AS duplicate_count
FROM vendor
GROUP BY vendor_id
HAVING count(*) > 1;

SELECT 'contract.contract_id' AS check_name, contract_id AS duplicate_value, count(*) AS duplicate_count
FROM contract
GROUP BY contract_id
HAVING count(*) > 1;

SELECT 'compliance_record.compliance_id' AS check_name, compliance_id AS duplicate_value, count(*) AS duplicate_count
FROM compliance_record
GROUP BY compliance_id
HAVING count(*) > 1;

SELECT 'transaction_master.transaction_id' AS check_name, transaction_id AS duplicate_value, count(*) AS duplicate_count
FROM transaction_master
GROUP BY transaction_id
HAVING count(*) > 1;

SELECT 'expense_claim.claim_id' AS check_name, claim_id AS duplicate_value, count(*) AS duplicate_count
FROM expense_claim
GROUP BY claim_id
HAVING count(*) > 1;

SELECT 'approval_workflow.approval_id' AS check_name, approval_id AS duplicate_value, count(*) AS duplicate_count
FROM approval_workflow
GROUP BY approval_id
HAVING count(*) > 1;

SELECT 'audit_investigation.investigation_id' AS check_name, investigation_id AS duplicate_value, count(*) AS duplicate_count
FROM audit_investigation
GROUP BY investigation_id
HAVING count(*) > 1;

SELECT 'audit_finding.finding_id' AS check_name, finding_id AS duplicate_value, count(*) AS duplicate_count
FROM audit_finding
GROUP BY finding_id
HAVING count(*) > 1;

SELECT 'evidence.evidence_id' AS check_name, evidence_id AS duplicate_value, count(*) AS duplicate_count
FROM evidence
GROUP BY evidence_id
HAVING count(*) > 1;

-- Business-key duplicate checks.

SELECT 'department_master.cost_center' AS check_name, cost_center AS duplicate_value, count(*) AS duplicate_count
FROM department_master
GROUP BY cost_center
HAVING count(*) > 1;

SELECT 'vendor.registration_no' AS check_name, registration_no AS duplicate_value, count(*) AS duplicate_count
FROM vendor
GROUP BY registration_no
HAVING count(*) > 1;

SELECT 'employee_master.email informational duplicate check' AS check_name, email AS duplicate_value, count(*) AS duplicate_count
FROM employee_master
GROUP BY email
HAVING count(*) > 1
ORDER BY duplicate_count DESC, duplicate_value;

-- =========================================================
-- 3. NULL CHECKS
-- =========================================================

SELECT *
FROM (
    SELECT 'department_master.department_id' AS column_name, count(*) FILTER (WHERE department_id IS NULL) AS null_count FROM department_master
    UNION ALL SELECT 'department_master.department_name', count(*) FILTER (WHERE department_name IS NULL) FROM department_master
    UNION ALL SELECT 'department_master.cost_center', count(*) FILTER (WHERE cost_center IS NULL) FROM department_master
    UNION ALL SELECT 'department_master.head_employee_id', count(*) FILTER (WHERE head_employee_id IS NULL) FROM department_master
    UNION ALL SELECT 'employee_master.employee_id', count(*) FILTER (WHERE employee_id IS NULL) FROM employee_master
    UNION ALL SELECT 'employee_master.employee_name', count(*) FILTER (WHERE employee_name IS NULL) FROM employee_master
    UNION ALL SELECT 'employee_master.department_id', count(*) FILTER (WHERE department_id IS NULL) FROM employee_master
    UNION ALL SELECT 'employee_master.designation', count(*) FILTER (WHERE designation IS NULL) FROM employee_master
    UNION ALL SELECT 'employee_master.email', count(*) FILTER (WHERE email IS NULL) FROM employee_master
    UNION ALL SELECT 'employee_master.location', count(*) FILTER (WHERE location IS NULL) FROM employee_master
    UNION ALL SELECT 'employee_master.joining_date', count(*) FILTER (WHERE joining_date IS NULL) FROM employee_master
    UNION ALL SELECT 'employee_master.employment_status', count(*) FILTER (WHERE employment_status IS NULL) FROM employee_master
    UNION ALL SELECT 'vendor.vendor_id', count(*) FILTER (WHERE vendor_id IS NULL) FROM vendor
    UNION ALL SELECT 'vendor.vendor_name', count(*) FILTER (WHERE vendor_name IS NULL) FROM vendor
    UNION ALL SELECT 'vendor.vendor_type', count(*) FILTER (WHERE vendor_type IS NULL) FROM vendor
    UNION ALL SELECT 'vendor.country', count(*) FILTER (WHERE country IS NULL) FROM vendor
    UNION ALL SELECT 'vendor.registration_no', count(*) FILTER (WHERE registration_no IS NULL) FROM vendor
    UNION ALL SELECT 'vendor.risk_rating', count(*) FILTER (WHERE risk_rating IS NULL) FROM vendor
    UNION ALL SELECT 'vendor.onboarding_date', count(*) FILTER (WHERE onboarding_date IS NULL) FROM vendor
    UNION ALL SELECT 'vendor.status', count(*) FILTER (WHERE status IS NULL) FROM vendor
    UNION ALL SELECT 'contract.contract_id', count(*) FILTER (WHERE contract_id IS NULL) FROM contract
    UNION ALL SELECT 'contract.vendor_id', count(*) FILTER (WHERE vendor_id IS NULL) FROM contract
    UNION ALL SELECT 'contract.contract_value', count(*) FILTER (WHERE contract_value IS NULL) FROM contract
    UNION ALL SELECT 'contract.currency', count(*) FILTER (WHERE currency IS NULL) FROM contract
    UNION ALL SELECT 'contract.start_date', count(*) FILTER (WHERE start_date IS NULL) FROM contract
    UNION ALL SELECT 'contract.end_date', count(*) FILTER (WHERE end_date IS NULL) FROM contract
    UNION ALL SELECT 'contract.contract_type', count(*) FILTER (WHERE contract_type IS NULL) FROM contract
    UNION ALL SELECT 'contract.status', count(*) FILTER (WHERE status IS NULL) FROM contract
    UNION ALL SELECT 'contract.created_by_employee_id', count(*) FILTER (WHERE created_by_employee_id IS NULL) FROM contract
    UNION ALL SELECT 'compliance_record.compliance_id', count(*) FILTER (WHERE compliance_id IS NULL) FROM compliance_record
    UNION ALL SELECT 'compliance_record.vendor_id', count(*) FILTER (WHERE vendor_id IS NULL) FROM compliance_record
    UNION ALL SELECT 'compliance_record.framework', count(*) FILTER (WHERE framework IS NULL) FROM compliance_record
    UNION ALL SELECT 'compliance_record.status', count(*) FILTER (WHERE status IS NULL) FROM compliance_record
    UNION ALL SELECT 'compliance_record.assessment_date', count(*) FILTER (WHERE assessment_date IS NULL) FROM compliance_record
    UNION ALL SELECT 'compliance_record.expiry_date', count(*) FILTER (WHERE expiry_date IS NULL) FROM compliance_record
    UNION ALL SELECT 'compliance_record.assessed_by', count(*) FILTER (WHERE assessed_by IS NULL) FROM compliance_record
    UNION ALL SELECT 'compliance_record.findings_summary', count(*) FILTER (WHERE findings_summary IS NULL) FROM compliance_record
    UNION ALL SELECT 'compliance_record.document_ref', count(*) FILTER (WHERE document_ref IS NULL) FROM compliance_record
    UNION ALL SELECT 'transaction_master.transaction_id', count(*) FILTER (WHERE transaction_id IS NULL) FROM transaction_master
    UNION ALL SELECT 'transaction_master.transaction_date', count(*) FILTER (WHERE transaction_date IS NULL) FROM transaction_master
    UNION ALL SELECT 'transaction_master.vendor_id', count(*) FILTER (WHERE vendor_id IS NULL) FROM transaction_master
    UNION ALL SELECT 'transaction_master.amount', count(*) FILTER (WHERE amount IS NULL) FROM transaction_master
    UNION ALL SELECT 'transaction_master.currency', count(*) FILTER (WHERE currency IS NULL) FROM transaction_master
    UNION ALL SELECT 'transaction_master.transaction_type', count(*) FILTER (WHERE transaction_type IS NULL) FROM transaction_master
    UNION ALL SELECT 'transaction_master.risk_score', count(*) FILTER (WHERE risk_score IS NULL) FROM transaction_master
    UNION ALL SELECT 'transaction_master.status', count(*) FILTER (WHERE status IS NULL) FROM transaction_master
    UNION ALL SELECT 'expense_claim.claim_id', count(*) FILTER (WHERE claim_id IS NULL) FROM expense_claim
    UNION ALL SELECT 'expense_claim.employee_id', count(*) FILTER (WHERE employee_id IS NULL) FROM expense_claim
    UNION ALL SELECT 'expense_claim.amount', count(*) FILTER (WHERE amount IS NULL) FROM expense_claim
    UNION ALL SELECT 'expense_claim.expense_category', count(*) FILTER (WHERE expense_category IS NULL) FROM expense_claim
    UNION ALL SELECT 'expense_claim.claim_date', count(*) FILTER (WHERE claim_date IS NULL) FROM expense_claim
    UNION ALL SELECT 'expense_claim.submission_date', count(*) FILTER (WHERE submission_date IS NULL) FROM expense_claim
    UNION ALL SELECT 'expense_claim.receipt_attached', count(*) FILTER (WHERE receipt_attached IS NULL) FROM expense_claim
    UNION ALL SELECT 'expense_claim.policy_id', count(*) FILTER (WHERE policy_id IS NULL) FROM expense_claim
    UNION ALL SELECT 'expense_claim.approval_status', count(*) FILTER (WHERE approval_status IS NULL) FROM expense_claim
    UNION ALL SELECT 'approval_workflow.approval_id', count(*) FILTER (WHERE approval_id IS NULL) FROM approval_workflow
    UNION ALL SELECT 'approval_workflow.transaction_id', count(*) FILTER (WHERE transaction_id IS NULL) FROM approval_workflow
    UNION ALL SELECT 'approval_workflow.transaction_amount', count(*) FILTER (WHERE transaction_amount IS NULL) FROM approval_workflow
    UNION ALL SELECT 'approval_workflow.approver_employee_id', count(*) FILTER (WHERE approver_employee_id IS NULL) FROM approval_workflow
    UNION ALL SELECT 'approval_workflow.approval_level', count(*) FILTER (WHERE approval_level IS NULL) FROM approval_workflow
    UNION ALL SELECT 'approval_workflow.approval_limit', count(*) FILTER (WHERE approval_limit IS NULL) FROM approval_workflow
    UNION ALL SELECT 'approval_workflow.approval_status', count(*) FILTER (WHERE approval_status IS NULL) FROM approval_workflow
    UNION ALL SELECT 'approval_workflow.approval_date', count(*) FILTER (WHERE approval_date IS NULL) FROM approval_workflow
    UNION ALL SELECT 'audit_investigation.investigation_id', count(*) FILTER (WHERE investigation_id IS NULL) FROM audit_investigation
    UNION ALL SELECT 'audit_investigation.audit_question', count(*) FILTER (WHERE audit_question IS NULL) FROM audit_investigation
    UNION ALL SELECT 'audit_investigation.investigation_type', count(*) FILTER (WHERE investigation_type IS NULL) FROM audit_investigation
    UNION ALL SELECT 'audit_investigation.status', count(*) FILTER (WHERE status IS NULL) FROM audit_investigation
    UNION ALL SELECT 'audit_investigation.created_date', count(*) FILTER (WHERE created_date IS NULL) FROM audit_investigation
    UNION ALL SELECT 'audit_investigation.scope_period_start', count(*) FILTER (WHERE scope_period_start IS NULL) FROM audit_investigation
    UNION ALL SELECT 'audit_investigation.scope_period_end', count(*) FILTER (WHERE scope_period_end IS NULL) FROM audit_investigation
    UNION ALL SELECT 'audit_investigation.created_by_employee_id', count(*) FILTER (WHERE created_by_employee_id IS NULL) FROM audit_investigation
    UNION ALL SELECT 'audit_finding.finding_id', count(*) FILTER (WHERE finding_id IS NULL) FROM audit_finding
    UNION ALL SELECT 'audit_finding.investigation_id', count(*) FILTER (WHERE investigation_id IS NULL) FROM audit_finding
    UNION ALL SELECT 'audit_finding.severity', count(*) FILTER (WHERE severity IS NULL) FROM audit_finding
    UNION ALL SELECT 'audit_finding.category', count(*) FILTER (WHERE category IS NULL) FROM audit_finding
    UNION ALL SELECT 'audit_finding.description', count(*) FILTER (WHERE description IS NULL) FROM audit_finding
    UNION ALL SELECT 'audit_finding.confidence_score', count(*) FILTER (WHERE confidence_score IS NULL) FROM audit_finding
    UNION ALL SELECT 'audit_finding.status', count(*) FILTER (WHERE status IS NULL) FROM audit_finding
    UNION ALL SELECT 'audit_finding.created_at', count(*) FILTER (WHERE created_at IS NULL) FROM audit_finding
    UNION ALL SELECT 'evidence.evidence_id', count(*) FILTER (WHERE evidence_id IS NULL) FROM evidence
    UNION ALL SELECT 'evidence.finding_id', count(*) FILTER (WHERE finding_id IS NULL) FROM evidence
    UNION ALL SELECT 'evidence.source_type', count(*) FILTER (WHERE source_type IS NULL) FROM evidence
    UNION ALL SELECT 'evidence.source_table', count(*) FILTER (WHERE source_table IS NULL) FROM evidence
    UNION ALL SELECT 'evidence.source_record_id', count(*) FILTER (WHERE source_record_id IS NULL) FROM evidence
    UNION ALL SELECT 'evidence.evidence_text', count(*) FILTER (WHERE evidence_text IS NULL) FROM evidence
    UNION ALL SELECT 'evidence.alignment_score', count(*) FILTER (WHERE alignment_score IS NULL) FROM evidence
    UNION ALL SELECT 'evidence.citation_reference', count(*) FILTER (WHERE citation_reference IS NULL) FROM evidence
    UNION ALL SELECT 'evidence.retrieved_at', count(*) FILTER (WHERE retrieved_at IS NULL) FROM evidence
) AS null_checks
WHERE null_count > 0
ORDER BY column_name;

-- Nullable columns expected by design.

SELECT *
FROM (
    SELECT 'employee_master.manager_id' AS column_name, count(*) FILTER (WHERE manager_id IS NULL) AS null_count FROM employee_master
    UNION ALL SELECT 'expense_claim.approved_by', count(*) FILTER (WHERE approved_by IS NULL) FROM expense_claim
    UNION ALL SELECT 'approval_workflow.rejection_reason', count(*) FILTER (WHERE rejection_reason IS NULL) FROM approval_workflow
    UNION ALL SELECT 'approval_workflow.delegation_ref', count(*) FILTER (WHERE delegation_ref IS NULL) FROM approval_workflow
    UNION ALL SELECT 'audit_investigation.completed_date', count(*) FILTER (WHERE completed_date IS NULL) FROM audit_investigation
    UNION ALL SELECT 'audit_finding.validated_at', count(*) FILTER (WHERE validated_at IS NULL) FROM audit_finding
) AS nullable_column_profile
ORDER BY column_name;

-- =========================================================
-- 4. FK VALIDATION SUMMARY
-- =========================================================

SELECT *
FROM (
    SELECT 'employee_master.department_id -> department_master.department_id' AS fk_check, count(*) AS orphan_count
    FROM employee_master c
    LEFT JOIN department_master p ON p.department_id = c.department_id
    WHERE p.department_id IS NULL
    UNION ALL
    SELECT 'employee_master.manager_id -> employee_master.employee_id', count(*)
    FROM employee_master c
    LEFT JOIN employee_master p ON p.employee_id = c.manager_id
    WHERE c.manager_id IS NOT NULL AND p.employee_id IS NULL
    UNION ALL
    SELECT 'department_master.head_employee_id -> employee_master.employee_id', count(*)
    FROM department_master c
    LEFT JOIN employee_master p ON p.employee_id = c.head_employee_id
    WHERE p.employee_id IS NULL
    UNION ALL
    SELECT 'contract.vendor_id -> vendor.vendor_id', count(*)
    FROM contract c
    LEFT JOIN vendor p ON p.vendor_id = c.vendor_id
    WHERE p.vendor_id IS NULL
    UNION ALL
    SELECT 'contract.created_by_employee_id -> employee_master.employee_id', count(*)
    FROM contract c
    LEFT JOIN employee_master p ON p.employee_id = c.created_by_employee_id
    WHERE p.employee_id IS NULL
    UNION ALL
    SELECT 'compliance_record.vendor_id -> vendor.vendor_id', count(*)
    FROM compliance_record c
    LEFT JOIN vendor p ON p.vendor_id = c.vendor_id
    WHERE p.vendor_id IS NULL
    UNION ALL
    SELECT 'transaction_master.vendor_id -> vendor.vendor_id', count(*)
    FROM transaction_master c
    LEFT JOIN vendor p ON p.vendor_id = c.vendor_id
    WHERE p.vendor_id IS NULL
    UNION ALL
    SELECT 'expense_claim.employee_id -> employee_master.employee_id', count(*)
    FROM expense_claim c
    LEFT JOIN employee_master p ON p.employee_id = c.employee_id
    WHERE p.employee_id IS NULL
    UNION ALL
    SELECT 'expense_claim.approved_by -> employee_master.employee_id', count(*)
    FROM expense_claim c
    LEFT JOIN employee_master p ON p.employee_id = c.approved_by
    WHERE c.approved_by IS NOT NULL AND p.employee_id IS NULL
    UNION ALL
    SELECT 'approval_workflow.transaction_id -> transaction_master.transaction_id', count(*)
    FROM approval_workflow c
    LEFT JOIN transaction_master p ON p.transaction_id = c.transaction_id
    WHERE p.transaction_id IS NULL
    UNION ALL
    SELECT 'approval_workflow.approver_employee_id -> employee_master.employee_id', count(*)
    FROM approval_workflow c
    LEFT JOIN employee_master p ON p.employee_id = c.approver_employee_id
    WHERE p.employee_id IS NULL
    UNION ALL
    SELECT 'audit_investigation.created_by_employee_id -> employee_master.employee_id', count(*)
    FROM audit_investigation c
    LEFT JOIN employee_master p ON p.employee_id = c.created_by_employee_id
    WHERE p.employee_id IS NULL
    UNION ALL
    SELECT 'audit_finding.investigation_id -> audit_investigation.investigation_id', count(*)
    FROM audit_finding c
    LEFT JOIN audit_investigation p ON p.investigation_id = c.investigation_id
    WHERE p.investigation_id IS NULL
    UNION ALL
    SELECT 'evidence.finding_id -> audit_finding.finding_id', count(*)
    FROM evidence c
    LEFT JOIN audit_finding p ON p.finding_id = c.finding_id
    WHERE p.finding_id IS NULL
) AS fk_summary
ORDER BY fk_check;

-- =========================================================
-- 5. ORPHAN DETECTION DETAIL
-- =========================================================

SELECT c.employee_id, c.department_id
FROM employee_master c
LEFT JOIN department_master p ON p.department_id = c.department_id
WHERE p.department_id IS NULL;

SELECT c.employee_id, c.manager_id
FROM employee_master c
LEFT JOIN employee_master p ON p.employee_id = c.manager_id
WHERE c.manager_id IS NOT NULL AND p.employee_id IS NULL;

SELECT c.department_id, c.head_employee_id
FROM department_master c
LEFT JOIN employee_master p ON p.employee_id = c.head_employee_id
WHERE p.employee_id IS NULL;

SELECT c.contract_id, c.vendor_id
FROM contract c
LEFT JOIN vendor p ON p.vendor_id = c.vendor_id
WHERE p.vendor_id IS NULL;

SELECT c.contract_id, c.created_by_employee_id
FROM contract c
LEFT JOIN employee_master p ON p.employee_id = c.created_by_employee_id
WHERE p.employee_id IS NULL;

SELECT c.compliance_id, c.vendor_id
FROM compliance_record c
LEFT JOIN vendor p ON p.vendor_id = c.vendor_id
WHERE p.vendor_id IS NULL;

SELECT c.transaction_id, c.vendor_id
FROM transaction_master c
LEFT JOIN vendor p ON p.vendor_id = c.vendor_id
WHERE p.vendor_id IS NULL;

SELECT c.claim_id, c.employee_id
FROM expense_claim c
LEFT JOIN employee_master p ON p.employee_id = c.employee_id
WHERE p.employee_id IS NULL;

SELECT c.claim_id, c.approved_by
FROM expense_claim c
LEFT JOIN employee_master p ON p.employee_id = c.approved_by
WHERE c.approved_by IS NOT NULL AND p.employee_id IS NULL;

SELECT c.approval_id, c.transaction_id
FROM approval_workflow c
LEFT JOIN transaction_master p ON p.transaction_id = c.transaction_id
WHERE p.transaction_id IS NULL;

SELECT c.approval_id, c.approver_employee_id
FROM approval_workflow c
LEFT JOIN employee_master p ON p.employee_id = c.approver_employee_id
WHERE p.employee_id IS NULL;

SELECT c.investigation_id, c.created_by_employee_id
FROM audit_investigation c
LEFT JOIN employee_master p ON p.employee_id = c.created_by_employee_id
WHERE p.employee_id IS NULL;

SELECT c.finding_id, c.investigation_id
FROM audit_finding c
LEFT JOIN audit_investigation p ON p.investigation_id = c.investigation_id
WHERE p.investigation_id IS NULL;

SELECT c.evidence_id, c.finding_id
FROM evidence c
LEFT JOIN audit_finding p ON p.finding_id = c.finding_id
WHERE p.finding_id IS NULL;

-- =========================================================
-- 6. BUSINESS RULE VALIDATION
-- =========================================================

SELECT 'contract.contract_value > 0' AS rule_name, count(*) AS violation_count
FROM contract
WHERE contract_value <= 0;

SELECT 'contract.end_date >= contract.start_date' AS rule_name, count(*) AS violation_count
FROM contract
WHERE end_date < start_date;

SELECT 'transaction_master.amount > 0' AS rule_name, count(*) AS violation_count
FROM transaction_master
WHERE amount <= 0;

SELECT 'transaction_master.risk_score between 0 and 1' AS rule_name, count(*) AS violation_count
FROM transaction_master
WHERE risk_score < 0 OR risk_score > 1;

SELECT 'expense_claim.amount > 0' AS rule_name, count(*) AS violation_count
FROM expense_claim
WHERE amount <= 0;

SELECT 'expense_claim.submission_date >= expense_claim.claim_date' AS rule_name, count(*) AS violation_count
FROM expense_claim
WHERE submission_date < claim_date;

SELECT 'approval_workflow.transaction_amount > 0' AS rule_name, count(*) AS violation_count
FROM approval_workflow
WHERE transaction_amount <= 0;

SELECT 'approval_workflow.approval_limit > 0' AS rule_name, count(*) AS violation_count
FROM approval_workflow
WHERE approval_limit <= 0;

SELECT 'approval_workflow.approval_level between 1 and 5' AS rule_name, count(*) AS violation_count
FROM approval_workflow
WHERE approval_level < 1 OR approval_level > 5;

SELECT 'approval_workflow rejected rows require rejection_reason only' AS rule_name, count(*) AS violation_count
FROM approval_workflow
WHERE (approval_status = 'REJECTED' AND rejection_reason IS NULL)
   OR (approval_status <> 'REJECTED' AND rejection_reason IS NOT NULL);

SELECT 'approval_workflow escalated rows require delegation_ref only' AS rule_name, count(*) AS violation_count
FROM approval_workflow
WHERE (approval_status = 'ESCALATED' AND delegation_ref IS NULL)
   OR (approval_status <> 'ESCALATED' AND delegation_ref IS NOT NULL);

SELECT 'audit_investigation.scope_period_end >= scope_period_start' AS rule_name, count(*) AS violation_count
FROM audit_investigation
WHERE scope_period_end < scope_period_start;

SELECT 'audit_investigation.completed_date >= created_date when completed_date exists' AS rule_name, count(*) AS violation_count
FROM audit_investigation
WHERE completed_date IS NOT NULL
  AND completed_date < created_date;

SELECT 'audit_finding.confidence_score between 0 and 1' AS rule_name, count(*) AS violation_count
FROM audit_finding
WHERE confidence_score < 0 OR confidence_score > 1;

SELECT 'audit_finding.validated_at >= created_at when validated_at exists' AS rule_name, count(*) AS violation_count
FROM audit_finding
WHERE validated_at IS NOT NULL
  AND validated_at < created_at;

SELECT 'evidence.alignment_score between 0 and 1' AS rule_name, count(*) AS violation_count
FROM evidence
WHERE alignment_score < 0 OR alignment_score > 1;

SELECT 'employee_master.email contains @' AS rule_name, count(*) AS violation_count
FROM employee_master
WHERE position('@' IN email) <= 1;

-- Status/date consistency checks that may indicate data quality issues.

SELECT 'completed investigations should have completed_date' AS rule_name, count(*) AS issue_count
FROM audit_investigation
WHERE status = 'COMPLETED'
  AND completed_date IS NULL;

SELECT 'non-completed investigations should not have completed_date' AS rule_name, count(*) AS issue_count
FROM audit_investigation
WHERE status <> 'COMPLETED'
  AND completed_date IS NOT NULL;

SELECT 'validated findings should have validated_at' AS rule_name, count(*) AS issue_count
FROM audit_finding
WHERE status = 'VALIDATED'
  AND validated_at IS NULL;

-- =========================================================
-- 7. AUDIT INTEGRITY VALIDATION
-- =========================================================

SELECT i.investigation_id, i.audit_question
FROM audit_investigation i
LEFT JOIN audit_finding f ON f.investigation_id = i.investigation_id
WHERE f.finding_id IS NULL
ORDER BY i.investigation_id;

SELECT f.finding_id, f.investigation_id, f.severity, f.status
FROM audit_finding f
LEFT JOIN evidence e ON e.finding_id = f.finding_id
WHERE e.evidence_id IS NULL
ORDER BY f.finding_id;

SELECT e.evidence_id, e.finding_id, e.source_type, e.source_table, e.source_record_id
FROM evidence e
WHERE e.source_table NOT IN (
    'Approval_Workflow',
    'Audit_Reports',
    'Compliance_Record',
    'Contract',
    'DNS_Logs',
    'Enterprise_Policies',
    'Expense_Claim',
    'HR_Analytics',
    'PaySim_Transactions',
    'Vendor'
)
ORDER BY e.evidence_id;

SELECT e.evidence_id, e.finding_id, e.source_type, e.source_table
FROM evidence e
WHERE (e.source_type = 'APPROVAL_RECORD' AND e.source_table <> 'Approval_Workflow')
   OR (e.source_type = 'AUDIT_REPORT' AND e.source_table <> 'Audit_Reports')
   OR (e.source_type = 'COMPLIANCE_RECORD' AND e.source_table <> 'Compliance_Record')
   OR (e.source_type = 'CONTRACT_RECORD' AND e.source_table <> 'Contract')
   OR (e.source_type = 'DNS_LOG' AND e.source_table <> 'DNS_Logs')
   OR (e.source_type = 'EXPENSE_CLAIM' AND e.source_table <> 'Expense_Claim')
   OR (e.source_type = 'HR_RECORD' AND e.source_table <> 'HR_Analytics')
   OR (e.source_type = 'POLICY_DOCUMENT' AND e.source_table <> 'Enterprise_Policies')
   OR (e.source_type = 'TRANSACTION_RECORD' AND e.source_table <> 'PaySim_Transactions')
   OR (e.source_type = 'VENDOR_RECORD' AND e.source_table <> 'Vendor')
ORDER BY e.evidence_id;

SELECT f.investigation_id, count(*) AS finding_count
FROM audit_finding f
GROUP BY f.investigation_id
HAVING count(*) = 0;

SELECT f.finding_id, count(e.evidence_id) AS evidence_count
FROM audit_finding f
LEFT JOIN evidence e ON e.finding_id = f.finding_id
GROUP BY f.finding_id
HAVING count(e.evidence_id) = 0
ORDER BY f.finding_id;

SELECT citation_reference, count(*) AS citation_count
FROM evidence
GROUP BY citation_reference
HAVING count(*) > 1
ORDER BY citation_count DESC, citation_reference;

-- =========================================================
-- 8. AUDIT RISK AND CONTROL EXCEPTION QUERIES
-- =========================================================

SELECT v.vendor_id, v.vendor_name, v.risk_rating, v.status, count(t.transaction_id) AS transaction_count
FROM vendor v
JOIN transaction_master t ON t.vendor_id = v.vendor_id
WHERE v.risk_rating IN ('HIGH', 'CRITICAL')
GROUP BY v.vendor_id, v.vendor_name, v.risk_rating, v.status
ORDER BY transaction_count DESC, v.vendor_id;

SELECT v.vendor_id, v.vendor_name, c.compliance_id, c.framework, c.status, c.expiry_date
FROM vendor v
JOIN compliance_record c ON c.vendor_id = v.vendor_id
WHERE c.status IN ('EXPIRED', 'NON_COMPLIANT')
ORDER BY c.expiry_date, v.vendor_id;

SELECT aw.approval_id, aw.transaction_id, aw.transaction_amount, aw.approver_employee_id, aw.approval_limit
FROM approval_workflow aw
WHERE aw.transaction_amount > aw.approval_limit
  AND aw.approval_status = 'APPROVED'
ORDER BY aw.transaction_amount DESC;

SELECT ec.claim_id, ec.employee_id, ec.amount, ec.expense_category, ec.approval_status
FROM expense_claim ec
WHERE ec.receipt_attached = false
  AND ec.approval_status = 'APPROVED'
ORDER BY ec.amount DESC;

SELECT c.contract_id, c.vendor_id, c.end_date, c.status
FROM contract c
WHERE c.end_date < CURRENT_DATE
  AND c.status = 'ACTIVE'
ORDER BY c.end_date;
