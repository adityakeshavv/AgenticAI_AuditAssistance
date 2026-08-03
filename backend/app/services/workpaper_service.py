from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services.base_investigation_service import BaseInvestigationService


class WorkpaperService(BaseInvestigationService):
    """Builds standardized workpapers and exportable audit report artifacts."""

    def build(self, response_contract: dict[str, Any], trace_context: Any | None = None) -> dict[str, Any]:
        span = trace_context.begin_span(
            "workpaper_generation",
            input_payload={
                "query": response_contract.get("query", ""),
                "entity_type": response_contract.get("entity_type"),
                "finding_title": response_contract.get("finding", {}).get("title"),
            },
            metadata={"service": "WorkpaperService"},
        ) if trace_context else None

        workpaper = self._build_workpaper(response_contract)
        report_exports = self._build_report_exports(workpaper)

        if span:
            span.finish(
                output={
                    "workpaper_id": workpaper.get("workpaper_id"),
                    "title": workpaper.get("title"),
                    "formats": report_exports.get("formats", []),
                },
                metadata={
                    "workpaper_id": workpaper.get("workpaper_id"),
                    "format_count": len(report_exports.get("formats", [])),
                },
            )

        return {
            "workpaper": workpaper,
            "report_exports": report_exports,
        }

    def _build_workpaper(self, response_contract: dict[str, Any]) -> dict[str, Any]:
        query = str(response_contract.get("query") or "")
        finding = response_contract.get("finding", {}) if isinstance(response_contract.get("finding"), dict) else {}
        traceability = response_contract.get("traceability", {}) if isinstance(response_contract.get("traceability"), dict) else {}
        evaluation = response_contract.get("evaluation", {}) if isinstance(response_contract.get("evaluation"), dict) else {}
        workflow_automation = response_contract.get("workflow_automation", {}) if isinstance(response_contract.get("workflow_automation"), dict) else {}
        execution_metadata = list(response_contract.get("execution_metadata", []))
        supporting_documents = self.prioritize_supporting_evidence(list(response_contract.get("supporting_documents", [])))
        supporting_evidence = list(response_contract.get("supporting_evidence", []))
        structured_evidence = list(response_contract.get("structured_evidence", []))
        document_evidence = list(response_contract.get("document_evidence", []))
        entities = list(response_contract.get("entities_investigated", []))
        metrics = dict(response_contract.get("investigation_metrics", {}))

        entity_type = str(response_contract.get("entity_type") or "audit").strip() or "audit"
        entity_id = response_contract.get("entity_id")
        title = self._build_title(entity_type=entity_type, finding_title=str(finding.get("title") or "Audit Workpaper"))
        workpaper_id = self._build_workpaper_id(entity_type=entity_type, query=query)

        methodology = self._build_methodology(response_contract)
        key_findings = self._build_key_findings(response_contract)
        recommendations = list(response_contract.get("recommendations", []))

        if not metrics:
            metrics = {
                "transactions_reviewed": len(structured_evidence),
                "contracts_reviewed": 0,
                "documents_reviewed": len(document_evidence),
                "flagged_transactions": sum(1 for row in structured_evidence if str(row.get("status", "")).upper() == "FLAGGED"),
            }

        workpaper = {
            "workpaper_id": workpaper_id,
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "objective": self._build_objective(response_contract),
            "scope": {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entities_investigated": entities,
                "agents_used": list(response_contract.get("agents_used", [])),
                "sources_used": list(response_contract.get("sources", [])),
            },
            "methodology": methodology,
            "summary": str(response_contract.get("final_response") or response_contract.get("investigation_summary") or finding.get("summary") or ""),
            "finding": {
                "title": finding.get("title"),
                "summary": finding.get("summary"),
                "category": finding.get("category"),
                "severity": finding.get("severity"),
                "risk_reasoning": finding.get("risk_reasoning"),
            },
            "metrics": metrics,
            "risk_assessment": {
                "risk_rating": response_contract.get("risk_rating"),
                "risk_score": response_contract.get("risk_score"),
                "risk_drivers": list(response_contract.get("risk_drivers", [])),
            },
            "key_findings": key_findings,
            "supporting_evidence": self._summarize_structured_evidence(structured_evidence),
            "supporting_documents": supporting_documents,
            "citations": self._summarize_citations(list(response_contract.get("citations", []))),
            "recommendations": recommendations,
            "validation": evaluation,
            "workflow_automation": workflow_automation,
            "traceability": {
                "agents_invoked": list(traceability.get("agents_invoked", [])),
                "agent_selection_reasoning": list(traceability.get("agent_selection_reasoning", [])),
                "sources_used": list(traceability.get("sources_used", [])),
                "reasoning_path": list(traceability.get("reasoning_path", [])),
                "langfuse": dict(traceability.get("langfuse", {})),
            },
            "execution_metadata": execution_metadata,
        }
        return workpaper

    def _build_report_exports(self, workpaper: dict[str, Any]) -> dict[str, Any]:
        markdown = self._build_markdown_report(workpaper)
        return {
            "formats": ["json", "markdown"],
            "file_name": f"{workpaper.get('workpaper_id', 'audit_workpaper')}.md",
            "markdown": markdown,
            "json": workpaper,
        }

    def _build_markdown_report(self, workpaper: dict[str, Any]) -> str:
        lines: list[str] = []
        lines.append(f"# {workpaper.get('title', 'Audit Workpaper')}")
        lines.append("")
        lines.append(f"- Workpaper ID: {workpaper.get('workpaper_id', '')}")
        lines.append(f"- Generated At: {workpaper.get('generated_at', '')}")
        lines.append(f"- Query: {workpaper.get('query', '')}")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append(str(workpaper.get("summary") or ""))
        lines.append("")
        lines.append("## Objective")
        lines.append(str(workpaper.get("objective") or ""))
        lines.append("")
        lines.append("## Scope")
        scope = workpaper.get("scope", {})
        lines.append(f"- Entity Type: {scope.get('entity_type', '')}")
        lines.append(f"- Entity ID: {scope.get('entity_id', '')}")
        lines.append(f"- Entities Investigated: {', '.join(scope.get('entities_investigated', [])) or 'None'}")
        lines.append(f"- Agents Used: {', '.join(scope.get('agents_used', [])) or 'None'}")
        lines.append(f"- Sources Used: {', '.join(scope.get('sources_used', [])) or 'None'}")
        lines.append("")
        lines.append("## Methodology")
        for item in workpaper.get("methodology", []) or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("## Finding")
        finding = workpaper.get("finding", {})
        lines.append(f"- Title: {finding.get('title', '')}")
        lines.append(f"- Summary: {finding.get('summary', '')}")
        lines.append(f"- Category: {finding.get('category', '')}")
        lines.append(f"- Severity: {finding.get('severity', '')}")
        lines.append("")
        lines.append("## Risk Assessment")
        risk = workpaper.get("risk_assessment", {})
        lines.append(f"- Risk Rating: {risk.get('risk_rating', '')}")
        lines.append(f"- Risk Score: {risk.get('risk_score', '')}")
        for driver in risk.get("risk_drivers", []) or []:
            lines.append(f"- Driver: {driver}")
        lines.append("")
        lines.append("## Metrics")
        for key, value in (workpaper.get("metrics", {}) or {}).items():
            lines.append(f"- {key.replace('_', ' ').title()}: {value}")
        lines.append("")
        lines.append("## Key Findings")
        for item in workpaper.get("key_findings", []) or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("## Supporting Evidence")
        for item in workpaper.get("supporting_evidence", []) or []:
            lines.append(f"- {item.get('summary', '')}")
        lines.append("")
        lines.append("## Supporting Documents")
        for document in workpaper.get("supporting_documents", []) or []:
            lines.append(
                f"- {document.get('document_id', '')} | {document.get('file_name', '')} | "
                f"Page {document.get('page_number', 'n/a')} | {document.get('reason_selected', '')}"
            )
        lines.append("")
        lines.append("## Citations")
        for citation in workpaper.get("citations", []) or []:
            lines.append(
                f"- {citation.get('document_id', '')} | {citation.get('file_name', '')} | "
                f"Page {citation.get('page_number', 'n/a')} | {citation.get('citation_text', '')}"
            )
        lines.append("")
        lines.append("## Recommendations")
        for item in workpaper.get("recommendations", []) or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("## Validation")
        validation = workpaper.get("validation", {})
        for key, value in validation.items():
            lines.append(f"- {key.replace('_', ' ').title()}: {value}")
        lines.append("")
        lines.append("## Workflow Automation")
        workflow = workpaper.get("workflow_automation", {})
        if workflow:
            lines.append(f"- Workflow ID: {workflow.get('workflow_id', '')}")
            lines.append(f"- Workflow Type: {workflow.get('workflow_type', '')}")
            lines.append(f"- Current Stage: {workflow.get('current_stage', '')}")
            lines.append(f"- Overall Status: {workflow.get('overall_status', '')}")
            progress = workflow.get("progress", {})
            lines.append(
                f"- Progress: {progress.get('completed_stages', 0)}/{progress.get('total_stages', 0)} "
                f"({progress.get('percentage', 0)}%)"
            )
            for stage in workflow.get("stages", []) or []:
                lines.append(f"- {stage.get('label', stage.get('name', 'Stage'))}: {stage.get('status', '')} — {stage.get('summary', '')}")
        else:
            lines.append("- No workflow automation metadata available.")
        lines.append("")
        lines.append("## Traceability")
        traceability = workpaper.get("traceability", {})
        lines.append(f"- Agents Invoked: {', '.join(traceability.get('agents_invoked', [])) or 'None'}")
        lines.append(f"- Sources Used: {', '.join(traceability.get('sources_used', [])) or 'None'}")
        lines.append(f"- Reasoning Path: {', '.join(traceability.get('reasoning_path', [])) or 'None'}")
        return "\n".join(lines).strip()

    def _build_workpaper_id(self, *, entity_type: str, query: str) -> str:
        return f"WP-{entity_type.upper()}-{uuid4().hex[:10].upper()}"

    def _build_title(self, *, entity_type: str, finding_title: str) -> str:
        if entity_type == "vendor":
            return "Vendor Investigation Workpaper"
        if entity_type == "transaction":
            return "Transaction Investigation Workpaper"
        if entity_type == "control":
            return "Control Testing Workpaper"
        return f"{finding_title or 'Audit'} Workpaper"

    def _build_objective(self, response_contract: dict[str, Any]) -> str:
        query = str(response_contract.get("query") or "").strip()
        finding = response_contract.get("finding", {}) if isinstance(response_contract.get("finding"), dict) else {}
        objective_bits = [
            f"Answer the audit question: {query}." if query else "Answer the audit question.",
            f"The review produced a finding titled '{finding.get('title', 'Audit Finding')}'.",
        ]
        return " ".join(objective_bits)

    def _build_methodology(self, response_contract: dict[str, Any]) -> list[str]:
        steps = []
        routing = response_contract.get("routing_decision", {})
        if routing:
            steps.append(f"Query routed to {routing.get('agent', 'general_agent')} with confidence {routing.get('confidence', 0)}.")
        source_route = response_contract.get("source_route", {})
        if source_route:
            steps.append(f"Source routing selected {source_route.get('source_mode', 'unknown')} evidence.")
        execution_metadata = list(response_contract.get("execution_metadata", []))
        for entry in execution_metadata:
            agent = entry.get("agent") or "agent"
            status = entry.get("status") or "unknown"
            reason = entry.get("reason_selected") or ""
            steps.append(f"{agent} executed with status {status}. {reason}".strip())
        if not steps:
            steps.append("Deterministic evidence aggregation and report composition were applied.")
        return steps

    def _build_key_findings(self, response_contract: dict[str, Any]) -> list[str]:
        key_findings = list(response_contract.get("key_findings", []))
        if key_findings:
            return [
                finding if isinstance(finding, str) else str(finding.get("summary") or finding)
                for finding in key_findings
            ]
        finding = response_contract.get("finding", {})
        summary = finding.get("summary") if isinstance(finding, dict) else ""
        return [str(summary)] if summary else []

    def _summarize_structured_evidence(self, structured_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summary: list[dict[str, Any]] = []
        for index, item in enumerate(structured_evidence[:50], start=1):
            summary.append(
                {
                    "item": index,
                    "source_type": item.get("source_type") or item.get("table_name") or "structured",
                    "reference": item.get("transaction_id") or item.get("vendor_id") or item.get("approval_id") or item.get("compliance_id") or item.get("control_test_id"),
                    "status": item.get("status"),
                    "summary": item.get("reason_selected") or item.get("finding_summary") or item.get("result_reason") or item.get("summary") or "",
                }
            )
        return summary

    def _summarize_citations(self, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summary: list[dict[str, Any]] = []
        for index, citation in enumerate(citations[:50], start=1):
            summary.append(
                {
                    "item": index,
                    "document_id": citation.get("document_id"),
                    "file_name": citation.get("file_name") or citation.get("document_name"),
                    "page_number": citation.get("page_number"),
                    "section_title": citation.get("section_title"),
                    "citation_text": citation.get("citation_text"),
                    "selection_reason": citation.get("selection_reason") or citation.get("selection_explanation", {}).get("selection_reason") if isinstance(citation.get("selection_explanation"), dict) else citation.get("selection_reason"),
                }
            )
        return summary
