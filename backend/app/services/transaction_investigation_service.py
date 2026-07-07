from __future__ import annotations

import re
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ApprovalWorkflow, AuditFinding, Contract, Evidence, TransactionMaster
from app.services.base_investigation_service import BaseInvestigationService
from app.services.document_retrieval_agent_service import DocumentRetrievalAgent
from app.services.evidence_aggregator_service import EvidenceAggregatorService
from app.services.recommendation_service import RecommendationService
from app.services.risk_scoring_service import RiskScoringService
from app.services.vendor_service import VendorService


class TransactionInvestigationService(BaseInvestigationService):
    def __init__(self, db: Session) -> None:
        self.db = db
        self.vendor_service = VendorService(db)
        self.document_agent = DocumentRetrievalAgent(db)
        self.evidence_aggregator = EvidenceAggregatorService()
        self.risk_scoring_service = RiskScoringService()
        self.recommendation_service = RecommendationService()

    def matches_transaction_investigation(self, query: str) -> bool:
        normalized = query.lower()
        if re.search(r"\b(?:investigate|review|analyze|analyse)\b.*\btransaction\b", normalized):
            return True
        if re.search(r"\btransaction\b.*\b(?:investigate|review|analyze|analyse)\b", normalized):
            return True
        return bool(self.extract_transaction_id(query))

    def extract_transaction_id(self, query: str) -> str | None:
        match = re.search(r"\bTXN[- ]?[A-Z0-9]+\b", query.upper())
        if not match:
            return None
        return match.group(0).replace(" ", "-")

    def investigate(self, *, query: str, transaction_id: str, trace_context: Any | None = None) -> dict[str, Any]:
        span = trace_context.begin_span(
            "transaction_investigation_agent",
            input_payload={"query": query, "transaction_id": transaction_id},
            metadata={"service": "TransactionInvestigationService"},
        ) if trace_context else None

        transaction = self.db.get(TransactionMaster, transaction_id)
        if not transaction:
            result = self._not_found_response(query=query, transaction_id=transaction_id)
            if span:
                span.finish(output=result, metadata={"status": "not_found"})
            return result

        vendor = self.vendor_service.get_vendor_profile(transaction.vendor_id)
        contracts = self._get_related_contracts(transaction.vendor_id)
        approvals = self._get_approval_records(transaction.transaction_id)
        findings = self._get_related_findings(transaction.transaction_id, transaction.vendor_id)

        transaction_row = self._serialize_transaction(transaction)
        structured_intent = {
            "original_query": query,
            "normalized_query": query.strip().lower(),
            "domain": "transaction",
            "entity": "transaction",
            "intent": "transaction_investigation",
            "query_type": "investigate",
            "filters": {"transaction_id": {"operator": "=", "value": transaction_id}},
            "supported": True,
            "confidence": 1.0,
            "reason": "Transaction investigation was identified from the query.",
        }

        document_result = self.document_agent.retrieve(
            query=query,
            structured_intent=structured_intent,
            transaction_results=[transaction_row],
            trace_context=trace_context,
        )

        structured_evidence = self._build_structured_evidence(
            transaction=transaction_row,
            vendor=vendor,
            contracts=contracts,
            approvals=approvals,
            findings=findings,
        )
        aggregated = self.evidence_aggregator.aggregate(
            structured_evidence=structured_evidence,
            document_evidence=list(document_result.get("documents", [])),
            sources=[
                "transaction_master",
                "vendor",
                "contract",
                "approval_workflow",
                "audit_finding",
                *document_result.get("sources", []),
            ],
            trace_context=trace_context,
        )

        risk = self.risk_scoring_service.score(
            finding={"finding_title": "Transaction Investigation Summary", "finding_summary": transaction.transaction_id},
            structured_evidence=aggregated["structured_evidence"],
            document_evidence=aggregated["document_evidence"],
            trace_context=trace_context,
        )

        metrics = self.calculate_metrics(
            transactions=[transaction_row],
            contracts=contracts,
            documents=aggregated["document_evidence"],
        )
        metrics["findings_reviewed"] = len(findings)
        metrics["evidence_records"] = len(approvals) + len(findings)
        metrics["linked_entities"] = len(
            [item for item in (vendor, *contracts, *approvals, *findings) if item]
        )

        key_findings = self.build_findings(
            entity_type="transaction",
            transactions=[transaction_row],
            contracts=contracts,
            findings=findings,
            documents=aggregated["document_evidence"],
            risk_drivers=risk["risk_drivers"],
        )
        key_findings.extend(self._transaction_specific_findings(transaction_row, approvals, findings, aggregated["document_evidence"]))
        key_findings = list(dict.fromkeys(key_findings))

        supporting_evidence = self._build_supporting_evidence(
            transaction=transaction_row,
            vendor=vendor,
            contracts=contracts,
            approvals=approvals,
            findings=findings,
            documents=aggregated["document_evidence"],
            key_findings=key_findings,
        )
        recommendations = self.build_recommendations(
            entity_type="transaction",
            transactions=[transaction_row],
            contracts=contracts,
            findings=findings,
            risk_rating=risk["risk_rating"],
        )
        recommendations.extend(self._transaction_recommendations(transaction_row, approvals, findings, risk["risk_rating"]))
        recommendations = list(dict.fromkeys(recommendations))

        investigation_summary = self.build_summary(
            entity_type="transaction",
            entity_id=transaction_id,
            entity_name=f"{transaction.currency} {float(transaction.amount):,.2f}",
            risk_rating=risk["risk_rating"],
            risk_drivers=risk["risk_drivers"],
            key_findings=key_findings,
            metrics={
                "transactions_reviewed": 1,
                "contracts_reviewed": len(contracts),
                "documents_reviewed": len(aggregated["document_evidence"]),
                "flagged_transactions": 1 if str(transaction.status).upper() == "FLAGGED" else 0,
            },
        )

        supporting_documents = aggregated["document_evidence"]
        top_supporting_evidence = self.prioritize_supporting_evidence(supporting_documents)[:5]

        finding = {
            "finding_title": "Transaction Investigation Summary",
            "finding_summary": investigation_summary,
            "evidence_summary": " ".join(key_findings) if key_findings else "No significant transaction findings were identified.",
            "recommendation": recommendations[0] if recommendations else self.recommendation_service.recommend(
                finding_title="Transaction Investigation Summary",
                structured_evidence=aggregated["structured_evidence"],
                document_evidence=aggregated["document_evidence"],
            ),
            "supporting_documents": supporting_documents,
        }

        result = {
            "success": True,
            "intent": structured_intent,
            "entity_type": "transaction",
            "entity_id": transaction_id,
            "transaction_summary": investigation_summary,
            "investigation_summary": investigation_summary,
            "investigation_metrics": metrics,
            "top_supporting_evidence": top_supporting_evidence,
            "key_findings": key_findings,
            "supporting_evidence": supporting_evidence,
            "supporting_documents": supporting_documents,
            "recommendations": recommendations,
            "structured_evidence": aggregated["structured_evidence"],
            "document_evidence": aggregated["document_evidence"],
            "sources": aggregated["sources"],
            "risk_rating": risk["risk_rating"],
            "risk_score": risk["risk_score"],
            "risk_drivers": risk["risk_drivers"],
            "finding": finding,
            "reasoning": [
                f"Transaction {transaction_id} profile retrieved.",
                f"{len(contracts)} related contract(s) retrieved.",
                f"{len(approvals)} related approval record(s) retrieved.",
                f"{len(findings)} related finding(s) retrieved.",
                f"{len(aggregated['document_evidence'])} supporting document(s) retrieved.",
                "Evidence was aggregated and scored for transaction investigation.",
            ],
        }
        if span:
            span.finish(
                output={
                    "success": True,
                    "risk_rating": result["risk_rating"],
                    "structured_count": len(result["structured_evidence"]),
                    "document_count": len(result["document_evidence"]),
                },
                metadata={
                    "risk_rating": result["risk_rating"],
                    "structured_count": len(result["structured_evidence"]),
                    "document_count": len(result["document_evidence"]),
                },
            )
        return result

    def _not_found_response(self, *, query: str, transaction_id: str) -> dict[str, Any]:
        return {
            "success": False,
            "reason": "transaction_not_found",
            "message": f"Transaction {transaction_id} was not found.",
            "intent": {
                "original_query": query,
                "normalized_query": query.strip().lower(),
                "domain": "transaction",
                "entity": "transaction",
                "intent": "transaction_investigation",
                "query_type": "investigate",
                "filters": {"transaction_id": {"operator": "=", "value": transaction_id}},
                "supported": False,
                "confidence": 0.0,
                "reason": "Transaction identifier was not found in the database.",
            },
            "entity_type": "transaction",
            "entity_id": transaction_id,
            "transaction_summary": "",
            "investigation_summary": "",
            "investigation_metrics": {
                "documents_reviewed": 0,
                "findings_reviewed": 0,
                "evidence_records": 0,
                "linked_entities": 0,
            },
            "top_supporting_evidence": [],
            "key_findings": [],
            "supporting_evidence": [],
            "supporting_documents": [],
            "recommendations": [],
            "structured_evidence": [],
            "document_evidence": [],
            "sources": [],
            "finding": {
                "finding_title": "Transaction Not Found",
                "finding_summary": f"Transaction {transaction_id} was not found.",
                "evidence_summary": "No transaction record was available for the supplied identifier.",
                "recommendation": "Verify the transaction identifier and try again.",
                "supporting_documents": [],
            },
            "final_response": f"Transaction {transaction_id} was not found.",
            "reasoning": [f"Transaction lookup failed for {transaction_id}."],
        }

    def _serialize_transaction(self, transaction: TransactionMaster) -> dict[str, Any]:
        return {
            "transaction_id": transaction.transaction_id,
            "transaction_date": transaction.transaction_date.isoformat(),
            "vendor_id": transaction.vendor_id,
            "amount": float(transaction.amount),
            "currency": transaction.currency,
            "transaction_type": transaction.transaction_type,
            "risk_score": float(transaction.risk_score),
            "status": transaction.status,
        }

    def _get_related_contracts(self, vendor_id: str) -> list[dict[str, Any]]:
        stmt = select(Contract).where(Contract.vendor_id == vendor_id).order_by(desc(Contract.end_date))
        contracts = list(self.db.scalars(stmt).all())
        return [
            {
                "contract_id": contract.contract_id,
                "vendor_id": contract.vendor_id,
                "contract_value": float(contract.contract_value),
                "currency": contract.currency,
                "start_date": contract.start_date.isoformat(),
                "end_date": contract.end_date.isoformat(),
                "contract_type": contract.contract_type,
                "status": contract.status,
                "created_by_employee_id": contract.created_by_employee_id,
            }
            for contract in contracts
        ]

    def _get_approval_records(self, transaction_id: str) -> list[dict[str, Any]]:
        stmt = select(ApprovalWorkflow).where(ApprovalWorkflow.transaction_id == transaction_id).order_by(
            desc(ApprovalWorkflow.approval_date), desc(ApprovalWorkflow.approval_level)
        )
        approvals = list(self.db.scalars(stmt).all())
        return [
            {
                "approval_id": approval.approval_id,
                "transaction_id": approval.transaction_id,
                "transaction_amount": float(approval.transaction_amount),
                "approver_employee_id": approval.approver_employee_id,
                "approval_level": approval.approval_level,
                "approval_limit": float(approval.approval_limit),
                "approval_status": approval.approval_status,
                "approval_date": approval.approval_date.isoformat(),
                "rejection_reason": approval.rejection_reason,
                "delegation_ref": approval.delegation_ref,
            }
            for approval in approvals
        ]

    def _get_related_findings(self, transaction_id: str, vendor_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(AuditFinding)
            .join(Evidence, AuditFinding.finding_id == Evidence.finding_id)
            .where(
                (
                    (Evidence.source_type == "TRANSACTION_RECORD")
                    & (Evidence.source_record_id == transaction_id)
                )
                | (
                    (Evidence.source_type == "VENDOR_RECORD")
                    & (Evidence.source_record_id == vendor_id)
                )
            )
            .order_by(desc(AuditFinding.created_at), desc(AuditFinding.updated_at))
        )
        findings = list(self.db.scalars(stmt).unique().all())
        return [
            {
                "finding_id": finding.finding_id,
                "investigation_id": finding.investigation_id,
                "severity": finding.severity,
                "category": finding.category,
                "description": finding.description,
                "confidence_score": float(finding.confidence_score),
                "status": finding.status,
            }
            for finding in findings
        ]

    def _build_structured_evidence(
        self,
        *,
        transaction: dict[str, Any],
        vendor: dict[str, Any] | None,
        contracts: list[dict[str, Any]],
        approvals: list[dict[str, Any]],
        findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = [
            {
                "source_type": "transaction_profile",
                **transaction,
            }
        ]
        if vendor:
            evidence.append(
                {
                    "source_type": "vendor_profile",
                    "vendor_id": vendor.get("vendor_id"),
                    "vendor_name": vendor.get("vendor_name"),
                    "vendor_type": vendor.get("vendor_type"),
                    "country": vendor.get("country"),
                    "risk_rating": vendor.get("risk_rating"),
                    "status": vendor.get("status"),
                }
            )
        evidence.extend({"source_type": "contract", **contract} for contract in contracts)
        evidence.extend({"source_type": "approval_workflow", **approval} for approval in approvals)
        evidence.extend({"source_type": "audit_finding", **finding} for finding in findings)
        return evidence

    def _build_supporting_evidence(
        self,
        *,
        transaction: dict[str, Any],
        vendor: dict[str, Any] | None,
        contracts: list[dict[str, Any]],
        approvals: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        key_findings: list[str],
    ) -> list[dict[str, Any]]:
        supporting_evidence: list[dict[str, Any]] = [
            {
                "summary": (
                    f"Transaction {transaction.get('transaction_id')} for {transaction.get('currency')} "
                    f"{float(transaction.get('amount') or 0):,.2f} was reviewed with status {transaction.get('status')} "
                    f"and risk score {float(transaction.get('risk_score') or 0):.2f}."
                )
            }
        ]

        if vendor:
            supporting_evidence.append(
                {
                    "summary": (
                        f"Related vendor {vendor.get('vendor_id')} ({vendor.get('vendor_name')}) "
                        f"has status {vendor.get('status')} and risk rating {vendor.get('risk_rating')}."
                    )
                }
            )

        supporting_evidence.append(
            {
                "summary": (
                    f"{len(contracts)} related contract(s), {len(approvals)} approval record(s), "
                    f"{len(findings)} linked finding(s), and {len(documents)} supporting document(s) were retrieved."
                )
            }
        )

        if approvals:
            supporting_evidence.append(
                {
                    "summary": (
                        f"{sum(1 for item in approvals if str(item.get('approval_status', '')).upper() == 'ESCALATED')} "
                        "approval exception(s) and "
                        f"{sum(1 for item in approvals if str(item.get('approval_status', '')).upper() == 'REJECTED')} "
                        "rejected approval(s) were identified."
                    )
                }
            )

        if key_findings:
            supporting_evidence.extend({"summary": finding} for finding in key_findings[:3])

        return supporting_evidence

    def _transaction_specific_findings(
        self,
        transaction: dict[str, Any],
        approvals: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        documents: list[dict[str, Any]],
    ) -> list[str]:
        key_findings: list[str] = []
        try:
            amount = float(transaction.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        try:
            risk_score = float(transaction.get("risk_score") or 0)
        except (TypeError, ValueError):
            risk_score = 0.0

        if amount > 1_000_000:
            key_findings.append("High transaction value detected.")
        elif amount > 50_000:
            key_findings.append("Elevated transaction value detected.")
        if risk_score > 0.8:
            key_findings.append("High transaction risk score detected.")
        if any(str(item.get("approval_status", "")).upper() == "ESCALATED" for item in approvals):
            key_findings.append("Approval exception detected.")
        if any(str(doc.get("document_category", "")).lower() == "investigation_reports" for doc in documents):
            key_findings.append("Investigation report linked.")
        if any(str(doc.get("document_category", "")).lower() == "emails" for doc in documents):
            key_findings.append("Escalation email detected.")
        if len(documents) > 3:
            key_findings.append("Multiple supporting documents identified.")
        if findings:
            key_findings.append(f"{len(findings)} related finding(s) retrieved.")
        return key_findings

    def _transaction_recommendations(
        self,
        transaction: dict[str, Any],
        approvals: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        risk_rating: str,
    ) -> list[str]:
        recommendations: list[str] = []
        if any(str(item.get("approval_status", "")).upper() == "ESCALATED" for item in approvals):
            recommendations.append("Review approval chain.")
        if any(str(doc.get("approval_status", "")).upper() == "REJECTED" for doc in approvals):
            recommendations.append("Validate supporting documentation.")
        if findings:
            recommendations.append("Conduct manual audit review.")
        if risk_rating in {"HIGH", "CRITICAL"}:
            recommendations.append("Escalate for compliance verification.")
        if not recommendations:
            recommendations.append("Continue periodic transaction monitoring.")
        return list(dict.fromkeys(recommendations))
