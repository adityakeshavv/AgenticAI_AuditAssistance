from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.approval_service import execute_approval_query
from app.services.compliance_service import execute_compliance_query
from app.services.document_retrieval_agent_service import DocumentRetrievalAgent
from app.services.evidence_aggregator_service import EvidenceAggregatorService
from app.services.investigation_planner_service import InvestigationPlannerService
from app.services.vendor_investigation_service import VendorInvestigationService
from app.services.expense_service import execute_expense_query
from app.services.transaction_service import execute_transaction_query
from app.services.gemini_client_service import GeminiClientService
from app.services.agent_orchestrator_service import AgentOrchestratorService


class GeminiAdkWorkflowService:
    """Gemini-first workflow runtime for the audit assistant.

    The app does not yet depend on a dedicated Gemini ADK package, so this
    service implements the ADK-style execution boundary directly:
    planner -> step execution -> evidence aggregation -> structured output.
    When Gemini is unavailable or the runtime flag is not enabled, we fall
    back to the legacy orchestrator to preserve existing behavior.
    """

    def __init__(
        self,
        db: Session,
        *,
        document_agent: DocumentRetrievalAgent,
        vendor_investigation_service: VendorInvestigationService,
        evidence_aggregator: EvidenceAggregatorService,
        investigation_planner: InvestigationPlannerService,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.gemini_client = GeminiClientService()
        self.document_agent = document_agent
        self.vendor_investigation_service = vendor_investigation_service
        self.evidence_aggregator = evidence_aggregator
        self.investigation_planner = investigation_planner
        self.legacy_orchestrator = AgentOrchestratorService(
            db,
            document_agent=document_agent,
            vendor_investigation_service=vendor_investigation_service,
            evidence_aggregator=evidence_aggregator,
            investigation_planner=investigation_planner,
        )

    def run(
        self,
        *,
        query: str,
        investigation_plan: dict[str, Any],
        structured_intent: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 10,
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        if not self._use_gemini_runtime():
            return self.legacy_orchestrator.run(
                query=query,
                investigation_plan=investigation_plan,
                structured_intent=structured_intent,
                page=page,
                page_size=page_size,
                trace_context=trace_context,
            )

        structured_intent = structured_intent or {}
        plan = list(investigation_plan.get("plan", []))
        if not plan:
            return self._unsupported_execution(query=query, investigation_plan=investigation_plan, structured_intent=structured_intent)

        execution_metadata: list[dict[str, Any]] = []
        transaction_rows: list[dict[str, Any]] = []
        vendor_investigations: list[dict[str, Any]] = []
        extra_structured_evidence: list[dict[str, Any]] = []
        document_result: dict[str, Any] = {"documents": [], "sources": []}
        transaction_intent: dict[str, Any] = structured_intent

        for step in plan:
            agent = str(step.get("agent") or "").strip()
            if not agent:
                continue

            started_at = self._timestamp()
            result: dict[str, Any] = {"success": False, "skipped": True, "reason": "unsupported_agent"}

            if agent == "transaction_agent":
                execution_query = self._resolve_execution_query(query=query, step=step)
                result = execute_transaction_query(
                    self.db,
                    execution_query,
                    page=page,
                    page_size=page_size,
                    trace_context=trace_context,
                )
                if result.get("success"):
                    transaction_rows = list(result.get("results", []))
                    transaction_intent = result.get("structured_intent", transaction_intent) or transaction_intent

            elif agent in {"vendor_agent", "vendor_investigation_agent"}:
                vendor_ids = self._top_vendor_ids(transaction_rows, limit=3)
                if vendor_ids:
                    vendor_results: list[dict[str, Any]] = []
                    for vendor_id in vendor_ids:
                        vendor_result = self.vendor_investigation_service.investigate(
                            query=f"review vendor {vendor_id}",
                            vendor_id=vendor_id,
                            trace_context=trace_context,
                        )
                        vendor_results.append(vendor_result)
                        if vendor_result.get("success"):
                            vendor_investigations.append(vendor_result)
                    result = {
                        "success": True,
                        "vendor_ids": vendor_ids,
                        "result_count": len(vendor_results),
                    }
                else:
                    result = {"success": False, "skipped": True, "reason": "no_vendor_ids"}

            elif agent == "document_retrieval_agent":
                document_result = self.document_agent.retrieve(
                    query=query,
                    structured_intent=transaction_intent,
                    transaction_results=transaction_rows,
                    trace_context=trace_context,
                )
                result = {
                    "success": True,
                    "document_count": len(document_result.get("documents", [])),
                    "sources": list(document_result.get("sources", [])),
                }

            elif agent == "compliance_agent":
                execution_query = self._resolve_execution_query(query=query, step=step)
                result = execute_compliance_query(self.db, execution_query, page=page, page_size=page_size)
                if result.get("success"):
                    extra_structured_evidence.extend(list(result.get("results", [])))

            elif agent == "approval_agent":
                execution_query = self._resolve_execution_query(query=query, step=step)
                result = execute_approval_query(self.db, execution_query, page=page, page_size=page_size)
                if result.get("success"):
                    extra_structured_evidence.extend(list(result.get("results", [])))

            elif agent == "expense_agent":
                execution_query = self._resolve_execution_query(query=query, step=step)
                result = execute_expense_query(self.db, execution_query, page=page, page_size=page_size)
                if result.get("success"):
                    extra_structured_evidence.extend(list(result.get("results", [])))

            self._append_execution_metadata(
                execution_metadata,
                agent=agent,
                reason=step.get("reason"),
                started_at=started_at,
                result=result,
                inputs=self._build_inputs(
                    query=query,
                    step=step,
                    structured_intent=transaction_intent,
                    transaction_count=len(transaction_rows),
                    page=page,
                    page_size=page_size,
                ),
                status=self._status_from_result(result),
            )

        structured_evidence = list(transaction_rows) + list(extra_structured_evidence)
        document_evidence = list(document_result.get("documents", []))
        sources = ["transaction_master"]
        if document_evidence:
            sources.append("document_metadata")
        sources.extend(list(document_result.get("sources", [])))

        for vendor_result in vendor_investigations:
            structured_evidence.extend(list(vendor_result.get("structured_evidence", [])))
            document_evidence.extend(list(vendor_result.get("document_evidence", [])))
            sources.extend(list(vendor_result.get("sources", [])))

        structured_evidence = self._dedupe_records(
            structured_evidence,
            fields=("source_type", "transaction_id", "vendor_id", "contract_id", "finding_id", "approval_id", "compliance_id", "claim_id"),
        )
        document_evidence = self._dedupe_records(document_evidence, fields=("document_id",))

        aggregated = self.evidence_aggregator.aggregate(
            structured_evidence=structured_evidence,
            document_evidence=document_evidence,
            sources=sources,
            trace_context=trace_context,
        )

        return {
            "success": True,
            "investigation_plan": investigation_plan,
            "entities_investigated": list(investigation_plan.get("entities_required", [])),
            "entity_type": "investigation",
            "structured_intent": transaction_intent,
            "transaction_rows": transaction_rows,
            "vendor_investigations": vendor_investigations,
            "structured_evidence": aggregated["structured_evidence"],
            "document_evidence": aggregated["document_evidence"],
            "sources": aggregated["sources"],
            "execution_metadata": execution_metadata,
            "agents_used": [entry["agent"] for entry in execution_metadata if entry.get("status") == "completed"],
            "transaction_result_count": len(transaction_rows),
            "document_result_count": len(document_evidence),
        }

    def _use_gemini_runtime(self) -> bool:
        return str(self.settings.agent_runtime).strip().lower() == "gemini_adk" and self.gemini_client.is_configured()

    def _unsupported_execution(
        self,
        *,
        query: str,
        investigation_plan: dict[str, Any],
        structured_intent: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "success": False,
            "investigation_plan": investigation_plan,
            "entities_investigated": list(investigation_plan.get("entities_required", [])),
            "entity_type": "investigation",
            "structured_intent": structured_intent,
            "transaction_rows": [],
            "vendor_investigations": [],
            "structured_evidence": [],
            "document_evidence": [],
            "sources": [],
            "execution_metadata": [],
            "agents_used": [],
            "transaction_result_count": 0,
            "document_result_count": 0,
            "message": "No executable Gemini investigation plan was produced for this query.",
            "query": query,
        }

    def _resolve_execution_query(self, *, query: str, step: dict[str, Any]) -> str:
        query_hint = str(step.get("query_hint") or "").strip()
        if query_hint:
            return query_hint
        built = self.investigation_planner.build_execution_query(query)
        if built:
            return built
        return query

    def _append_execution_metadata(
        self,
        execution_metadata: list[dict[str, Any]],
        *,
        agent: str,
        reason: Any,
        started_at: str,
        result: dict[str, Any],
        inputs: dict[str, Any],
        status: str = "completed",
    ) -> None:
        execution_metadata.append(
            {
                "agent": agent,
                "reason_selected": str(reason or "").strip(),
                "status": status,
                "started_at": started_at,
                "ended_at": self._timestamp(),
                "inputs": inputs,
                "outputs": result,
            }
        )

    def _status_from_result(self, result: dict[str, Any]) -> str:
        if result.get("success"):
            return "completed"
        if result.get("skipped"):
            return "skipped"
        return "failed"

    def _build_inputs(
        self,
        *,
        query: str,
        step: dict[str, Any],
        structured_intent: dict[str, Any],
        transaction_count: int,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        return {
            "query": query,
            "query_hint": step.get("query_hint"),
            "structured_intent": structured_intent,
            "transaction_count": transaction_count,
            "page": page,
            "page_size": page_size,
        }

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

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
