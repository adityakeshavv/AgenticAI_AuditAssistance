-- Agentic AI-Powered Audit Assistant
-- PostgreSQL 17.5 audit investigation query library.
--
-- Scope:
-- - Uses only the 11 finalized canonical tables.
-- - Each query is executable independently.
-- - Queries are designed as realistic audit investigations for vendor,
--   compliance, transaction, approval, expense, investigation, and evidence
--   traceability workflows.

-- =========================================================
-- 1. VENDOR AUDITS
-- =========================================================

-- 1. High-risk or critical vendors with completed payments in the last 12 months of available transaction data.
WITH max_txn_date AS (
    SELECT max(transaction_date) AS as_of_date
    FROM transaction_master
)
SELECT
    v.vendor_id,
    v.vendor_name,
    v.vendor_type,
    v.country,
    v.risk_rating,
    v.status AS vendor_status,
    count(t.transaction_id) AS transaction_count,
    sum(t.amount) AS total_paid,
    max(t.transaction_date) AS latest_payment_date
FROM vendor v
JOIN transaction_master t ON t.vendor_id = v.vendor_id
CROSS JOIN max_txn_date m
WHERE v.risk_rating IN ('HIGH', 'CRITICAL')
  AND t.status = 'COMPLETED'
  AND t.transaction_date >= m.as_of_date - INTERVAL '12 months'
GROUP BY v.vendor_id, v.vendor_name, v.vendor_type, v.country, v.risk_rating, v.status
ORDER BY total_paid DESC, transaction_count DESC;

-- 2. Blacklisted vendors with any transaction activity.
SELECT
    v.vendor_id,
    v.vendor_name,
    v.status AS vendor_status,
    count(t.transaction_id) AS transaction_count,
    sum(t.amount) AS total_transaction_amount,
    min(t.transaction_date) AS first_transaction_date,
    max(t.transaction_date) AS last_transaction_date
FROM vendor v
JOIN transaction_master t ON t.vendor_id = v.vendor_id
WHERE v.status = 'BLACKLISTED'
GROUP BY v.vendor_id, v.vendor_name, v.status
ORDER BY total_transaction_amount DESC;

-- 3. Active contracts with blacklisted vendors.
SELECT
    c.contract_id,
    c.vendor_id,
    v.vendor_name,
    v.risk_rating,
    v.status AS vendor_status,
    c.contract_value,
    c.currency,
    c.start_date,
    c.end_date,
    c.status AS contract_status
FROM contract c
JOIN vendor v ON v.vendor_id = c.vendor_id
WHERE v.status = 'BLACKLISTED'
  AND c.status = 'ACTIVE'
ORDER BY c.contract_value DESC;

-- 4. Vendors with high total spend but low/medium risk rating.
SELECT
    v.vendor_id,
    v.vendor_name,
    v.risk_rating,
    count(t.transaction_id) AS transaction_count,
    sum(t.amount) AS total_spend,
    avg(t.risk_score) AS average_transaction_risk
FROM vendor v
JOIN transaction_master t ON t.vendor_id = v.vendor_id
WHERE t.status IN ('COMPLETED', 'FLAGGED')
GROUP BY v.vendor_id, v.vendor_name, v.risk_rating
HAVING v.risk_rating IN ('LOW', 'MEDIUM')
   AND sum(t.amount) >= 1000000
ORDER BY total_spend DESC;

-- 5. Vendors with multiple active contracts.
SELECT
    v.vendor_id,
    v.vendor_name,
    v.risk_rating,
    count(c.contract_id) AS active_contract_count,
    sum(c.contract_value) AS total_active_contract_value
FROM vendor v
JOIN contract c ON c.vendor_id = v.vendor_id
WHERE c.status = 'ACTIVE'
GROUP BY v.vendor_id, v.vendor_name, v.risk_rating
HAVING count(c.contract_id) > 1
ORDER BY active_contract_count DESC, total_active_contract_value DESC;

-- =========================================================
-- 2. COMPLIANCE AUDITS
-- =========================================================

-- 6. Vendors paid after compliance expiry.
SELECT
    v.vendor_id,
    v.vendor_name,
    cr.compliance_id,
    cr.framework,
    cr.status AS compliance_status,
    cr.expiry_date,
    t.transaction_id,
    t.transaction_date,
    t.amount,
    t.status AS transaction_status
FROM vendor v
JOIN compliance_record cr ON cr.vendor_id = v.vendor_id
JOIN transaction_master t ON t.vendor_id = v.vendor_id
WHERE t.transaction_date > cr.expiry_date
  AND t.status IN ('COMPLETED', 'FLAGGED')
ORDER BY t.transaction_date DESC, t.amount DESC;

