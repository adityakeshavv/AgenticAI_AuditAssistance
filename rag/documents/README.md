# Agentic AI-Powered Audit Assistant — Synthetic Document Repository

This repository contains 835 synthetic, enterprise-grade unstructured documents
that cross-reference the structured audit datasets (Employee_Master, Vendor,
Contract, Compliance_Record, Transaction_Master, Expense_Claim,
Approval_Workflow, Purchase_Order, Audit_Investigation, Audit_Finding,
Evidence). It is designed for ingestion into a RAG pipeline supporting the
Agentic AI Audit Assistant.

## Folder Structure

```
repository/
├── 01_policies/              20 PDFs  — Enterprise policy documents
├── 02_contracts/             100 PDFs — Vendor contract agreements
├── 03_audit_reports/         50 PDFs  — Internal audit reports
├── 04_investigation_reports/ 100 PDFs — Audit investigation reports
├── 05_emails/                500 .eml — Email communications (6 categories)
├── 06_sop_documents/         15 PDFs  — Standard operating procedures
├── 07_meeting_minutes/       50 DOCX  — Audit/risk/compliance meeting minutes
└── 08_metadata/
    ├── metadata.csv                       <- MASTER metadata file (835 rows)
    ├── metadata_policies.csv
    ├── metadata_contracts.csv
    ├── metadata_audit_reports.csv
    ├── metadata_investigation_reports.csv
    ├── metadata_emails.csv
    ├── metadata_sops.csv
    └── metadata_meeting_minutes.csv
```

**Total: 835 documents** (20 + 100 + 50 + 100 + 500 + 15 + 50)

## metadata.csv Schema

| Column | Description |
|---|---|
| document_id | Unique document identifier (matches in-document ID where applicable) |
| document_type | One of: POLICY, CONTRACT, AUDIT_REPORT, INVESTIGATION_REPORT, SOP, MEETING_MINUTES, EMAIL_APPROVAL_REQUEST, EMAIL_ESCALATION, EMAIL_COMPLIANCE_VIOLATION, EMAIL_SUSPICIOUS_TRANSACTION, EMAIL_VENDOR_DISCUSSION, EMAIL_AUDIT_COMMUNICATION |
| related_vendor_id | FK -> Vendor.vendor_id (blank if not applicable) |
| related_employee_id | FK -> Employee_Master.employee_id (blank if not applicable) |
| related_transaction_id | FK -> Transaction_Master.transaction_id (blank if not applicable) |
| related_contract_id | FK -> Contract.contract_id (blank if not applicable) |
| related_investigation_id | FK -> Audit_Investigation.investigation_id (blank if not applicable) |
| creation_date | Document creation/filing date (ISO format, 2023-2026) |
| file_name | File name within its type folder |

## Email Category Breakdown (500 total)

| Category | Count | Description |
|---|---|---|
| EMAIL_APPROVAL_REQUEST | 110 | Requests for transaction/approval sign-off |
| EMAIL_ESCALATION | 90 | Escalations for limit breaches or stalled approvals |
| EMAIL_COMPLIANCE_VIOLATION | 80 | Alerts on expired/non-compliant vendor certifications |
| EMAIL_SUSPICIOUS_TRANSACTION | 80 | Fraud/anomaly detection alerts |
| EMAIL_VENDOR_DISCUSSION | 80 | Vendor-facing contract/performance discussions |
| EMAIL_AUDIT_COMMUNICATION | 60 | Investigation document requests, interviews, findings notices |

## Validation Summary

- **Referential integrity:** 0 orphan references across vendor_id, employee_id,
  transaction_id, contract_id, and investigation_id — all checked against the
  structured CSV tables.
- **File existence:** 835/835 metadata rows have a corresponding file on disk.
- **Date range:** 835/835 documents have a creation_date between 2023-01-01
  and 2026-12-31.
- **Scenario coverage:** Documents intentionally include both compliant and
  non-compliant scenarios — e.g. expired-but-active contracts, non-compliant
  vendors, escalated/rejected approvals, high-risk-score transactions, and
  inconclusive/unsubstantiated investigation outcomes — alongside routine,
  clean-record documents.

## Notes on Realism & Cross-Referencing

- Contract PDFs preserve the underlying contract's real start/end dates and
  status from the structured Contract table (some intentionally show
  EXPIRED-but-historically-ACTIVE status for audit testing), while the
  document's own filing/signature date is set within the 2023-2026 window.
- Investigation reports reference real Audit_Investigation, Audit_Finding,
  Vendor, Employee, and Transaction records, but are filed within the
  2023-2026 repository window since investigations may review prior periods.
- Emails use realistic enterprise email addressing
  (firstname.lastname@enterprise.com for internal staff; vendor-domain
  addresses for external vendor contacts) and reference actual IDs from the
  structured tables in the message body for RAG-traceable evidence linking.
- All email files are encoded as standard RFC 5322 .eml files
  (quoted-printable, UTF-8) and open as plain readable text in any mail
  client or text-based parser.

## RAG Ingestion Guidance

1. Use `08_metadata/metadata.csv` as the primary index — load it first to
   build a document_id -> file_path -> related entity ID mapping.
2. Chunk PDFs and DOCX files using your standard text-extraction pipeline
   (e.g. pdfplumber / python-docx) — each document is 1-3 pages and chunks
   cleanly by section heading.
3. Use the related_*_id columns to build graph edges between unstructured
   documents and structured database rows for hybrid (vector + SQL +
   knowledge graph) retrieval, consistent with the Agentic AI Audit
   Assistant's Layer 4 (Hybrid Retrieval) architecture.
4. Emails are flat text files — no attachments are embedded; treat each
   .eml as a single retrievable unit.
