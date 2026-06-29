from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.document_retrieval_agent_service import DocumentRetrievalAgent
from app.services.evidence_aggregator_service import EvidenceAggregatorService
from app.services.investigation_planner_service import InvestigationPlannerService
from app.services.transaction_service import execute_transaction_query
from app.services.vendor_investigation_service import VendorInvestigationService


class AgentOrchestratorService:
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
        self.document_agent = document_agent
        self.vendor_investigation_service = vendor_investigation_service
        self.evidence_aggregator = evidence_aggregator
        self.investigation_planner = investigation_planner

    def run(
        self,
        *,
        query: str,
        investigation_plan: dict[str, Any],
        structured_intent: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        structured_intent = structured_intent or {}
        plan_steps = list(investigation_plan.get("plan", []))

        execution_metadata: list[dict[str, Any]] = []
        transaction_rows: list[dict[str, Any]] = []
        vendor_investigations: list[dict[str, Any]] = []
        document_result: dict[str, Any] = {"documents": [], "sources": []}
        transaction_intent: dict[str, Any] = structured_intent

        for step in plan_steps:
            agent = str(step.get("agent") or "").strip()
            if not agent:
                continue

            started_at = self._timestamp()
            if agent == "transaction_agent":
                execution_query = self._resolve_execution_query(query=query, step=step)
                result = execute_transaction_query(self.db, execution_query, page=page, page_size=page_size)
                transaction_rows = list(result.get("results", [])) if result.get("success", False) else []
                transaction_intent = result.get("structured_intent", transaction_intent) or transaction_intent
                self._append_execution_metadata(
                    execution_metadata,
                    agent=agent,
                    reason=step.get("reason"),
                    started_at=started_at,
                    result=result,
                    inputs={
                        "query": query,
                        "execution_query": execution_query,
                        "page": page,
                        "page_size": page_size,
                    },
                    status="completed" if result.get("success", False) else "failed",
                )
                continue

            if agent in {"vendor_agent", "vendor_investigation_agent"}:
                vendor_ids = self._top_vendor_ids(transaction_rows, limit=3)
                if not vendor_ids:
                    self._append_execution_metadata(
                        execution_metadata,
                        agent=agent,
                        reason=step.get("reason"),
                        started_at=started_at,
                        result={"success": False, "skipped": True, "reason": "no_vendor_ids"},
                        inputs={
                            "query": query,
                            "transaction_count": len(transaction_rows),
                        },
                        status="skipped",
                    )
                    continue

                vendor_results: list[dict[str, Any]] = []
                for vendor_id in vendor_ids:
                    vendor_result = self.vendor_investigation_service.investigate(
                        query=f"review vendor {vendor_id}",
                        vendor_id=vendor_id,
                    )
                    vendor_results.append(vendor_result)
                    if vendor_result.get("success"):
                        vendor_investigations.append(vendor_result)

                self._append_execution_metadata(
                    execution_metadata,
                    agent=agent,
                    reason=step.get("reason"),
                    started_at=started_at,
                    result={
                        "success": True,
                        "vendor_ids": vendor_ids,
                        "result_count": len(vendor_results),
                    },
                    inputs={
                        "query": query,
                        "vendor_ids": vendor_ids,
                        "transaction_count": len(transaction_rows),
                    },
                )
                continue

            if agent == "document_retrieval_agent":
                document_result = self.document_agent.retrieve(
                    query=query,
                    structured_intent=transaction_intent,
                    transaction_results=transaction_rows,
                )
                self._append_execution_metadata(
                    execution_metadata,
                    agent=agent,
                    reason=step.get("reason"),
                    started_at=started_at,
                    result={
                        "success": True,
                        "document_count": len(document_result.get("documents", [])),
                        "sources": list(document_result.get("sources", [])),
                    },
                    inputs={
                        "query": query,
                        "transaction_count": len(transaction_rows),
                        "structured_intent": transaction_intent,
                    },
                )
                continue

            self._append_execution_metadata(
                execution_metadata,
                agent=agent,
                reason=step.get("reason"),
                started_at=started_at,
                result={"success": False, "skipped": True, "reason": "unsupported_agent"},
                inputs={"query": query},
                status="skipped",
            )

        structured_evidence = list(transaction_rows)
        document_evidence = list(document_result.get("documents", []))
        aggregated_sources = ["transaction_master"]
        if document_evidence:
            aggregated_sources.append("document_metadata")
        aggregated_sources.extend(document_result.get("sources", []))

        for vendor_result in vendor_investigations:
            structured_evidence.extend(vendor_result.get("structured_evidence", []))
            document_evidence.extend(vendor_result.get("document_evidence", []))
            aggregated_sources.extend(vendor_result.get("sources", []))

        structured_evidence = self._dedupe_records(
            structured_evidence,
            fields=("source_type", "transaction_id", "vendor_id", "contract_id", "finding_id", "approval_id"),
        )
        document_evidence = self._dedupe_records(document_evidence, fields=("document_id",))

        aggregated = self.evidence_aggregator.aggregate(
            structured_evidence=structured_evidence,
            document_evidence=document_evidence,
            sources=aggregated_sources,
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