-- 7. Active vendors without any compliant compliance record.
SELECT
    v.vendor_id,
    v.vendor_name,
    v.risk_rating,
    v.status AS vendor_status,
    count(cr.compliance_id) AS compliance_record_count,
    count(cr.compliance_id) FILTER (WHERE cr.status = 'COMPLIANT') AS compliant_record_count
FROM vendor v
LEFT JOIN compliance_record cr ON cr.vendor_id = v.vendor_id
WHERE v.status = 'ACTIVE'
GROUP BY v.vendor_id, v.vendor_name, v.risk_rating, v.status
HAVING count(cr.compliance_id) FILTER (WHERE cr.status = 'COMPLIANT') = 0
ORDER BY v.risk_rating DESC, compliance_record_count ASC;

-- 8. High-risk vendors with non-compliant or expired ISO 27001/SOC 2 records.
SELECT
    v.vendor_id,
    v.vendor_name,
    v.risk_rating,
    cr.compliance_id,
    cr.framework,
    cr.status,
    cr.assessment_date,
    cr.expiry_date,
    cr.findings_summary
FROM vendor v
JOIN compliance_record cr ON cr.vendor_id = v.vendor_id
WHERE v.risk_rating IN ('HIGH', 'CRITICAL')
  AND cr.framework IN ('ISO 27001', 'SOC 2 Type II')
  AND cr.status IN ('EXPIRED', 'NON_COMPLIANT')
ORDER BY v.risk_rating DESC, cr.expiry_date;

-- 9. Vendors with active contracts and expired compliance records.
SELECT DISTINCT
    v.vendor_id,
    v.vendor_name,
    c.contract_id,
    c.contract_value,
    c.end_date,
    cr.compliance_id,
    cr.framework,
    cr.expiry_date
FROM vendor v
JOIN contract c ON c.vendor_id = v.vendor_id
JOIN compliance_record cr ON cr.vendor_id = v.vendor_id
WHERE c.status = 'ACTIVE'
  AND cr.status = 'EXPIRED'
ORDER BY cr.expiry_date, c.contract_value DESC;

-- 10. Compliance frameworks with highest non-compliance volume.
SELECT
    framework,
    count(*) AS total_records,
    count(*) FILTER (WHERE status = 'NON_COMPLIANT') AS non_compliant_records,
    count(*) FILTER (WHERE status = 'EXPIRED') AS expired_records,
    round(
        100.0 * count(*) FILTER (WHERE status IN ('NON_COMPLIANT', 'EXPIRED')) / count(*),
        2
    ) AS issue_rate_pct
FROM compliance_record
GROUP BY framework
ORDER BY issue_rate_pct DESC, total_records DESC;

-- =========================================================
-- 3. TRANSACTION AUDITS
-- =========================================================

-- 11. Highest risk transactions with vendor context.
SELECT
    t.transaction_id,
    t.transaction_date,
    t.vendor_id,
    v.vendor_name,
    v.risk_rating,
    v.status AS vendor_status,
    t.amount,
    t.currency,
    t.transaction_type,
    t.risk_score,
    t.status AS transaction_status
FROM transaction_master t
JOIN vendor v ON v.vendor_id = t.vendor_id
WHERE t.risk_score >= 0.900
ORDER BY t.risk_score DESC, t.amount DESC;

-- 12. Round-number high-value transactions.
SELECT
    t.transaction_id,
    t.transaction_date,
    v.vendor_name,
    t.amount,
    t.currency,
    t.transaction_type,
    t.risk_score,
    t.status
FROM transaction_master t
JOIN vendor v ON v.vendor_id = t.vendor_id
WHERE t.amount >= 100000
  AND mod(t.amount, 1000) = 0
ORDER BY t.amount DESC;

-- 13. Vendors with unusually concentrated transaction activity.
SELECT
    v.vendor_id,
    v.vendor_name,
    v.risk_rating,
    count(t.transaction_id) AS transaction_count,
    sum(t.amount) AS total_amount,
    avg(t.amount) AS average_amount,
    max(t.amount) AS largest_transaction
FROM vendor v
JOIN transaction_master t ON t.vendor_id = v.vendor_id
GROUP BY v.vendor_id, v.vendor_name, v.risk_rating
HAVING count(t.transaction_id) >= 20
ORDER BY transaction_count DESC, total_amount DESC;

-- 14. Flagged transactions to active low-risk vendors.
SELECT
    t.transaction_id,
    t.transaction_date,
    v.vendor_id,
    v.vendor_name,
    v.risk_rating,
    v.status AS vendor_status,
    t.amount,
    t.transaction_type,
    t.risk_score
FROM transaction_master t
JOIN vendor v ON v.vendor_id = t.vendor_id
WHERE t.status = 'FLAGGED'
  AND v.status = 'ACTIVE'
  AND v.risk_rating = 'LOW'
