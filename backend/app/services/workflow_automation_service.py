from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class WorkflowAutomationService:
    """Derives an explicit audit lifecycle from the current response contract."""

    STAGE_ORDER = [
        "investigation",
        "review",
        "approval",
        "remediation",
        "closure",
    ]

    def build(self, response_contract: dict[str, Any], trace_context: Any | None = None) -> dict[str, Any]:
        span = trace_context.begin_span(
            "workflow_automation",
            input_payload={
                "query": response_contract.get("query", ""),
                "entity_type": response_contract.get("entity_type"),
                "risk_rating": response_contract.get("risk_rating"),
            },
            metadata={"service": "WorkflowAutomationService"},
        ) if trace_context else None

        workflow = self._build_workflow(response_contract)

        if span:
            span.finish(
                output={
                    "workflow_id": workflow.get("workflow_id"),
                    "current_stage": workflow.get("current_stage"),
                    "overall_status": workflow.get("overall_status"),
                },
                metadata={
                    "workflow_id": workflow.get("workflow_id"),
                    "completed_stage_count": workflow.get("summary", {}).get("completed_stage_count", 0),
                },
            )

        return workflow

    def _build_workflow(self, response_contract: dict[str, Any]) -> dict[str, Any]:
        risk_rating = str(response_contract.get("risk_rating") or "LOW").upper()
        finding = response_contract.get("finding", {}) if isinstance(response_contract.get("finding"), dict) else {}
        has_finding = bool(finding.get("title") or finding.get("summary"))
        has_docs = bool(response_contract.get("document_evidence") or response_contract.get("supporting_documents"))
        has_tx = bool(response_contract.get("structured_evidence"))
        has_recommendations = bool(response_contract.get("recommendations"))
        evaluation = response_contract.get("evaluation", {}) if isinstance(response_contract.get("evaluation"), dict) else {}
        exec_meta = list(response_contract.get("execution_metadata", []))
        agents_used = list(response_contract.get("agents_used", []))

        investigation_stage = self._stage(
            name="investigation",
            label="Investigation",
            status="completed" if has_tx or has_docs or has_finding else "not_started",
            description="Collect structured evidence, document evidence, and traceability inputs.",
            summary=f"{len(response_contract.get('structured_evidence', []))} structured item(s) and {len(response_contract.get('document_evidence', []))} document item(s) were collected.",
        )
        review_stage = self._stage(
            name="review",
            label="Review",
            status="completed" if has_finding else "in_progress" if has_tx or has_docs else "not_started",
            description="Review the evidence and determine the audit observation.",
            summary=f"Finding status: {finding.get('title') or 'not yet determined'}.",
        )
        approval_stage = self._stage(
            name="approval",
            label="Approval",
            status=self._approval_status(risk_rating=risk_rating, has_finding=has_finding),
            description="Route the result for supervisory review when risk or findings require escalation.",
            summary=self._approval_summary(risk_rating=risk_rating, has_finding=has_finding),
        )
        remediation_stage = self._stage(
            name="remediation",
            label="Remediation",
            status="completed" if not has_recommendations and risk_rating in {"LOW", "N/A"} else "pending",
            description="Define and track remediation actions for identified issues.",
            summary=" ".join(response_contract.get("recommendations", [])[:2]) or "No remediation actions were required.",
        )
        closure_stage = self._stage(
            name="closure",
            label="Closure",
            status="completed" if risk_rating in {"LOW", "N/A"} and not has_recommendations else "pending",
            description="Close the workflow once review and remediation have been captured.",
            summary="The workflow is ready for closure once remediation is accepted or the case is confirmed low risk.",
        )

        stages = [investigation_stage, review_stage, approval_stage, remediation_stage, closure_stage]
        completed_count = sum(1 for stage in stages if stage["status"] == "completed")
        current_stage = self._current_stage(stages)

        return {
            "workflow_id": f"WF-{uuid4().hex[:10].upper()}",
            "workflow_type": "audit_lifecycle",
            "entity_type": response_contract.get("entity_type"),
            "entity_id": response_contract.get("entity_id"),
            "current_stage": current_stage,
            "overall_status": self._overall_status(stages),
            "progress": {
                "completed_stages": completed_count,
                "total_stages": len(stages),
                "percentage": int((completed_count / len(stages)) * 100) if stages else 0,
            },
            "summary": {
                "completed_stage_count": completed_count,
                "pending_stage_count": sum(1 for stage in stages if stage["status"] in {"pending", "in_progress", "not_started"}),
                "status": self._overall_status(stages),
                "description": self._build_summary(response_contract, stages),
            },
            "stages": stages,
            "timeline": self._build_timeline(stages, exec_meta, agents_used),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _stage(
        self,
        *,
        name: str,
        label: str,
        status: str,
        description: str,
        summary: str,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "label": label,
            "status": status,
            "description": description,
            "summary": summary,
        }

    def _approval_status(self, *, risk_rating: str, has_finding: bool) -> str:
        if not has_finding:
            return "not_started"
        if risk_rating in {"HIGH", "CRITICAL"}:
            return "pending"
        return "completed"

    def _approval_summary(self, *, risk_rating: str, has_finding: bool) -> str:
        if not has_finding:
            return "No approval step was required because no final finding was produced."
        if risk_rating in {"HIGH", "CRITICAL"}:
            return "The finding should be escalated for supervisory approval before closure."
        return "The finding can proceed through standard approval review."

    def _current_stage(self, stages: list[dict[str, Any]]) -> str:
        for stage in stages:
            if stage["status"] in {"in_progress", "pending", "not_started"}:
                return stage["name"]
        return stages[-1]["name"] if stages else "closure"

    def _overall_status(self, stages: list[dict[str, Any]]) -> str:
        statuses = [stage["status"] for stage in stages]
        if any(status == "pending" for status in statuses):
            return "awaiting_action"
        if any(status == "in_progress" for status in statuses):
            return "in_progress"
        if all(status == "completed" for status in statuses):
            return "closed"
        return "open"

    def _build_summary(self, response_contract: dict[str, Any], stages: list[dict[str, Any]]) -> str:
        finding = response_contract.get("finding", {}) if isinstance(response_contract.get("finding"), dict) else {}
        risk_rating = str(response_contract.get("risk_rating") or "LOW").upper()
        stage_summary = ", ".join(f"{stage['label']}={stage['status']}" for stage in stages)
        return (
            f"The audit lifecycle was derived from the current investigation result. "
            f"Finding: {finding.get('title') or 'none'}; Risk rating: {risk_rating}; Stage status: {stage_summary}."
        )

    def _build_timeline(
        self,
        stages: list[dict[str, Any]],
        execution_metadata: list[dict[str, Any]],
        agents_used: list[str],
    ) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []
        stage_status_by_name = {stage["name"]: stage["status"] for stage in stages}
        stage_labels = {stage["name"]: stage["label"] for stage in stages}
        for index, stage_name in enumerate(self.STAGE_ORDER, start=1):
            timeline.append(
                {
                    "step": index,
                    "stage": stage_name,
                    "label": stage_labels.get(stage_name, stage_name.title()),
                    "status": stage_status_by_name.get(stage_name, "not_started"),
                    "agent": self._stage_agent(stage_name),
                    "summary": self._stage_summary(stage_name, execution_metadata, agents_used),
                }
            )
        return timeline

    def _stage_agent(self, stage_name: str) -> str:
        return {
            "investigation": "investigation_planner",
            "review": "response_composer",
            "approval": "governance_review",
            "remediation": "recommendation_service",
            "closure": "workflow_closure",
        }.get(stage_name, "workflow_engine")

    def _stage_summary(self, stage_name: str, execution_metadata: list[dict[str, Any]], agents_used: list[str]) -> str:
        if stage_name == "investigation":
            return f"Agents used: {', '.join(agents_used) or 'none'}."
        if stage_name == "review":
            return f"{len(execution_metadata)} execution step(s) were recorded."
        if stage_name == "approval":
            return "Approval status is derived from the resulting risk rating."
        if stage_name == "remediation":
            return "Recommendations define the remediation path."
        if stage_name == "closure":
            return "Workflow closure depends on approval and remediation outcomes."
        return "Workflow stage processed."
