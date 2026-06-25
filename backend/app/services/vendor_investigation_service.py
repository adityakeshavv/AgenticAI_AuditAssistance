from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.base_investigation_service import BaseInvestigationService
from app.services.document_retrieval_agent_service import DocumentRetrievalAgent
from app.services.evidence_aggregator_service import EvidenceAggregatorService
from app.services.recommendation_service import RecommendationService
from app.services.risk_scoring_service import RiskScoringService
from app.services.vendor_service import VendorService


class VendorInvestigationService(BaseInvestigationService):
    def __init__(self, db: Session) -> None:
        self.db = db
        self.vendor_service = VendorService(db)
        self.document_agent = DocumentRetrievalAgent(db)
        self.evidence_aggregator = EvidenceAggregatorService()
        self.risk_scoring_service = RiskScoringService()
        self.recommendation_service = RecommendationService()

    def matches_vendor_investigation(self, query: str) -> bool:
        normalized = query.lower()
        if re.search(r"\b(?:investigate|review|analyze|analyse)\b.*\bvendor\b", normalized):
            return True
        if re.search(r"\bvendor\b.*\b(?:investigate|review|analyze|analyse)\b", normalized):
            return True
        return bool(self.extract_vendor_id(query))

    def extract_vendor_id(self, query: str) -> str | None:
        match = re.search(r"\bVND[- ]?\d+\b", query.upper())
        if not match:
            return None
        return match.group(0).replace(" ", "-")

    def investigate(self, *, query: str, vendor_id: str) -> dict[str, Any]:
        bundle = self.vendor_service.build_bundle(vendor_id)
        vendor = bundle["vendor"]
        if not vendor:
            return {
                "success": False,
                "reason": "vendor_not_found",
                "message": f"Vendor {vendor_id} was not found.",
                "intent": {
                    "original_query": query,
                    "normalized_query": query.strip().lower(),
                    "domain": "vendor",
                    "entity": "vendor",
                    "intent": "vendor_investigation",
                    "query_type": "investigate",
                    "filters": {"vendor_id": {"operator": "=", "value": vendor_id}},
                    "supported": False,
                    "confidence": 0.0,
                    "reason": "Vendor identifier was not found in the database.",
                },
                "entity_type": "vendor",
                "entity_id": vendor_id,
                "vendor_summary": "",
                "key_findings": [],
                "supporting_evidence": [],
                "supporting_documents": [],
                "recommendations": [],
                "structured_evidence": [],
                "document_evidence": [],
                "sources": [],
                "finding": {
                    "finding_title": "Vendor Not Found",
                    "finding_summary": f"Vendor {vendor_id} was not found.",
                    "evidence_summary": "No vendor profile was available for the supplied identifier.",
                    "recommendation": "Verify the vendor identifier and try again.",
                    "supporting_documents": [],
                },
                "final_response": f"Vendor {vendor_id} was not found.",
                "reasoning": [f"Vendor lookup failed for {vendor_id}."],
            }

        structured_intent = {
            "original_query": query,
            "normalized_query": query.strip().lower(),
            "domain": "vendor",
            "entity": "vendor",
            "intent": "vendor_investigation",
            "query_type": "investigate",
            "filters": {"vendor_id": {"operator": "=", "value": vendor_id}},
            "supported": True,
            "confidence": 1.0,
            "reason": "Vendor investigation was identified from the query.",
        }

        document_result = self.document_agent.retrieve(
            query=query,
            structured_intent=structured_intent,
            transaction_results=bundle["transactions"],
        )

        structured_evidence = self._build_structured_evidence(bundle)
        aggregated = self.evidence_aggregator.aggregate(
            structured_evidence=structured_evidence,
            document_evidence=list(document_result.get("documents", [])),
            sources=[
                "vendor",
                "transaction_master",
                "contract",
                "audit_finding",
                *document_result.get("sources", []),
            ],
        )

        risk = self.risk_scoring_service.score(
            finding={"finding_title": "Vendor Investigation Summary", "finding_summary": vendor["vendor_name"]},
            structured_evidence=aggregated["structured_evidence"],
            document_evidence=aggregated["document_evidence"],
        )

        metrics = self.calculate_metrics(
            transactions=bundle["transactions"],
            contracts=bundle["contracts"],
            documents=aggregated["document_evidence"],
        )
        key_findings = self.build_findings(
            entity_type="vendor",
            transactions=bundle["transactions"],
            contracts=bundle["contracts"],
            findings=bundle["findings"],
            documents=aggregated["document_evidence"],
            risk_drivers=risk["risk_drivers"],
        )
        supporting_evidence = self._build_supporting_evidence(bundle, aggregated, key_findings)
        recommendations = self.build_recommendations(
            entity_type="vendor",
            transactions=bundle["transactions"],
            contracts=bundle["contracts"],
            findings=bundle["findings"],
            risk_rating=risk["risk_rating"],
        )
        investigation_summary = self.build_summary(
            entity_type="vendor",
            entity_id=vendor_id,
            entity_name=vendor["vendor_name"],
            risk_rating=risk["risk_rating"],
            risk_drivers=risk["risk_drivers"],
            key_findings=key_findings,
            metrics=metrics,
        )
        supporting_documents = aggregated["document_evidence"]
        top_supporting_evidence = self.prioritize_supporting_evidence(supporting_documents)[:5]

        finding = {
            "finding_title": "Vendor Investigation Summary",
            "finding_summary": investigation_summary,
            "evidence_summary": " ".join(key_findings) if key_findings else "No significant vendor findings were identified.",
            "recommendation": recommendations[0] if recommendations else self.recommendation_service.recommend(
                finding_title="Vendor Investigation Summary",
                structured_evidence=aggregated["structured_evidence"],
                document_evidence=aggregated["document_evidence"],
            ),
            "supporting_documents": supporting_documents,
        }

        return {
            "success": True,
            "intent": structured_intent,
            "entity_type": "vendor",
            "entity_id": vendor_id,
            "vendor_summary": investigation_summary,
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
                f"Vendor {vendor_id} profile retrieved.",
                f"{len(bundle['transactions'])} vendor transaction(s) retrieved.",
                f"{len(bundle['contracts'])} vendor contract(s) retrieved.",
                f"{len(aggregated['document_evidence'])} supporting document(s) retrieved.",
                f"{len(bundle['findings'])} linked finding(s) retrieved.",
                "Evidence was aggregated and scored for vendor investigation.",
            ],
        }

    def _build_structured_evidence(self, bundle: dict[str, Any]) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        vendor = bundle["vendor"]
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

        evidence.extend(
            {
                "source_type": "vendor_transaction",
                **transaction,
            }
            for transaction in bundle["transactions"]
        )
        evidence.extend(
            {
                "source_type": "vendor_contract",
                **contract,
            }
            for contract in bundle["contracts"]
        )
        evidence.extend(
            {
                "source_type": "vendor_finding",
                **finding,
            }
            for finding in bundle["findings"]
        )
        return evidence

    def _build_supporting_evidence(
        self,
        bundle: dict[str, Any],
        aggregated: dict[str, Any],
        key_findings: list[str],
    ) -> list[dict[str, Any]]:
        vendor = bundle["vendor"] or {}
        transactions = bundle["transactions"]
        contracts = bundle["contracts"]
        findings = bundle["findings"]

        supporting_evidence = [
            {
                "summary": (
                    f"Vendor profile: {vendor.get('vendor_name')} ({vendor.get('vendor_id')}) "
                    f"with status {vendor.get('status')} and risk rating {vendor.get('risk_rating')}."
                )
            },
            {
                "summary": (
                    f"{len(transactions)} transaction(s) reviewed; "
                    f"{sum(1 for row in transactions if str(row.get('status', '')).upper() == 'FLAGGED')} flagged; "
                    f"{sum(1 for row in transactions if float(row.get('risk_score') or 0) > 0.8)} above risk threshold."
                )
            },
            {
                "summary": (
                    f"{len(contracts)} contract(s) reviewed; "
                    f"{sum(1 for row in contracts if str(row.get('status', '')).upper() == 'EXPIRED')} expired."
                )
            },
            {
                "summary": f"{len(findings)} linked audit finding(s) and {len(aggregated['document_evidence'])} supporting document(s) retrieved."
            },
        ]

        if key_findings:
            supporting_evidence.extend({"summary": finding} for finding in key_findings[:3])
        return supporting_evidence
