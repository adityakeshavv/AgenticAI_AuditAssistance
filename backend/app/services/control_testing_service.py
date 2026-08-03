from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import TransactionMaster
from app.services.approval_service import execute_approval_query
from app.services.compliance_service import execute_compliance_query
from app.services.document_retrieval_agent_service import DocumentRetrievalAgent
from app.services.evidence_aggregator_service import EvidenceAggregatorService
from app.services.transaction_service import execute_transaction_query


class ControlTestingService:
    """Deterministic control-testing engine built from structured audit evidence."""

    def __init__(
        self,
        db: Session,
        *,
        document_agent: DocumentRetrievalAgent | None = None,
        evidence_aggregator: EvidenceAggregatorService | None = None,
    ) -> None:
        self.db = db
        self.document_agent = document_agent or DocumentRetrievalAgent(db)
        self.evidence_aggregator = evidence_aggregator or EvidenceAggregatorService()

    def run(
        self,
        *,
        query: str,
        trace_context: Any | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        span = trace_context.begin_span(
            "control_testing_agent",
            input_payload={"query": query, "page": page, "page_size": page_size},
            metadata={"service": "ControlTestingService"},
        ) if trace_context else None

        transaction_result = execute_transaction_query(self.db, "show flagged transactions", page=page, page_size=page_size, trace_context=trace_context)
        approval_result = execute_approval_query(self.db, "show approvals that exceeded authority", page=page, page_size=page_size)
        compliance_result = execute_compliance_query(self.db, "show expired compliance records", page=page, page_size=page_size)
        duplicate_rows = self._duplicate_payment_test()

        structured_evidence: list[dict[str, Any]] = []
        structured_evidence.extend(self._normalize_transaction_rows(transaction_result.get("results", [])))
        structured_evidence.extend(self._normalize_approval_rows(approval_result.get("results", [])))
        structured_evidence.extend(self._normalize_compliance_rows(compliance_result.get("results", [])))
        structured_evidence.extend(duplicate_rows)

        control_tests = self._build_control_tests(
            transaction_result=transaction_result,
            approval_result=approval_result,
            compliance_result=compliance_result,
            duplicate_rows=duplicate_rows,
        )
        control_summary = self._build_control_summary(control_tests=control_tests, structured_evidence=structured_evidence)
        key_findings = self._build_key_findings(control_tests=control_tests, structured_evidence=structured_evidence)

        document_result = self.document_agent.retrieve(
            query=query,
            structured_intent={
                "intent": "control_testing",
                "domain": "control",
                "entity": "control",
                "supported": True,
                "filters": {},
            },
            transaction_results=structured_evidence,
            trace_context=trace_context,
        )
        document_evidence = list(document_result.get("documents", []))
        aggregated = self.evidence_aggregator.aggregate(
            structured_evidence=structured_evidence,
            document_evidence=document_evidence,
            sources=["transaction_master", "approval_workflow", "compliance_record", *document_result.get("sources", [])],
            trace_context=trace_context,
        )

        findings_count = sum(1 for test in control_tests if test.get("status") == "failed")
        risk_rating = self._risk_rating(findings_count=findings_count, evidence_count=len(structured_evidence), document_count=len(document_evidence))
        recommendations = self._build_recommendations(control_tests=control_tests, structured_evidence=structured_evidence, document_evidence=document_evidence)

        finding_title = "Control Exceptions Detected" if findings_count else "No Material Control Exceptions"
        finding_summary = control_summary
        if not findings_count:
            finding_summary = "No material control exceptions were identified by the baseline control test suite."

        response = {
            "success": True,
            "entity_type": "control",
            "entity_id": None,
            "control_summary": control_summary,
            "control_tests": control_tests,
            "control_metrics": {
                "tests_run": len(control_tests),
                "tests_failed": findings_count,
                "structured_records_reviewed": len(structured_evidence),
                "documents_reviewed": len(document_evidence),
            },
            "investigation_summary": control_summary,
            "key_findings": key_findings,
            "top_supporting_evidence": self._rank_evidence(structured_evidence, document_evidence)[:5],
            "supporting_evidence": self._build_supporting_evidence(structured_evidence, duplicate_rows, control_tests),
            "supporting_documents": document_evidence,
            "structured_evidence": aggregated["structured_evidence"],
            "document_evidence": aggregated["document_evidence"],
            "sources": aggregated["sources"],
            "recommendations": recommendations,
            "finding": {
                "title": finding_title,
                "summary": finding_summary,
                "category": "Control Monitoring",
                "severity": risk_rating,
                "evidence_summary": " ".join(key_findings) if key_findings else finding_summary,
                "recommendation": recommendations[0] if recommendations else "",
                "supporting_documents": document_evidence,
            },
            "agents_used": ["control_testing_agent"] + (["document_retrieval_agent"] if document_evidence else []),
            "reasoning": [
                "Baseline control tests were executed across transactions, approvals, compliance records, and duplicate-payment detection.",
                "Supporting documents were linked from structured control evidence where available.",
            ],
        }

        if span:
            span.finish(
                output={
                    "tests_run": len(control_tests),
                    "tests_failed": findings_count,
                    "structured_record_count": len(structured_evidence),
                    "document_count": len(document_evidence),
                    "risk_rating": risk_rating,
                },
                metadata={
                    "tests_run": len(control_tests),
                    "tests_failed": findings_count,
                    "structured_record_count": len(structured_evidence),
                    "document_count": len(document_evidence),
                    "risk_rating": risk_rating,
                },
            )

        return response

    def _build_control_tests(
        self,
        *,
        transaction_result: dict[str, Any],
        approval_result: dict[str, Any],
        compliance_result: dict[str, Any],
        duplicate_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        tx_rows = list(transaction_result.get("results", [])) if transaction_result.get("success") else []
        approval_rows = list(approval_result.get("results", [])) if approval_result.get("success") else []
        compliance_rows = list(compliance_result.get("results", [])) if compliance_result.get("success") else []

        return [
            {
                "test_name": "transaction_monitoring",
                "description": "Flagged transactions were reviewed for transaction monitoring exceptions.",
                "status": "failed" if tx_rows else "passed",
                "result_count": len(tx_rows),
                "severity": "MEDIUM" if tx_rows else "LOW",
            },
            {
                "test_name": "approval_authority",
                "description": "Approval workflows were checked for authority-limit exceptions.",
                "status": "failed" if approval_rows else "passed",
                "result_count": len(approval_rows),
                "severity": "HIGH" if approval_rows else "LOW",
            },
            {
                "test_name": "compliance_certification",
                "description": "Compliance records were checked for expired or non-compliant certificates.",
                "status": "failed" if compliance_rows else "passed",
                "result_count": len(compliance_rows),
                "severity": "HIGH" if compliance_rows else "LOW",
            },
            {
                "test_name": "duplicate_payments",
                "description": "Potential duplicate payments were identified through repeated vendor/date/amount combinations.",
                "status": "failed" if duplicate_rows else "passed",
                "result_count": len(duplicate_rows),
                "severity": "HIGH" if duplicate_rows else "LOW",
            },
        ]

    def _build_control_summary(self, *, control_tests: list[dict[str, Any]], structured_evidence: list[dict[str, Any]]) -> str:
        failed = [test for test in control_tests if test.get("status") == "failed"]
        if not failed:
            return (
                f"Baseline control testing reviewed {len(control_tests)} control area(s) and found no material exceptions "
                f"across {len(structured_evidence)} structured evidence item(s)."
            )
        failed_labels = ", ".join(str(test.get("test_name") or "control") for test in failed)
        return (
            f"Baseline control testing reviewed {len(control_tests)} control area(s) and identified exceptions in "
            f"{len(failed)} area(s): {failed_labels}. {len(structured_evidence)} structured evidence item(s) were reviewed."
        )

    def _build_key_findings(self, *, control_tests: list[dict[str, Any]], structured_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for test in control_tests:
            if test.get("status") == "failed":
                findings.append(
                    {
                        "summary": f"{test.get('description')} ({test.get('result_count', 0)} exception(s) detected.)",
                        "severity": test.get("severity", "LOW"),
                        "category": "Control Exception",
                    }
                )
        if not findings:
            findings.append(
                {
                    "summary": f"No material exceptions were detected across {len(structured_evidence)} reviewed control evidence item(s).",
                    "severity": "LOW",
                    "category": "Control Monitoring",
                }
            )
        return findings

    def _build_recommendations(
        self,
        *,
        control_tests: list[dict[str, Any]],
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
    ) -> list[str]:
        failed_names = [str(test.get("test_name") or "") for test in control_tests if test.get("status") == "failed"]
        recommendations: list[str] = []
        if "approval_authority" in failed_names:
            recommendations.append("Review approval authority thresholds and escalation handling for the affected approval workflows.")
        if "compliance_certification" in failed_names:
            recommendations.append("Revalidate expired or non-compliant certificates before further vendor engagement.")
        if "duplicate_payments" in failed_names:
            recommendations.append("Investigate the duplicate payment candidates and confirm whether matching entries were intentional.")
        if "transaction_monitoring" in failed_names:
            recommendations.append("Review the flagged transaction population for control design or monitoring gaps.")
        if document_evidence:
            recommendations.append("Review supporting documents for the cited control exceptions.")
        if not recommendations:
            recommendations.append("Continue periodic monitoring and re-run the control test suite on a scheduled basis.")
        return list(dict.fromkeys(recommendations))

    def _build_supporting_evidence(
        self,
        structured_evidence: list[dict[str, Any]],
        duplicate_rows: list[dict[str, Any]],
        control_tests: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for item in structured_evidence:
            evidence.append(
                {
                    "source_type": item.get("source_type"),
                    "reference": item.get("transaction_id") or item.get("approval_id") or item.get("compliance_id") or item.get("control_test_id"),
                    "summary": item.get("reason_selected") or item.get("findings_summary") or item.get("result_reason") or "Control evidence item.",
                }
            )
        for item in duplicate_rows:
            evidence.append(
                {
                    "source_type": "control_test",
                    "reference": item.get("control_test_id"),
                    "summary": item.get("reason_selected") or "Potential duplicate payment control exception.",
                }
            )
        for item in control_tests:
            evidence.append(
                {
                    "source_type": "control_test",
                    "reference": item.get("test_name"),
                    "summary": item.get("description"),
                }
            )
        return evidence

    def _duplicate_payment_test(self) -> list[dict[str, Any]]:
        stmt = (
            select(
                TransactionMaster.vendor_id,
                TransactionMaster.amount,
                TransactionMaster.currency,
                TransactionMaster.transaction_type,
                TransactionMaster.transaction_date,
                func.count(TransactionMaster.transaction_id).label("duplicate_count"),
            )
            .group_by(
                TransactionMaster.vendor_id,
                TransactionMaster.amount,
                TransactionMaster.currency,
                TransactionMaster.transaction_type,
                TransactionMaster.transaction_date,
            )
            .having(func.count(TransactionMaster.transaction_id) > 1)
            .order_by(desc(func.count(TransactionMaster.transaction_id)))
            .limit(10)
        )

        rows = self.db.execute(stmt).all()
        duplicates: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            vendor_id = str(row.vendor_id)
            amount = float(row.amount) if isinstance(row.amount, Decimal) else row.amount
            duplicate_count = int(row.duplicate_count or 0)
            control_test_id = f"DUP-{vendor_id}-{row.transaction_date.isoformat()}-{index}"
            duplicates.append(
                {
                    "control_test_id": control_test_id,
                    "source_type": "control_test",
                    "control_test_name": "duplicate_payments",
                    "vendor_id": vendor_id,
                    "amount": amount,
                    "currency": row.currency,
                    "transaction_type": row.transaction_type,
                    "transaction_date": row.transaction_date.isoformat() if isinstance(row.transaction_date, date) else row.transaction_date,
                    "duplicate_count": duplicate_count,
                    "status": "FLAGGED",
                    "reason_selected": "Potential duplicate payment pattern identified by matching vendor, amount, currency, type, and date.",
                    "citation_text": (
                        f"{duplicate_count} transactions share vendor {vendor_id}, amount {amount}, currency {row.currency}, "
                        f"type {row.transaction_type}, and date {row.transaction_date.isoformat()}."
                    ),
                    "risk_score": 0.85,
                }
            )
        return duplicates

    def _normalize_transaction_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            normalized.append(
                {
                    **row,
                    "source_type": row.get("source_type") or "transaction_master",
                    "reason_selected": row.get("reason_selected") or "Flagged transaction reviewed by the control test suite.",
                }
            )
        return normalized

    def _normalize_approval_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            normalized.append(
                {
                    **row,
                    "source_type": row.get("source_type") or "approval_workflow",
                    "employee_id": row.get("approver_employee_id") or row.get("employee_id"),
                    "reason_selected": row.get("reason_selected") or "Approval control exception identified by the test suite.",
                }
            )
        return normalized

    def _normalize_compliance_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            normalized.append(
                {
                    **row,
                    "source_type": row.get("source_type") or "compliance_record",
                    "reason_selected": row.get("reason_selected") or "Compliance control exception identified by the test suite.",
                }
            )
        return normalized

    def _rank_evidence(self, structured_evidence: list[dict[str, Any]], document_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked = []
        for item in structured_evidence:
            ranked.append(
                {
                    "source_type": item.get("source_type"),
                    "reference": item.get("transaction_id") or item.get("approval_id") or item.get("compliance_id") or item.get("control_test_id"),
                    "summary": item.get("reason_selected") or item.get("citation_text") or "Control evidence item.",
                }
            )
        for item in document_evidence:
            ranked.append(
                {
                    "source_type": "document_metadata",
                    "reference": item.get("document_id"),
                    "summary": item.get("reason_selected") or item.get("citation_text") or "Supporting document.",
                }
            )
        return ranked

    def _risk_rating(self, *, findings_count: int, evidence_count: int, document_count: int) -> str:
        score = findings_count * 3 + (1 if evidence_count > 5 else 0) + (1 if document_count > 0 else 0)
        if score >= 7:
            return "CRITICAL"
        if score >= 5:
            return "HIGH"
        if score >= 2:
            return "MEDIUM"
        return "LOW"
