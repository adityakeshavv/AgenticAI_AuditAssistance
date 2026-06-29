from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.document_retrieval_agent_service import DocumentRetrievalAgent
from app.services.agent_orchestrator_service import AgentOrchestratorService
from app.services.evidence_aggregator_service import EvidenceAggregatorService
from app.services.investigation_planner_service import InvestigationPlannerService
from app.services.llm_router_service import StructuredIntentService
from app.services.response_composer_service import ResponseComposerService
from app.services.traceability_service import TraceabilityService
from app.services.vendor_investigation_service import VendorInvestigationService
from app.services.transaction_investigation_service import TransactionInvestigationService
from app.services.transaction_service import TRANSACTION_ALLOWED_INTENTS, execute_transaction_query


class AgentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.intent_service = StructuredIntentService()
        self.investigation_planner = InvestigationPlannerService()
        self.traceability_service = TraceabilityService()
        self.document_agent = DocumentRetrievalAgent(db)
        self.vendor_investigation_service = VendorInvestigationService(db)
        self.transaction_investigation_service = TransactionInvestigationService(db)
        self.evidence_aggregator = EvidenceAggregatorService()
        self.response_composer = ResponseComposerService()
        self.agent_orchestrator = AgentOrchestratorService(
            db,
            document_agent=self.document_agent,
            vendor_investigation_service=self.vendor_investigation_service,
            evidence_aggregator=self.evidence_aggregator,
            investigation_planner=self.investigation_planner,
        )

    def run(self, *, query: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        traceability = self.traceability_service.initialize()
        response_contract: dict[str, Any] = {
            "success": True,
            "query": query,
            "intent": {},
            "investigation_plan": {},
            "entities_investigated": [],
            "entity_type": None,
            "entity_id": None,
            "agents_used": [],
            "risk_rating": "LOW",
            "risk_score": 0,
            "risk_drivers": [],
            "transaction_summary": "",
            "vendor_summary": "",
            "key_findings": [],
            "supporting_evidence": [],
            "supporting_documents": [],
            "recommendations": [],
            "structured_evidence": [],
            "document_evidence": [],
            "sources": [],
            "reasoning": [],
            "execution_metadata": [],
            "finding": {},
            "final_response": "",
            "traceability": traceability,
            "message": None,
        }

        transaction_id = self.transaction_investigation_service.extract_transaction_id(query)
        if self.transaction_investigation_service.matches_transaction_investigation(query) and transaction_id:
            self.traceability_service.record_reasoning(
                traceability,
                "Query matched the transaction investigation workflow.",
            )
            self.traceability_service.record_agent(
                traceability,
                "transaction_investigation_agent",
                "Query requested transaction investigation and contained a transaction identifier.",
            )

            transaction_result = self.transaction_investigation_service.investigate(query=query, transaction_id=transaction_id)
            response_contract.update(transaction_result)

            for reason in transaction_result.get("reasoning", []):
                self.traceability_service.record_reasoning(traceability, reason)

            if transaction_result.get("document_evidence"):
                self.traceability_service.record_agent(
                    traceability,
                    "document_retrieval_agent",
                    "Transaction investigation retrieved supporting documents from document metadata.",
                )

            for source in transaction_result.get("sources", []):
                self.traceability_service.record_source(traceability, source)

            for item in transaction_result.get("structured_evidence", []):
                reference = item.get("transaction_id") or item.get("vendor_id") or item.get("contract_id") or item.get("finding_id")
                self.traceability_service.record_evidence(
                    traceability,
                    {
                        "type": "structured",
                        "reference": reference,
                        "source": item.get("source_type", "transaction"),
                    },
                )

            for item in transaction_result.get("document_evidence", []):
                self.traceability_service.record_evidence(
                    traceability,
                    {
                        "type": "document",
                        "reference": item.get("document_id"),
                        "source": "document_metadata",
                    },
                )

            response_contract["traceability"] = traceability
            response_contract = self.response_composer.compose(response_contract)
            response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
            return response_contract

        investigation_plan = self.investigation_planner.plan(
            query,
            intent={},
            available_agents=None,
            investigation_context={
                "query": query,
                "page": page,
                "page_size": page_size,
            },
        )
        if investigation_plan.get("investigation_type") != "unsupported":
            response_contract["investigation_plan"] = investigation_plan
            response_contract["entities_investigated"] = list(investigation_plan.get("entities_required", []))
            response_contract["entity_type"] = "investigation"

            self.traceability_service.record_agent(
                traceability,
                "investigation_planner",
                "Planner identified a cross-entity investigation scenario.",
            )
            for reason in investigation_plan.get("reasoning", []):
                self.traceability_service.record_reasoning(traceability, reason)

            orchestration = self.agent_orchestrator.run(
                query=query,
                investigation_plan=investigation_plan,
                structured_intent=response_contract.get("intent", {}),
                page=page,
                page_size=page_size,
            )
            response_contract.update(orchestration)
            response_contract["execution_metadata"] = list(orchestration.get("execution_metadata", []))
            response_contract["intent"] = orchestration.get("structured_intent", response_contract.get("intent", {}))
            traceability["execution_metadata"] = response_contract["execution_metadata"]

            for step in response_contract["execution_metadata"]:
                agent_name = str(step.get("agent") or "").strip()
                reason_selected = str(step.get("reason_selected") or "").strip()
                if agent_name:
                    self.traceability_service.record_agent(
                        traceability,
                        agent_name,
                        reason_selected or "Planner-selected investigation step.",
                    )
                outputs = step.get("outputs", {}) if isinstance(step.get("outputs", {}), dict) else {}
                if agent_name == "transaction_agent" and outputs.get("success"):
                    self.traceability_service.record_source(traceability, "transaction_master")
                    self.traceability_service.record_reasoning(
                        traceability,
                        f"Transaction agent returned {outputs.get('result_count', 0)} record(s).",
                    )
                elif agent_name in {"vendor_agent", "vendor_investigation_agent"} and outputs.get("success"):
                    self.traceability_service.record_source(traceability, "vendor")
                    self.traceability_service.record_reasoning(
                        traceability,
                        f"Vendor investigation executed for {len(outputs.get('vendor_ids', []))} vendor(s).",
                    )
                elif agent_name == "document_retrieval_agent" and outputs.get("success"):
                    self.traceability_service.record_source(traceability, "document_metadata")
                    for source in outputs.get("sources", []):
                        self.traceability_service.record_source(traceability, source)
                    self.traceability_service.record_reasoning(
                        traceability,
                        f"Document retrieval returned {outputs.get('document_count', 0)} related record(s).",
                    )

            transaction_rows = list(response_contract.get("transaction_rows", []))
            vendor_investigations = list(response_contract.get("vendor_investigations", []))

            response_contract["structured_evidence"] = list(response_contract.get("structured_evidence", []))
            response_contract["document_evidence"] = list(response_contract.get("document_evidence", []))
            response_contract["sources"] = list(response_contract.get("sources", []))

            risk = self.response_composer.risk_scoring_service.score(
                finding={
                    "finding_title": "Cross-Entity Investigation",
                    "finding_summary": query,
                },
                structured_evidence=response_contract["structured_evidence"],
                document_evidence=response_contract["document_evidence"],
            )

            response_contract["investigation_metrics"] = self._build_investigation_metrics(
                transaction_rows=transaction_rows,
                document_rows=response_contract["document_evidence"],
                vendor_investigations=vendor_investigations,
            )
            response_contract["investigation_summary"] = self._build_investigation_summary(
                query=query,
                plan=investigation_plan,
                transaction_rows=transaction_rows,
                vendor_investigations=vendor_investigations,
                risk_rating=risk["risk_rating"],
            )
            response_contract["key_findings"] = self._build_scenario_key_findings(
                transaction_rows=transaction_rows,
                document_rows=response_contract["document_evidence"],
                vendor_investigations=vendor_investigations,
                planner_reasoning=investigation_plan.get("reasoning", []),
                existing_key_findings=list(response_contract.get("key_findings", [])),
            )
            response_contract["top_supporting_evidence"] = self._rank_documents(response_contract["document_evidence"])[:5]
            response_contract["supporting_evidence"] = self._build_scenario_supporting_evidence(
                transaction_rows=transaction_rows,
                vendor_investigations=vendor_investigations,
                document_rows=response_contract["document_evidence"],
            )
            response_contract["recommendations"] = self._build_scenario_recommendations(
                transaction_rows=transaction_rows,
                vendor_investigations=vendor_investigations,
                existing_recommendations=list(response_contract.get("recommendations", [])),
            )
            response_contract["supporting_documents"] = response_contract["document_evidence"]
            response_contract["finding"] = {
                "finding_title": "Cross-Entity Investigation",
                "finding_summary": response_contract["investigation_summary"],
                "evidence_summary": " ".join(response_contract["key_findings"]) if response_contract["key_findings"] else "",
                "recommendation": response_contract["recommendations"][0] if response_contract["recommendations"] else "",
                "supporting_documents": response_contract["supporting_documents"],
            }

            response_contract["risk_rating"] = risk["risk_rating"]
            response_contract["risk_score"] = risk["risk_score"]
            response_contract["risk_drivers"] = risk["risk_drivers"]

            response_contract["traceability"] = traceability
            response_contract = self.response_composer.compose(response_contract)
            response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
            return response_contract

        vendor_id = self.vendor_investigation_service.extract_vendor_id(query)
        if self.vendor_investigation_service.matches_vendor_investigation(query) and vendor_id:
            self.traceability_service.record_reasoning(
                traceability,
                "Query matched the vendor investigation workflow.",
            )
            self.traceability_service.record_agent(
                traceability,
                "vendor_investigation_agent",
                "Query requested vendor investigation and contained a vendor identifier.",
            )

            vendor_result = self.vendor_investigation_service.investigate(query=query, vendor_id=vendor_id)
            response_contract.update(vendor_result)

            for reason in vendor_result.get("reasoning", []):
                self.traceability_service.record_reasoning(traceability, reason)

            if vendor_result.get("document_evidence"):
                self.traceability_service.record_agent(
                    traceability,
                    "document_retrieval_agent",
                    "Vendor investigation retrieved supporting documents from document metadata.",
                )

            for source in vendor_result.get("sources", []):
                self.traceability_service.record_source(traceability, source)

            for item in vendor_result.get("structured_evidence", []):
                reference = item.get("transaction_id") or item.get("contract_id") or item.get("finding_id") or item.get("vendor_id")
                self.traceability_service.record_evidence(
                    traceability,
                    {
                        "type": "structured",
                        "reference": reference,
                        "source": item.get("source_type", "vendor"),
                    },
                )

            for item in vendor_result.get("document_evidence", []):
                self.traceability_service.record_evidence(
                    traceability,
                    {
                        "type": "document",
                        "reference": item.get("document_id"),
                        "source": "document_metadata",
                    },
                )

            response_contract["traceability"] = traceability
            response_contract = self.response_composer.compose(response_contract)
            response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
            return response_contract

        structured_intent = self.intent_service.extract(
            query,
            domain="transaction",
            entity="transaction",
            allowed_intents=TRANSACTION_ALLOWED_INTENTS,
        )
        response_contract["intent"] = structured_intent
        self.traceability_service.record_reasoning(
            traceability,
            "Structured intent extracted for the transaction audit workflow.",
        )

        if not structured_intent.get("supported"):
            response_contract["success"] = False
            response_contract["finding"] = {
                "title": "Unsupported Query",
                "summary": "This query does not appear to be related to the supported audit workflow.",
                "category": "No Findings",
                "severity": "Low",
            }
            response_contract["final_response"] = response_contract["finding"]["summary"]
            self.traceability_service.record_reasoning(
                traceability,
                "Query was rejected because the extracted intent was unsupported.",
            )
            return self.response_composer.compose(response_contract)

        self.traceability_service.record_agent(
            traceability,
            "transaction_agent",
            "Structured intent mapped to transaction retrieval.",
        )

        transaction_result = execute_transaction_query(self.db, query, page=page, page_size=page_size)
        response_contract["structured_evidence"] = list(transaction_result.get("results", []))

        if not transaction_result.get("success", False):
            response_contract["success"] = False
            response_contract["message"] = transaction_result.get("message")
            response_contract["finding"] = {
                "title": "Transaction Retrieval Failed",
                "summary": transaction_result.get("message") or "Transaction retrieval failed.",
                "category": "No Findings",
                "severity": "Low",
            }
            self.traceability_service.record_reasoning(
                traceability,
                "Transaction retrieval did not return a supported result set.",
            )
            return self.response_composer.compose(response_contract)

        self.traceability_service.record_source(traceability, "transaction_master")
        self.traceability_service.record_reasoning(
            traceability,
            f"Transaction agent returned {len(response_contract['structured_evidence'])} record(s).",
        )

        document_result = self.document_agent.retrieve(
            query=query,
            structured_intent=structured_intent,
            transaction_results=response_contract["structured_evidence"],
        )
        response_contract["document_evidence"] = list(document_result.get("documents", []))

        if response_contract["document_evidence"]:
            self.traceability_service.record_agent(
                traceability,
                "document_retrieval_agent",
                "Related document metadata was available for the retrieved structured records.",
            )
            self.traceability_service.record_source(traceability, "document_metadata")
            for source in document_result.get("sources", []):
                self.traceability_service.record_source(traceability, source)
            self.traceability_service.record_reasoning(
                traceability,
                f"Document retrieval returned {len(response_contract['document_evidence'])} related record(s).",
            )

        aggregated_sources = ["transaction_master"]
        if response_contract["document_evidence"]:
            aggregated_sources.append("document_metadata")
        aggregated_sources.extend(document_result.get("sources", []))

        aggregator_output = self.evidence_aggregator.aggregate(
            structured_evidence=response_contract["structured_evidence"],
            document_evidence=response_contract["document_evidence"],
            sources=aggregated_sources,
        )
        response_contract["structured_evidence"] = aggregator_output["structured_evidence"]
        response_contract["document_evidence"] = aggregator_output["document_evidence"]
        response_contract["sources"] = aggregator_output["sources"]

        self.traceability_service.record_reasoning(
            traceability,
            "Deterministic finding generation will summarize the aggregated evidence.",
        )

        for source in response_contract["sources"]:
            self.traceability_service.record_source(traceability, source)

        for item in response_contract["structured_evidence"]:
            self.traceability_service.record_evidence(
                traceability,
                {
                    "type": "structured",
                    "reference": item.get("transaction_id"),
                    "source": "transaction_master",
                },
            )

        for item in response_contract["document_evidence"]:
            self.traceability_service.record_evidence(
                traceability,
                {
                    "type": "document",
                    "reference": item.get("document_id"),
                    "source": "document_metadata",
                },
            )

        response_contract = self.response_composer.compose(response_contract)
        response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
        return response_contract

    def _top_vendor_ids(self, transaction_rows: list[dict[str, Any]], limit: int = 3) -> list[str]:
        counts: dict[str, int] = {}
        for row in transaction_rows:
            vendor_id = row.get("vendor_id")
            if vendor_id:
                counts[str(vendor_id)] = counts.get(str(vendor_id), 0) + 1
        return [vendor_id for vendor_id, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]

    def _dedupe_records(self, records: list[dict[str, Any]], *, fields: tuple[str, ...]) -> list[dict[str, Any]]:
        seen: set[tuple[Any, ...]] = set()
        deduped: list[dict[str, Any]] = []
        for record in records:
            signature = tuple(record.get(field) for field in fields)
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(record)
        return deduped

    def _rank_documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        priority = {
            "investigation_reports": 1,
            "emails": 2,
            "audit_reports": 3,
            "policies": 4,
            "contracts": 5,
            "approval_emails": 6,
            "meeting_minutes": 7,
            "sop_documents": 8,
        }
        ranked = sorted(
            enumerate(documents),
            key=lambda item: (
                priority.get(str(item[1].get("document_category", "")).strip().lower(), 99),
                -float(item[1].get("relevance_score", 0) or 0),
                item[0],
            ),
        )
        return [
            {
                "document_id": document.get("document_id"),
                "document_type": document.get("document_type"),
                "document_category": document.get("document_category"),
                "linked_transaction": document.get("linked_transaction"),
                "reason_selected": document.get("reason_selected"),
                "content_snippet": document.get("content_snippet", ""),
                "chunk_id": document.get("chunk_id"),
                "relevance_score": document.get("relevance_score"),
                "priority": priority.get(str(document.get("document_category", "")).strip().lower(), 99),
            }
            for _, document in ranked
        ]

    def _build_investigation_metrics(
        self,
        *,
        transaction_rows: list[dict[str, Any]],
        document_rows: list[dict[str, Any]],
        vendor_investigations: list[dict[str, Any]],
    ) -> dict[str, int]:
        flagged_transactions = sum(1 for row in transaction_rows if str(row.get("status", "")).upper() == "FLAGGED")
        return {
            "transactions_reviewed": len(transaction_rows),
            "contracts_reviewed": sum(len(item.get("structured_evidence", [])) for item in vendor_investigations),
            "documents_reviewed": len(document_rows),
            "flagged_transactions": flagged_transactions,
        }

    def _build_investigation_summary(
        self,
        *,
        query: str,
        plan: dict[str, Any],
        transaction_rows: list[dict[str, Any]],
        vendor_investigations: list[dict[str, Any]],
        risk_rating: str,
    ) -> str:
        investigation_type = plan.get("investigation_type", "investigation")
        vendor_ids = self._top_vendor_ids(transaction_rows, limit=3)
        vendor_text = ", ".join(vendor_ids) if vendor_ids else "no vendor identifiers were surfaced"
        vendor_summary_bits = [item.get("vendor_summary", "") for item in vendor_investigations if item.get("vendor_summary")]
        vendor_summary = " ".join(vendor_summary_bits[:2])
        summary = (
            f"The query was handled as a {investigation_type.replace('_', ' ')}. "
            f"{len(transaction_rows)} transaction(s) were reviewed and vendor activity was analyzed across {vendor_text}."
        )
        if vendor_summary:
            summary += f" {vendor_summary}"
        if risk_rating:
            summary += f" Overall risk assessment: {risk_rating}."
        return summary

    def _build_scenario_key_findings(
        self,
        *,
        transaction_rows: list[dict[str, Any]],
        document_rows: list[dict[str, Any]],
        vendor_investigations: list[dict[str, Any]],
        planner_reasoning: list[str],
        existing_key_findings: list[str],
    ) -> list[str]:
        key_findings = list(existing_key_findings)
        flagged_count = sum(1 for row in transaction_rows if str(row.get("status", "")).upper() == "FLAGGED")
        high_risk_count = sum(1 for row in transaction_rows if float(row.get("risk_score") or 0) > 0.8)
        if flagged_count:
            key_findings.append(f"{flagged_count} flagged transaction(s) identified in the scenario review.")
        if high_risk_count:
            key_findings.append(f"{high_risk_count} transaction(s) exceeded risk threshold 0.8.")
        if document_rows:
            key_findings.append(f"{len(document_rows)} supporting document(s) were linked to the scenario.")
        if vendor_investigations:
            key_findings.append(f"{len(vendor_investigations)} vendor investigation(s) were executed for follow-up.")
        if planner_reasoning:
            key_findings.extend(planner_reasoning[:2])
        return list(dict.fromkeys(key_findings))

    def _build_scenario_supporting_evidence(
        self,
        *,
        transaction_rows: list[dict[str, Any]],
        vendor_investigations: list[dict[str, Any]],
        document_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        evidence = [
            {
                "summary": f"{len(transaction_rows)} transaction(s) reviewed during the scenario investigation.",
            },
            {
                "summary": f"{len(document_rows)} supporting document(s) were linked.",
            },
        ]
        if vendor_investigations:
            vendor_ids = [item.get("entity_id") for item in vendor_investigations if item.get("entity_id")]
            if vendor_ids:
                evidence.append(
                    {
                        "summary": "Vendor follow-up was performed for: " + ", ".join(vendor_ids[:3]) + ".",
                    }
                )
        return evidence

    def _build_scenario_recommendations(
        self,
        *,
        transaction_rows: list[dict[str, Any]],
        vendor_investigations: list[dict[str, Any]],
        existing_recommendations: list[str],
    ) -> list[str]:
        recommendations = list(existing_recommendations)
        if any(str(row.get("status", "")).upper() == "FLAGGED" for row in transaction_rows):
            recommendations.append("Review approval chain.")
        if any(float(row.get("risk_score") or 0) > 0.8 for row in transaction_rows):
            recommendations.append("Validate supporting documentation.")
        if vendor_investigations:
            recommendations.append("Conduct manual audit review across the linked vendors.")
        if not recommendations:
            recommendations.append("Continue periodic monitoring.")
        return list(dict.fromkeys(recommendations))