ORDER BY t.risk_score DESC, t.amount DESC;

-- 15. Transaction amounts not matching approval workflow amount.
SELECT
    aw.approval_id,
    aw.transaction_id,
    t.amount AS transaction_master_amount,
    aw.transaction_amount AS approval_record_amount,
    aw.approval_status,
    aw.approval_date
FROM approval_workflow aw
JOIN transaction_master t ON t.transaction_id = aw.transaction_id
WHERE aw.transaction_amount <> t.amount
ORDER BY abs(aw.transaction_amount - t.amount) DESC;

-- =========================================================
-- 4. APPROVAL AUDITS
-- =========================================================

-- 16. Approved transactions exceeding approver authority limit.
SELECT
    aw.approval_id,
    aw.transaction_id,
    aw.approver_employee_id,
    e.employee_name AS approver_name,
    e.designation,
    aw.transaction_amount,
    aw.approval_limit,
    aw.approval_level,
    aw.approval_date
FROM approval_workflow aw
JOIN employee_master e ON e.employee_id = aw.approver_employee_id
WHERE aw.approval_status = 'APPROVED'
  AND aw.transaction_amount > aw.approval_limit
ORDER BY aw.transaction_amount - aw.approval_limit DESC;

-- 17. Rejected approvals with high-risk vendor transactions.
SELECT
    aw.approval_id,
    aw.transaction_id,
    aw.approval_date,
    aw.rejection_reason,
    t.amount,
    t.risk_score,
    v.vendor_id,
    v.vendor_name,
    v.risk_rating
FROM approval_workflow aw
JOIN transaction_master t ON t.transaction_id = aw.transaction_id
JOIN vendor v ON v.vendor_id = t.vendor_id
WHERE aw.approval_status = 'REJECTED'
  AND v.risk_rating IN ('HIGH', 'CRITICAL')
ORDER BY t.risk_score DESC, t.amount DESC;

-- 18. Escalated approvals and their delegated references.
SELECT
    aw.approval_id,
    aw.transaction_id,
    aw.transaction_amount,
    aw.approver_employee_id,
    e.employee_name AS approver_name,
    aw.approval_level,
    aw.approval_limit,
    aw.delegation_ref,
    aw.approval_date
FROM approval_workflow aw
JOIN employee_master e ON e.employee_id = aw.approver_employee_id
WHERE aw.approval_status = 'ESCALATED'
ORDER BY aw.transaction_amount DESC;

-- 19. Approvers with repeated approvals over their limit.
SELECT
    aw.approver_employee_id,
    e.employee_name,
    e.designation,
    e.department_id,
    count(*) AS over_limit_approval_count,
    sum(aw.transaction_amount - aw.approval_limit) AS total_excess_amount
FROM approval_workflow aw
JOIN employee_master e ON e.employee_id = aw.approver_employee_id
WHERE aw.approval_status = 'APPROVED'
  AND aw.transaction_amount > aw.approval_limit
GROUP BY aw.approver_employee_id, e.employee_name, e.designation, e.department_id
HAVING count(*) >= 2
ORDER BY over_limit_approval_count DESC, total_excess_amount DESC;

-- 20. Transactions with multiple approval records.
SELECT
    aw.transaction_id,
    count(*) AS approval_record_count,
    min(aw.approval_date) AS first_approval_date,
    max(aw.approval_date) AS last_approval_date,
    string_agg(DISTINCT aw.approval_status::text, ', ' ORDER BY aw.approval_status::text) AS statuses
FROM approval_workflow aw
GROUP BY aw.transaction_id
HAVING count(*) > 1
ORDER BY approval_record_count DESC, aw.transaction_id;

-- =========================================================
-- 5. EXPENSE AUDITS
-- =========================================================

-- 21. Approved expense claims without receipts.
SELECT
    ec.claim_id,
    ec.employee_id,
    e.employee_name,
    e.department_id,
    ec.amount,
    ec.expense_category,
    ec.claim_date,
    ec.submission_date,
    ec.policy_id,
    ec.approved_by
FROM expense_claim ec
JOIN employee_master e ON e.employee_id = ec.employee_id
WHERE ec.approval_status = 'APPROVED'
  AND ec.receipt_attached = false
ORDER BY ec.amount DESC;

-- 22. Expense claims approved by the submitting employee.
SELECT
    ec.claim_id,
    ec.employee_id,
    e.employee_name,
    ec.amount,
    ec.expense_category,
    ec.approval_status,
    ec.approved_by
FROM expense_claim ec
JOIN employee_master e ON e.employee_id = ec.employee_id
WHERE ec.approved_by = ec.employee_id
ORDER BY ec.amount DESC;

