from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.governance_audit_service import GovernanceAuditService
from app.services.document_retrieval_agent_service import DocumentRetrievalAgent
from app.services.control_testing_service import ControlTestingService
from app.services.evidence_aggregator_service import EvidenceAggregatorService
from app.services.investigation_planner_service import InvestigationPlannerService
from app.services.langfuse_service import LangfuseService
from app.services.llm_router_service import StructuredIntentService
from app.services.query_router_service import QueryRoutingService
from app.services.response_composer_service import ResponseComposerService
from app.services.source_router_service import SourceRouterService
from app.services.traceability_service import TraceabilityService
from app.services.vendor_investigation_service import VendorInvestigationService
from app.services.transaction_investigation_service import TransactionInvestigationService
from app.services.transaction_service import TRANSACTION_ALLOWED_INTENTS, execute_transaction_query


class AuditWorkflowService:
    def __init__(
        self,
        db: Session,
        *,
        audit_db: Session | None = None,
        query_router: QueryRoutingService | None = None,
        intent_service: StructuredIntentService | None = None,
        investigation_planner: InvestigationPlannerService | None = None,
        traceability_service: TraceabilityService | None = None,
        langfuse_service: LangfuseService | None = None,
        source_router: SourceRouterService | None = None,
        document_agent: DocumentRetrievalAgent | None = None,
        vendor_investigation_service: VendorInvestigationService | None = None,
        transaction_investigation_service: TransactionInvestigationService | None = None,
        evidence_aggregator: EvidenceAggregatorService | None = None,
        response_composer: ResponseComposerService | None = None,
    ) -> None:
        self.db = db
        self.audit_db = audit_db or db
        self.query_router = query_router or QueryRoutingService()
        self.intent_service = intent_service or StructuredIntentService()
        self.investigation_planner = investigation_planner or InvestigationPlannerService()
        self.traceability_service = traceability_service or TraceabilityService()
        self.langfuse_service = langfuse_service or LangfuseService()
        self.source_router = source_router or SourceRouterService()
        self.document_agent = document_agent or DocumentRetrievalAgent(db)
        self.control_testing_service = ControlTestingService(db)
        self.vendor_investigation_service = vendor_investigation_service or VendorInvestigationService(db)
        self.transaction_investigation_service = transaction_investigation_service or TransactionInvestigationService(db)
        self.evidence_aggregator = evidence_aggregator or EvidenceAggregatorService()
        self.response_composer = response_composer or ResponseComposerService()

    def run(
        self,
        *,
        query: str,
        page: int = 1,
        page_size: int = 10,
        actor_user_id: str | None = None,
        attached_document_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        traceability = self.traceability_service.initialize()
        governance_audit = GovernanceAuditService(self.audit_db)
        governance_audit.record_event(
            actor_user_id=actor_user_id,
            action_type="audit_query_started",
            entity_type="audit_query",
            severity="info",
            summary=f"Audit query started: {query[:200]}",
            after_state={"query": query, "page": page, "page_size": page_size},
        )
        self.audit_db.commit()

        trace_context = self.langfuse_service.start_trace(
            name="audit_query",
            input_payload={"query": query, "page": page, "page_size": page_size},
            metadata={"agent_runtime": self.langfuse_service.settings.agent_runtime},
        )
        self.traceability_service.attach_langfuse(
            traceability,
            enabled=self.langfuse_service.is_enabled(),
            trace_id=trace_context.trace_id,
            trace_url=trace_context.as_traceability().get("trace_url"),
            session_id=trace_context.as_traceability().get("session_id"),
        )

        response_contract: dict[str, Any] = {
            "success": True,
            "query": query,
            "intent": {},
            "routing_decision": {},
            "source_route": {},
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
            "workflow_automation": {},
            "message": None,
        }

        routing_decision = self.query_router.route(query, trace_context=trace_context)
        response_contract["routing_decision"] = routing_decision
        self.traceability_service.record_agent(
            traceability,
            "query_router",
            routing_decision.get("reason", "Query routed to the next workflow step."),
        )
        self.traceability_service.record_reasoning(
            traceability,
            f"Query router selected {routing_decision.get('agent', 'general_agent')} with confidence {float(routing_decision.get('confidence', 0) or 0):.2f}.",
        )
        if routing_decision.get("escalate_to_planner"):
            self.traceability_service.record_reasoning(
                traceability,
                "Routing decision marked this query for planner escalation because it was ambiguous or multi-domain.",
            )
        governance_audit.record_router_decision(
            actor_user_id=actor_user_id,
            query=query,
            routing_decision=routing_decision,
            selected_agents=[],
        )
        self.audit_db.commit()

        source_route = self.source_router.route(
            query,
            attached_document_ids=attached_document_ids or [],
            memory_context={
                "query": query,
                "routing_decision": routing_decision,
                "attached_document_ids": attached_document_ids or [],
            },
            trace_context=trace_context,
        )
        response_contract["source_route"] = source_route
        self.traceability_service.record_agent(
            traceability,
            "source_router",
            source_route.get("reason", "Source routing selected the most likely evidence source."),
        )
        self.traceability_service.record_reasoning(
            traceability,
            f"Source router selected {source_route.get('source_mode', 'unknown')} with confidence {float(source_route.get('confidence', 0) or 0):.2f}.",
        )

        if self._looks_like_control_testing(query):
            self._run_control_testing(
                response_contract=response_contract,
                traceability=traceability,
                trace_context=trace_context,
                governance_audit=governance_audit,
                actor_user_id=actor_user_id,
                query=query,
                page=page,
                page_size=page_size,
                routing_decision=routing_decision,
            )
            return response_contract

        transaction_id = self.transaction_investigation_service.extract_transaction_id(query)
        if self.transaction_investigation_service.matches_transaction_investigation(query) and transaction_id:
            self._run_transaction_investigation(
                response_contract=response_contract,
                traceability=traceability,
                trace_context=trace_context,
                governance_audit=governance_audit,
                actor_user_id=actor_user_id,
                query=query,
                transaction_id=transaction_id,
                page=page,
                page_size=page_size,
                routing_decision=routing_decision,
            )
            return response_contract

        if source_route.get("source_mode") == "pdf_only":
            self._run_document_investigation(
                response_contract=response_contract,
                traceability=traceability,
                trace_context=trace_context,
                governance_audit=governance_audit,
                actor_user_id=actor_user_id,
                query=query,
                attached_document_ids=attached_document_ids or [],
            )
            return response_contract

        if source_route.get("source_mode") == "both":
            self._run_hybrid_source_investigation(
                response_contract=response_contract,
                traceability=traceability,
                trace_context=trace_context,
                governance_audit=governance_audit,
                actor_user_id=actor_user_id,
                query=query,
                page=page,
                page_size=page_size,
                attached_document_ids=attached_document_ids or [],
                routing_decision=routing_decision,
                source_route=source_route,
            )
            return response_contract

        investigation_plan = self.investigation_planner.plan(
            query,
            intent={},
            available_agents=None,
            investigation_context={
                "query": query,
                "page": page,
                "page_size": page_size,
                "routing_decision": routing_decision,
                "attached_document_ids": attached_document_ids or [],
            },
            trace_context=trace_context,
        )
        if investigation_plan.get("investigation_type") != "unsupported":
            self._run_cross_entity_investigation(
                response_contract=response_contract,
                traceability=traceability,
                trace_context=trace_context,
                governance_audit=governance_audit,
                actor_user_id=actor_user_id,
                query=query,
                page=page,
                page_size=page_size,
                routing_decision=routing_decision,
                investigation_plan=investigation_plan,
            )
            return response_contract

        vendor_id = self.vendor_investigation_service.extract_vendor_id(query)
        if self.vendor_investigation_service.matches_vendor_investigation(query) and vendor_id:
            self._run_vendor_investigation(
                response_contract=response_contract,
                traceability=traceability,
                trace_context=trace_context,
                governance_audit=governance_audit,
                actor_user_id=actor_user_id,
                query=query,
                vendor_id=vendor_id,
                routing_decision=routing_decision,
            )
            return response_contract

        if self._looks_like_document_request(query):
            self._run_document_investigation(
                response_contract=response_contract,
                traceability=traceability,
                trace_context=trace_context,
                governance_audit=governance_audit,
                actor_user_id=actor_user_id,
                query=query,
                attached_document_ids=attached_document_ids or [],
            )
            return response_contract

        structured_intent = self.intent_service.extract(
            query,
            domain="transaction",
            entity="transaction",
            allowed_intents=TRANSACTION_ALLOWED_INTENTS,
            trace_context=trace_context,
        )
        response_contract["intent"] = structured_intent
        self.traceability_service.record_reasoning(
            traceability,
            "Structured intent extracted for the transaction audit workflow.",
        )

        if not structured_intent.get("supported"):
            if routing_decision.get("escalate_to_planner"):
                response_contract["success"] = False
                response_contract["finding"] = {
                    "title": "Insufficient Evidence",
                    "summary": "I could not identify sufficient structured or document evidence to investigate this request.",
                    "category": "No Findings",
                    "severity": "Low",
                }
                response_contract["final_response"] = response_contract["finding"]["summary"]
                self.traceability_service.record_reasoning(
                    traceability,
                    "Structured intent was unsupported, but the router escalation path did not produce a clear investigation target.",
                )
                self._finalize_response(
                    response_contract=response_contract,
                    traceability=traceability,
                    trace_context=trace_context,
                    governance_audit=governance_audit,
                    actor_user_id=actor_user_id,
                    query=query,
                    result="insufficient_evidence",
                )
                return response_contract

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
            self._finalize_response(
                response_contract=response_contract,
                traceability=traceability,
                trace_context=trace_context,
                governance_audit=governance_audit,
                actor_user_id=actor_user_id,
                query=query,
                result="unsupported_query",
            )
            return response_contract

        self.traceability_service.record_agent(
            traceability,
            "transaction_agent",
            "Structured intent mapped to transaction retrieval.",
        )

        transaction_result = execute_transaction_query(self.db, query, page=page, page_size=page_size, trace_context=trace_context)
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
            self._finalize_response(
                response_contract=response_contract,
                traceability=traceability,
                trace_context=trace_context,
                governance_audit=governance_audit,
                actor_user_id=actor_user_id,
                query=query,
                result="transaction_retrieval_failed",
            )
            return response_contract

        self.traceability_service.record_source(traceability, "transaction_master")
        self.traceability_service.record_reasoning(
            traceability,
            f"Transaction agent returned {len(response_contract['structured_evidence'])} record(s).",
        )

        document_result = self.document_agent.retrieve(
            query=query,
            structured_intent=structured_intent,
            transaction_results=response_contract["structured_evidence"],
            attached_document_ids=attached_document_ids or [],
            trace_context=trace_context,
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
            trace_context=trace_context,
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

        response_contract["execution_metadata"] = [
            {
                "agent": "query_router",
                "reason_selected": routing_decision.get("reason", "Query routed to the next workflow step."),
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query},
                "outputs": {
                    "selected_agent": routing_decision.get("agent"),
                    "confidence": routing_decision.get("confidence"),
                },
            },
            {
                "agent": "source_router",
                "reason_selected": source_route.get("reason", "Source routing selected the most likely evidence source."),
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "attached_document_ids": attached_document_ids},
                "outputs": {
                    "source_mode": source_route.get("source_mode"),
                    "confidence": source_route.get("confidence"),
                    "decision_source": source_route.get("decision_source"),
                },
            },
            {
                "agent": "transaction_agent",
                "reason_selected": "Transaction workflow was selected for the current audit query.",
                "status": "completed" if response_contract["structured_evidence"] else "completed_with_no_rows",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "page": page, "page_size": page_size},
                "outputs": {
                    "result_count": len(response_contract["structured_evidence"]),
                    "success": bool(response_contract["structured_evidence"]),
                },
            },
            {
                "agent": "document_retrieval_agent",
                "reason_selected": "Related document evidence was retrieved for the transaction results.",
                "status": "completed" if response_contract["document_evidence"] else "completed_with_no_rows",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "transaction_count": len(response_contract["structured_evidence"])},
                "outputs": {
                    "document_count": len(response_contract["document_evidence"]),
                    "sources": list(response_contract.get("sources", [])),
                },
            },
            {
                "agent": "evidence_aggregator",
                "reason_selected": "Combine structured and document evidence into a single audit package.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "structured_count": len(response_contract["structured_evidence"]),
                    "document_count": len(response_contract["document_evidence"]),
                },
                "outputs": {
                    "structured_count": len(response_contract["structured_evidence"]),
                    "document_count": len(response_contract["document_evidence"]),
                    "sources": list(response_contract.get("sources", [])),
                },
            },
        ]

        response_contract = self.response_composer.compose(response_contract, trace_context=trace_context)
        response_contract["execution_metadata"].append(
            {
                "agent": "response_composer",
                "reason_selected": "Generate the final audit narrative and evaluation.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "structured_count": len(response_contract.get("structured_evidence", [])),
                    "document_count": len(response_contract.get("document_evidence", [])),
                },
                "outputs": {
                    "risk_rating": response_contract.get("risk_rating"),
                    "finding_title": response_contract.get("finding", {}).get("title"),
                },
            }
        )
        traceability["execution_metadata"] = list(response_contract["execution_metadata"])
        response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
        self._finalize_response(
            response_contract=response_contract,
            traceability=traceability,
            trace_context=trace_context,
            governance_audit=governance_audit,
            actor_user_id=actor_user_id,
            query=query,
            result="transaction_query",
        )
        return response_contract

    def _run_hybrid_source_investigation(
        self,
        *,
        response_contract: dict[str, Any],
        traceability: dict[str, Any],
        trace_context: Any,
        governance_audit: GovernanceAuditService,
        actor_user_id: str | None,
        query: str,
        page: int,
        page_size: int,
        attached_document_ids: list[str],
        routing_decision: dict[str, Any],
        source_route: dict[str, Any],
    ) -> None:
        self.traceability_service.record_reasoning(
            traceability,
            "Source router selected both PDF and database evidence, so both retrieval paths will be executed.",
        )
        self.traceability_service.record_agent(
            traceability,
            "transaction_agent",
            "Hybrid routing requested database retrieval alongside document evidence.",
        )
        self.traceability_service.record_agent(
            traceability,
            "document_retrieval_agent",
            "Hybrid routing requested document retrieval alongside database evidence.",
        )

        tx_span = trace_context.begin_span(
            "transaction_agent",
            input_payload={"query": query, "page": page, "page_size": page_size},
            metadata={"service": "AuditWorkflowService", "route": "both"},
        )
        transaction_result = execute_transaction_query(
            self.db,
            query,
            page=page,
            page_size=page_size,
            trace_context=trace_context,
        )
        tx_span.finish(
            output={
                "success": transaction_result.get("success"),
                "row_count": len(transaction_result.get("results", [])),
            },
            metadata={
                "row_count": len(transaction_result.get("results", [])),
                "sources": transaction_result.get("sources", []),
            },
        )

        structured_evidence = list(transaction_result.get("results", [])) if transaction_result.get("success", False) else []
        response_contract["intent"] = self.intent_service.extract(
            query,
            domain="transaction",
            entity="transaction",
            allowed_intents=TRANSACTION_ALLOWED_INTENTS,
            trace_context=trace_context,
        )
        response_contract["structured_evidence"] = structured_evidence

        if structured_evidence:
            self.traceability_service.record_source(traceability, "transaction_master")
            self.traceability_service.record_reasoning(
                traceability,
                f"Hybrid routing returned {len(structured_evidence)} transaction record(s).",
            )
        else:
            self.traceability_service.record_reasoning(
                traceability,
                "Hybrid routing did not return structured transaction records, so the answer will rely more heavily on document evidence if available.",
            )

        doc_span = trace_context.begin_span(
            "document_retrieval_agent",
            input_payload={
                "query": query,
                "transaction_count": len(structured_evidence),
                "attached_document_ids": attached_document_ids,
            },
            metadata={"service": "AuditWorkflowService", "route": "both"},
        )
        document_result = self.document_agent.retrieve(
            query=query,
            structured_intent=response_contract.get("intent", {}),
            transaction_results=structured_evidence,
            attached_document_ids=attached_document_ids,
            trace_context=trace_context,
        )
        response_contract["document_evidence"] = list(document_result.get("documents", []))
        doc_span.finish(
            output={
                "document_count": len(response_contract["document_evidence"]),
                "sources": document_result.get("sources", []),
            },
            metadata={
                "document_count": len(response_contract["document_evidence"]),
                "sources": document_result.get("sources", []),
            },
        )

        if response_contract["document_evidence"]:
            self.traceability_service.record_source(traceability, "document_metadata")
            for source in document_result.get("sources", []):
                self.traceability_service.record_source(traceability, source)
            self.traceability_service.record_reasoning(
                traceability,
                f"Hybrid routing returned {len(response_contract['document_evidence'])} supporting document(s).",
            )

        aggregated_sources = ["transaction_master"]
        if response_contract["document_evidence"]:
            aggregated_sources.append("document_metadata")
        aggregated_sources.extend(document_result.get("sources", []))

        aggregator_output = self.evidence_aggregator.aggregate(
            structured_evidence=response_contract["structured_evidence"],
            document_evidence=response_contract["document_evidence"],
            sources=aggregated_sources,
            trace_context=trace_context,
        )
        response_contract["structured_evidence"] = aggregator_output["structured_evidence"]
        response_contract["document_evidence"] = aggregator_output["document_evidence"]
        response_contract["sources"] = aggregator_output["sources"]
        response_contract["supporting_documents"] = response_contract["document_evidence"]
        response_contract["execution_metadata"] = [
            {
                "agent": "query_router",
                "reason_selected": routing_decision.get("reason", "Query routed to the next workflow step."),
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query},
                "outputs": {
                    "selected_agent": routing_decision.get("agent"),
                    "confidence": routing_decision.get("confidence"),
                },
            },
            {
                "agent": "source_router",
                "reason_selected": source_route.get("reason", "Source routing selected the most likely evidence source."),
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "attached_document_ids": attached_document_ids},
                "outputs": {
                    "source_mode": source_route.get("source_mode"),
                    "confidence": source_route.get("confidence"),
                    "decision_source": source_route.get("decision_source"),
                },
            },
            {
                "agent": "transaction_agent",
                "reason_selected": "Hybrid routing requested database retrieval alongside document evidence.",
                "status": "completed" if structured_evidence else "completed_with_no_rows",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "page": page, "page_size": page_size},
                "outputs": {
                    "result_count": len(structured_evidence),
                    "success": bool(structured_evidence),
                },
            },
            {
                "agent": "document_retrieval_agent",
                "reason_selected": "Hybrid routing requested document retrieval alongside database evidence.",
                "status": "completed" if response_contract["document_evidence"] else "completed_with_no_docs",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "attached_document_ids": attached_document_ids},
                "outputs": {
                    "document_count": len(response_contract["document_evidence"]),
                    "sources": document_result.get("sources", []),
                },
            },
            {
                "agent": "evidence_aggregator",
                "reason_selected": "Combine database and document evidence into one response.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "structured_count": len(response_contract["structured_evidence"]),
                    "document_count": len(response_contract["document_evidence"]),
                },
                "outputs": {
                    "structured_count": len(response_contract["structured_evidence"]),
                    "document_count": len(response_contract["document_evidence"]),
                    "source_count": len(response_contract["sources"]),
                },
            },
        ]
        traceability["execution_metadata"] = list(response_contract["execution_metadata"])

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

        response_contract["risk_rating"] = response_contract.get("risk_rating", "LOW")
        response_contract["risk_score"] = response_contract.get("risk_score", 0)
        response_contract["risk_drivers"] = response_contract.get("risk_drivers", [])
        response_contract["success"] = bool(response_contract["structured_evidence"] or response_contract["document_evidence"])
        if not response_contract["success"]:
            response_contract["finding"] = {
                "title": "Insufficient Evidence",
                "summary": "I could not identify sufficient structured or document evidence to investigate this request.",
                "category": "No Findings",
                "severity": "Low",
            }
            response_contract["final_response"] = response_contract["finding"]["summary"]

        response_contract["traceability"] = traceability
        response_contract = self.response_composer.compose(response_contract, trace_context=trace_context)
        response_contract["execution_metadata"].append(
            {
                "agent": "response_composer",
                "reason_selected": "Generate the final audit narrative and evaluation.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "structured_count": len(response_contract.get("structured_evidence", [])),
                    "document_count": len(response_contract.get("document_evidence", [])),
                },
                "outputs": {
                    "risk_rating": response_contract.get("risk_rating"),
                    "finding_title": response_contract.get("finding", {}).get("title"),
                },
            }
        )
        traceability["execution_metadata"] = list(response_contract["execution_metadata"])
        response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
        self._finalize_response(
            response_contract=response_contract,
            traceability=traceability,
            trace_context=trace_context,
            governance_audit=governance_audit,
            actor_user_id=actor_user_id,
            query=query,
            result="hybrid_query",
        )

    def _run_transaction_investigation(
        self,
        *,
        response_contract: dict[str, Any],
        traceability: dict[str, Any],
        trace_context: Any,
        governance_audit: GovernanceAuditService,
        actor_user_id: str | None,
        query: str,
        transaction_id: str,
        page: int,
        page_size: int,
        routing_decision: dict[str, Any],
    ) -> None:
        self.traceability_service.record_reasoning(traceability, "Query matched the transaction investigation workflow.")
        self.traceability_service.record_agent(
            traceability,
            "transaction_investigation_agent",
            "Query requested transaction investigation and contained a transaction identifier.",
        )
        tx_span = trace_context.begin_span(
            "transaction_investigation_agent",
            input_payload={"query": query, "transaction_id": transaction_id},
            metadata={"service": "AuditWorkflowService"},
        )
        transaction_result = self.transaction_investigation_service.investigate(
            query=query,
            transaction_id=transaction_id,
            trace_context=trace_context,
        )
        tx_span.finish(
            output={
                "success": transaction_result.get("success"),
                "risk_rating": transaction_result.get("risk_rating"),
                "transaction_count": len(transaction_result.get("structured_evidence", [])),
                "document_count": len(transaction_result.get("document_evidence", [])),
            },
            metadata={
                "transaction_count": len(transaction_result.get("structured_evidence", [])),
                "document_count": len(transaction_result.get("document_evidence", [])),
            },
        )
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

        response_contract["execution_metadata"] = [
            {
                "agent": "query_router",
                "reason_selected": routing_decision.get("reason", "Query routed to the next workflow step."),
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query},
                "outputs": {
                    "selected_agent": routing_decision.get("agent"),
                    "confidence": routing_decision.get("confidence"),
                },
            },
            {
                "agent": "source_router",
                "reason_selected": response_contract.get("source_route", {}).get(
                    "reason", "Source routing selected the most likely evidence source."
                ),
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query},
                "outputs": {
                    "source_mode": response_contract.get("source_route", {}).get("source_mode"),
                    "confidence": response_contract.get("source_route", {}).get("confidence"),
                    "decision_source": response_contract.get("source_route", {}).get("decision_source"),
                },
            },
            {
                "agent": "transaction_investigation_agent",
                "reason_selected": "Transaction investigation was requested for a specific transaction identifier.",
                "status": "completed" if transaction_result.get("success") else "completed_with_no_rows",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "transaction_id": transaction_id},
                "outputs": {
                    "risk_rating": transaction_result.get("risk_rating"),
                    "evidence_count": len(transaction_result.get("structured_evidence", [])),
                    "document_count": len(transaction_result.get("document_evidence", [])),
                },
            },
        ]
        if transaction_result.get("document_evidence"):
            response_contract["execution_metadata"].append(
                {
                    "agent": "document_retrieval_agent",
                    "reason_selected": "Supporting documents were retrieved for the transaction investigation.",
                    "status": "completed",
                    "started_at": self._now_iso(),
                    "ended_at": self._now_iso(),
                    "inputs": {"query": query, "transaction_id": transaction_id},
                    "outputs": {
                        "document_count": len(transaction_result.get("document_evidence", [])),
                        "sources": list(transaction_result.get("sources", [])),
                    },
                }
            )
        response_contract["execution_metadata"].append(
            {
                "agent": "evidence_aggregator",
                "reason_selected": "Combine structured and document evidence into a single audit package.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "structured_count": len(transaction_result.get("structured_evidence", [])),
                    "document_count": len(transaction_result.get("document_evidence", [])),
                },
                "outputs": {
                    "structured_count": len(transaction_result.get("structured_evidence", [])),
                    "document_count": len(transaction_result.get("document_evidence", [])),
                    "sources": list(transaction_result.get("sources", [])),
                },
            }
        )

        response_contract["traceability"] = traceability
        response_contract = self.response_composer.compose(response_contract, trace_context=trace_context)
        response_contract["execution_metadata"].append(
            {
                "agent": "response_composer",
                "reason_selected": "Generate the final audit narrative and evaluation.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "structured_count": len(response_contract.get("structured_evidence", [])),
                    "document_count": len(response_contract.get("document_evidence", [])),
                },
                "outputs": {
                    "risk_rating": response_contract.get("risk_rating"),
                    "finding_title": response_contract.get("finding", {}).get("title"),
                },
            }
        )
        traceability["execution_metadata"] = list(response_contract["execution_metadata"])
        response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
        self._finalize_response(
            response_contract=response_contract,
            traceability=traceability,
            trace_context=trace_context,
            governance_audit=governance_audit,
            actor_user_id=actor_user_id,
            query=query,
            result="transaction_investigation",
        )

    def _run_cross_entity_investigation(
        self,
        *,
        response_contract: dict[str, Any],
        traceability: dict[str, Any],
        trace_context: Any,
        governance_audit: GovernanceAuditService,
        actor_user_id: str | None,
        query: str,
        page: int,
        page_size: int,
        routing_decision: dict[str, Any],
        investigation_plan: dict[str, Any],
    ) -> None:
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

        orchestration_span = trace_context.begin_span(
            "investigation_orchestration",
            input_payload={
                "query": query,
                "investigation_plan": investigation_plan,
                "structured_intent": response_contract.get("intent", {}),
            },
            metadata={"service": "AuditWorkflowService"},
        )
        orchestration = self._run_adk_orchestrator(
            query=query,
            investigation_plan=investigation_plan,
            structured_intent=response_contract.get("intent", {}),
            page=page,
            page_size=page_size,
            trace_context=trace_context,
        )
        orchestration_span.finish(
            output={
                "success": orchestration.get("success"),
                "transaction_count": orchestration.get("transaction_result_count"),
                "document_count": orchestration.get("document_result_count"),
                "agents_used": orchestration.get("agents_used", []),
            },
            metadata={
                "transaction_count": orchestration.get("transaction_result_count"),
                "document_count": orchestration.get("document_result_count"),
            },
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
                self.traceability_service.record_reasoning(traceability, f"Transaction agent returned {outputs.get('result_count', 0)} record(s).")
            elif agent_name in {"vendor_agent", "vendor_investigation_agent"} and outputs.get("success"):
                self.traceability_service.record_source(traceability, "vendor")
                self.traceability_service.record_reasoning(traceability, f"Vendor investigation executed for {len(outputs.get('vendor_ids', []))} vendor(s).")
            elif agent_name == "document_retrieval_agent" and outputs.get("success"):
                self.traceability_service.record_source(traceability, "document_metadata")
                for source in outputs.get("sources", []):
                    self.traceability_service.record_source(traceability, source)
                self.traceability_service.record_reasoning(traceability, f"Document retrieval returned {outputs.get('document_count', 0)} related record(s).")

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
            trace_context=trace_context,
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
        response_contract = self.response_composer.compose(response_contract, trace_context=trace_context)
        response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
        self._finalize_response(
            response_contract=response_contract,
            traceability=traceability,
            trace_context=trace_context,
            governance_audit=governance_audit,
            actor_user_id=actor_user_id,
            query=query,
            result="investigation",
        )

    def _run_vendor_investigation(
        self,
        *,
        response_contract: dict[str, Any],
        traceability: dict[str, Any],
        trace_context: Any,
        governance_audit: GovernanceAuditService,
        actor_user_id: str | None,
        query: str,
        vendor_id: str,
        routing_decision: dict[str, Any],
    ) -> None:
        self.traceability_service.record_reasoning(traceability, "Query matched the vendor investigation workflow.")
        self.traceability_service.record_agent(
            traceability,
            "vendor_investigation_agent",
            "Query requested vendor investigation and contained a vendor identifier.",
        )
        vendor_span = trace_context.begin_span(
            "vendor_investigation_agent",
            input_payload={"query": query, "vendor_id": vendor_id},
            metadata={"service": "AuditWorkflowService"},
        )
        vendor_result = self.vendor_investigation_service.investigate(
            query=query,
            vendor_id=vendor_id,
            trace_context=trace_context,
        )
        vendor_span.finish(
            output={
                "success": vendor_result.get("success"),
                "risk_rating": vendor_result.get("risk_rating"),
                "transaction_count": len(vendor_result.get("structured_evidence", [])),
                "document_count": len(vendor_result.get("document_evidence", [])),
            },
            metadata={
                "transaction_count": len(vendor_result.get("structured_evidence", [])),
                "document_count": len(vendor_result.get("document_evidence", [])),
            },
        )
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

        response_contract["execution_metadata"] = [
            {
                "agent": "query_router",
                "reason_selected": routing_decision.get("reason", "Query routed to the next workflow step."),
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query},
                "outputs": {
                    "selected_agent": routing_decision.get("agent"),
                    "confidence": routing_decision.get("confidence"),
                },
            },
            {
                "agent": "source_router",
                "reason_selected": response_contract.get("source_route", {}).get(
                    "reason", "Source routing selected the most likely evidence source."
                ),
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query},
                "outputs": {
                    "source_mode": response_contract.get("source_route", {}).get("source_mode"),
                    "confidence": response_contract.get("source_route", {}).get("confidence"),
                    "decision_source": response_contract.get("source_route", {}).get("decision_source"),
                },
            },
            {
                "agent": "vendor_investigation_agent",
                "reason_selected": "Vendor investigation was requested for a specific vendor identifier.",
                "status": "completed" if vendor_result.get("success") else "completed_with_no_rows",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "vendor_id": vendor_id},
                "outputs": {
                    "risk_rating": vendor_result.get("risk_rating"),
                    "evidence_count": len(vendor_result.get("structured_evidence", [])),
                    "document_count": len(vendor_result.get("document_evidence", [])),
                },
            },
        ]
        if vendor_result.get("document_evidence"):
            response_contract["execution_metadata"].append(
                {
                    "agent": "document_retrieval_agent",
                    "reason_selected": "Supporting documents were retrieved for the vendor investigation.",
                    "status": "completed",
                    "started_at": self._now_iso(),
                    "ended_at": self._now_iso(),
                    "inputs": {"query": query, "vendor_id": vendor_id},
                    "outputs": {
                        "document_count": len(vendor_result.get("document_evidence", [])),
                        "sources": list(vendor_result.get("sources", [])),
                    },
                }
            )
        response_contract["execution_metadata"].append(
            {
                "agent": "evidence_aggregator",
                "reason_selected": "Combine structured and document evidence into a single audit package.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "structured_count": len(vendor_result.get("structured_evidence", [])),
                    "document_count": len(vendor_result.get("document_evidence", [])),
                },
                "outputs": {
                    "structured_count": len(vendor_result.get("structured_evidence", [])),
                    "document_count": len(vendor_result.get("document_evidence", [])),
                    "sources": list(vendor_result.get("sources", [])),
                },
            }
        )

        response_contract["traceability"] = traceability
        response_contract = self.response_composer.compose(response_contract, trace_context=trace_context)
        response_contract["execution_metadata"].append(
            {
                "agent": "response_composer",
                "reason_selected": "Generate the final audit narrative and evaluation.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "structured_count": len(response_contract.get("structured_evidence", [])),
                    "document_count": len(response_contract.get("document_evidence", [])),
                },
                "outputs": {
                    "risk_rating": response_contract.get("risk_rating"),
                    "finding_title": response_contract.get("finding", {}).get("title"),
                },
            }
        )
        traceability["execution_metadata"] = list(response_contract["execution_metadata"])
        response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
        self._finalize_response(
            response_contract=response_contract,
            traceability=traceability,
            trace_context=trace_context,
            governance_audit=governance_audit,
            actor_user_id=actor_user_id,
            query=query,
            result="vendor_investigation",
        )

    def _run_document_investigation(
        self,
        *,
        response_contract: dict[str, Any],
        traceability: dict[str, Any],
        trace_context: Any,
        governance_audit: GovernanceAuditService,
        actor_user_id: str | None,
        query: str,
        attached_document_ids: list[str],
    ) -> None:
        self.traceability_service.record_reasoning(traceability, "Query matched the document evidence workflow.")
        self.traceability_service.record_agent(
            traceability,
            "document_retrieval_agent",
            "Query requested document evidence or referenced uploaded documents.",
        )
        doc_span = trace_context.begin_span(
            "document_retrieval_agent",
            input_payload={"query": query, "attached_document_ids": attached_document_ids},
            metadata={"service": "AuditWorkflowService"},
        )
        document_result = self.document_agent.retrieve(
            query=query,
            structured_intent={},
            transaction_results=[],
            attached_document_ids=attached_document_ids,
            trace_context=trace_context,
        )
        doc_span.finish(
            output={
                "document_count": len(document_result.get("documents", [])),
                "sources": document_result.get("sources", []),
            },
            metadata={
                "document_count": len(document_result.get("documents", [])),
                "sources": document_result.get("sources", []),
            },
        )

        response_contract["structured_evidence"] = []
        response_contract["document_evidence"] = list(document_result.get("documents", []))
        response_contract["sources"] = list(dict.fromkeys(document_result.get("sources", [])))
        response_contract["success"] = bool(response_contract["document_evidence"])
        response_contract["investigation_summary"] = (
            f"Document evidence review returned {len(response_contract['document_evidence'])} document(s)."
            if response_contract["document_evidence"]
            else "I could not identify sufficient document evidence to investigate this request."
        )
        response_contract["top_supporting_evidence"] = self._rank_documents(response_contract["document_evidence"])[:5]
        response_contract["supporting_documents"] = response_contract["document_evidence"]
        response_contract["supporting_evidence"] = (
            [{"summary": f"{len(response_contract['document_evidence'])} uploaded document(s) were reviewed."}]
            if response_contract["document_evidence"]
            else []
        )
        response_contract["recommendations"] = (
            ["Review the attached documents for additional context."]
            if response_contract["document_evidence"]
            else ["Upload a supporting document or ask a more specific question."]
        )
        response_contract["finding"] = {
            "finding_title": "Document Evidence Review",
            "finding_summary": response_contract["investigation_summary"],
            "evidence_summary": response_contract["investigation_summary"],
            "recommendation": response_contract["recommendations"][0],
            "supporting_documents": response_contract["supporting_documents"],
        }
        response_contract["risk_rating"] = "LOW"
        response_contract["risk_score"] = 0
        response_contract["risk_drivers"] = []
        response_contract["execution_metadata"] = [
            {
                "agent": "query_router",
                "reason_selected": "The request matched the document evidence workflow.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query},
                "outputs": {"selected_agent": "document_retrieval_agent"},
            },
            {
                "agent": "source_router",
                "reason_selected": "Document evidence was selected as the primary source.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "attached_document_ids": attached_document_ids},
                "outputs": {
                    "source_mode": response_contract.get("source_route", {}).get("source_mode"),
                    "decision_source": response_contract.get("source_route", {}).get("decision_source"),
                },
            },
            {
                "agent": "document_retrieval_agent",
                "reason_selected": "Query requested document evidence or referenced uploaded documents.",
                "status": "completed" if response_contract["document_evidence"] else "completed_with_no_rows",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {"query": query, "attached_document_ids": attached_document_ids},
                "outputs": {
                    "document_count": len(response_contract["document_evidence"]),
                    "sources": list(response_contract["sources"]),
                },
            },
            {
                "agent": "evidence_aggregator",
                "reason_selected": "Combine document evidence into a single audit package.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "document_count": len(response_contract["document_evidence"]),
                    "source_count": len(response_contract["sources"]),
                },
                "outputs": {
                    "document_count": len(response_contract["document_evidence"]),
                    "source_count": len(response_contract["sources"]),
                },
            },
        ]
        response_contract["traceability"] = traceability
        response_contract = self.response_composer.compose(response_contract, trace_context=trace_context)
        response_contract["execution_metadata"].append(
            {
                "agent": "response_composer",
                "reason_selected": "Generate the final audit narrative and evaluation.",
                "status": "completed",
                "started_at": self._now_iso(),
                "ended_at": self._now_iso(),
                "inputs": {
                    "structured_count": len(response_contract.get("structured_evidence", [])),
                    "document_count": len(response_contract.get("document_evidence", [])),
                },
                "outputs": {
                    "risk_rating": response_contract.get("risk_rating"),
                    "finding_title": response_contract.get("finding", {}).get("title"),
                },
            }
        )
        traceability["execution_metadata"] = list(response_contract["execution_metadata"])
        response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
        self._finalize_response(
            response_contract=response_contract,
            traceability=traceability,
            trace_context=trace_context,
            governance_audit=governance_audit,
            actor_user_id=actor_user_id,
            query=query,
            result="document_review",
        )

    def _run_control_testing(
        self,
        *,
        response_contract: dict[str, Any],
        traceability: dict[str, Any],
        trace_context: Any,
        governance_audit: GovernanceAuditService,
        actor_user_id: str | None,
        query: str,
        page: int,
        page_size: int,
        routing_decision: dict[str, Any],
    ) -> None:
        self.traceability_service.record_reasoning(traceability, "Query matched the control testing workflow.")
        self.traceability_service.record_agent(
            traceability,
            "control_testing_agent",
            "Query requested control testing across approvals, compliance, and duplicate-payment patterns.",
        )
        control_span = trace_context.begin_span(
            "control_testing_agent",
            input_payload={"query": query, "page": page, "page_size": page_size},
            metadata={"service": "AuditWorkflowService"},
        )
        control_result = self.control_testing_service.run(
            query=query,
            trace_context=trace_context,
            page=page,
            page_size=page_size,
        )
        control_span.finish(
            output={
                "success": control_result.get("success"),
                "tests_run": len(control_result.get("control_tests", [])),
                "tests_failed": control_result.get("control_metrics", {}).get("tests_failed", 0),
                "structured_count": len(control_result.get("structured_evidence", [])),
                "document_count": len(control_result.get("document_evidence", [])),
            },
            metadata={
                "service": "AuditWorkflowService",
                "tests_run": len(control_result.get("control_tests", [])),
                "tests_failed": control_result.get("control_metrics", {}).get("tests_failed", 0),
            },
        )
        response_contract.update(
            {
                "success": control_result.get("success", True),
                "entity_type": control_result.get("entity_type", "control"),
                "entity_id": control_result.get("entity_id"),
                "control_summary": control_result.get("control_summary", ""),
                "control_tests": control_result.get("control_tests", []),
                "control_metrics": control_result.get("control_metrics", {}),
                "investigation_summary": control_result.get("investigation_summary", ""),
                "key_findings": control_result.get("key_findings", []),
                "top_supporting_evidence": control_result.get("top_supporting_evidence", []),
                "supporting_evidence": control_result.get("supporting_evidence", []),
                "supporting_documents": control_result.get("supporting_documents", []),
                "structured_evidence": control_result.get("structured_evidence", []),
                "document_evidence": control_result.get("document_evidence", []),
                "sources": control_result.get("sources", []),
                "recommendations": control_result.get("recommendations", []),
                "finding": control_result.get("finding", {}),
                "agents_used": control_result.get("agents_used", []),
                "reasoning": control_result.get("reasoning", []),
                "execution_metadata": control_result.get("execution_metadata", []),
            }
        )
        response_contract["routing_decision"] = routing_decision
        response_contract["traceability"] = traceability
        for source in response_contract.get("sources", []):
            self.traceability_service.record_source(traceability, source)
        for item in response_contract.get("structured_evidence", []):
            self.traceability_service.record_evidence(
                traceability,
                {
                    "type": "structured",
                    "reference": item.get("control_test_id") or item.get("transaction_id") or item.get("approval_id") or item.get("compliance_id"),
                    "source": item.get("source_type") or "control_test",
                },
            )
        for item in response_contract.get("document_evidence", []):
            self.traceability_service.record_evidence(
                traceability,
                {
                    "type": "document",
                    "reference": item.get("document_id"),
                    "source": "document_metadata",
                },
            )
        response_contract = self.response_composer.compose(response_contract, trace_context=trace_context)
        response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
        self._finalize_response(
            response_contract=response_contract,
            traceability=traceability,
            trace_context=trace_context,
            governance_audit=governance_audit,
            actor_user_id=actor_user_id,
            query=query,
            result="control_testing",
        )

    def _looks_like_control_testing(self, query: str) -> bool:
        normalized = query.lower()
        return bool(
            re.search(r"\bcontrol\b", normalized)
            or re.search(r"\bcontrols\b", normalized)
            or re.search(r"\bcontrol testing\b", normalized)
            or re.search(r"\btest controls\b", normalized)
            or re.search(r"\binternal control\b", normalized)
            or re.search(r"\bsegregation of duties\b", normalized)
            or re.search(r"\bpolicy exception\b", normalized)
            or re.search(r"\bduplicate payment\b", normalized)
        )

    def _looks_like_document_request(self, query: str) -> bool:
        normalized = query.lower()
        return bool(
            re.search(r"\b(document|documents|file|files|attachment|attachments|pdf|email|policy|contract|report)\b", normalized)
            or re.search(r"\b(uploaded document|attached document|this document|these documents)\b", normalized)
            or re.search(r"\bwhat does\b.*\bdocument\b", normalized)
            or re.search(r"\bsummarize\b.*\b(document|file|attachment)\b", normalized)
            or re.search(r"\bshow\b.*\b(citation|evidence|supporting document)\b", normalized)
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _run_adk_orchestrator(
        self,
        *,
        query: str,
        investigation_plan: dict[str, Any],
        structured_intent: dict[str, Any] | None,
        page: int,
        page_size: int,
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        from app.services.gemini_adk_workflow_service import GeminiAdkWorkflowService
        orchestrator = GeminiAdkWorkflowService(
            self.db,
            document_agent=self.document_agent,
            vendor_investigation_service=self.vendor_investigation_service,
            evidence_aggregator=self.evidence_aggregator,
            investigation_planner=self.investigation_planner,
        )
        return orchestrator.run(
            query=query,
            investigation_plan=investigation_plan,
            structured_intent=structured_intent,
            page=page,
            page_size=page_size,
            trace_context=trace_context,
        )

    def _finalize_response(
        self,
        *,
        response_contract: dict[str, Any],
        traceability: dict[str, Any],
        trace_context: Any,
        governance_audit: GovernanceAuditService,
        actor_user_id: str | None,
        query: str,
        result: str,
    ) -> None:
        selected_agents = list(response_contract.get("agents_used") or traceability.get("agents_invoked", []))
        routing = response_contract.get("routing_decision") or {}
        expected_agent = routing.get("agent")
        if expected_agent and selected_agents and expected_agent not in selected_agents:
            severity = "warning" if not routing.get("escalate_to_planner") else "info"
            self.traceability_service.record_reasoning(
                traceability,
                f"Router review noted that {expected_agent} was not the final executed path; selected agents were {', '.join(selected_agents)}.",
            )
            governance_audit.record_event(
                actor_user_id=actor_user_id,
                action_type="router_path_reviewed",
                entity_type="audit_query",
                severity=severity,
                summary=f"Router decision reviewed for query: {query[:180]}",
                after_state={
                    "query": query,
                    "routing_decision": routing,
                    "selected_agents": selected_agents,
                    "result": result,
                },
            )
            self.audit_db.commit()

        governance_audit.record_event(
            actor_user_id=actor_user_id,
            action_type="audit_query_completed",
            entity_type="audit_query",
            severity="info",
            summary=f"Audit query completed: {query[:200]}",
            after_state={
                "result": result,
                "risk_rating": response_contract.get("risk_rating"),
                "structured_evidence_count": len(response_contract.get("structured_evidence", [])),
                "document_evidence_count": len(response_contract.get("document_evidence", [])),
                "agents_used": selected_agents,
            },
        )
        self.audit_db.commit()
        trace_context.finalize(output=response_contract, metadata={"result": result})
        traceability["langfuse"] = trace_context.as_traceability()

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