-- 23. High-value pending expense claims.
SELECT
    ec.claim_id,
    ec.employee_id,
    e.employee_name,
    e.department_id,
    ec.amount,
    ec.expense_category,
    ec.claim_date,
    ec.submission_date,
    ec.receipt_attached
FROM expense_claim ec
JOIN employee_master e ON e.employee_id = ec.employee_id
WHERE ec.approval_status = 'PENDING'
  AND ec.amount >= 10000
ORDER BY ec.amount DESC;

-- 24. Potential duplicate expense claims by employee, amount, category, and claim date.
SELECT
    employee_id,
    amount,
    expense_category,
    claim_date,
    count(*) AS duplicate_claim_count,
    string_agg(claim_id, ', ' ORDER BY claim_id) AS claim_ids
FROM expense_claim
GROUP BY employee_id, amount, expense_category, claim_date
HAVING count(*) > 1
ORDER BY duplicate_claim_count DESC, amount DESC;

-- 25. Employees with repeated flagged or rejected expense claims.
SELECT
    ec.employee_id,
    e.employee_name,
    e.department_id,
    count(*) AS exception_claim_count,
    sum(ec.amount) AS exception_claim_amount
FROM expense_claim ec
JOIN employee_master e ON e.employee_id = ec.employee_id
WHERE ec.approval_status IN ('FLAGGED', 'REJECTED')
GROUP BY ec.employee_id, e.employee_name, e.department_id
HAVING count(*) >= 2
ORDER BY exception_claim_count DESC, exception_claim_amount DESC;

-- =========================================================
-- 6. INVESTIGATION AUDITS
-- =========================================================

-- 26. Open or in-progress investigations with high/critical findings.
SELECT
    ai.investigation_id,
    ai.audit_question,
    ai.investigation_type,
    ai.status AS investigation_status,
    ai.created_date,
    count(af.finding_id) AS high_severity_finding_count
FROM audit_investigation ai
JOIN audit_finding af ON af.investigation_id = ai.investigation_id
WHERE ai.status IN ('OPEN', 'IN_PROGRESS')
  AND af.severity IN ('HIGH', 'CRITICAL')
GROUP BY ai.investigation_id, ai.audit_question, ai.investigation_type, ai.status, ai.created_date
ORDER BY high_severity_finding_count DESC, ai.created_date;

-- 27. Validated findings with low confidence scores.
SELECT
    af.finding_id,
    af.investigation_id,
    ai.audit_question,
    af.severity,
    af.category,
    af.confidence_score,
    af.status,
    af.validated_at,
    af.description
FROM audit_finding af
JOIN audit_investigation ai ON ai.investigation_id = af.investigation_id
WHERE af.status = 'VALIDATED'
  AND af.confidence_score < 0.500
ORDER BY af.confidence_score ASC, af.severity DESC;

-- 28. Completed investigations with unresolved findings.
SELECT
    ai.investigation_id,
    ai.audit_question,
    ai.completed_date,
    af.finding_id,
    af.severity,
    af.category,
    af.status AS finding_status
FROM audit_investigation ai
JOIN audit_finding af ON af.investigation_id = ai.investigation_id
WHERE ai.status = 'COMPLETED'
  AND af.status IN ('OPEN', 'ESCALATED')
ORDER BY ai.completed_date DESC, af.severity DESC;

-- =========================================================
-- 7. EVIDENCE TRACEABILITY QUERIES
-- =========================================================

-- 29. Full evidence chain for findings, from investigation to evidence citation.
SELECT
    ai.investigation_id,
    ai.audit_question,
    af.finding_id,
    af.severity,
    af.category,
    af.status AS finding_status,
    af.confidence_score,
    e.evidence_id,
    e.source_type,
    e.source_table,
    e.source_record_id,
    e.alignment_score,
    e.citation_reference,
    e.retrieved_at,
    e.evidence_text
FROM audit_investigation ai
JOIN audit_finding af ON af.investigation_id = ai.investigation_id
JOIN evidence e ON e.finding_id = af.finding_id
ORDER BY ai.investigation_id, af.finding_id, e.alignment_score DESC;

-- 30. Findings supported by multiple independent source types.
SELECT
    af.finding_id,
    af.investigation_id,
    af.severity,
    af.category,
    af.status,
    count(e.evidence_id) AS evidence_count,
    count(DISTINCT e.source_type) AS source_type_count,
    string_agg(DISTINCT e.source_type::text, ', ' ORDER BY e.source_type::text) AS source_types,
    avg(e.alignment_score) AS average_alignment_score
FROM audit_finding af
JOIN evidence e ON e.finding_id = af.finding_id
GROUP BY af.finding_id, af.investigation_id, af.severity, af.category, af.status
HAVING count(DISTINCT e.source_type) >= 2
ORDER BY source_type_count DESC, evidence_count DESC, average_alignment_score DESC;
