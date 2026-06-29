from __future__ import annotations

import json
import logging
from typing import Any

from app.prompts import (
    build_finding_generation_messages,
    build_narrative_messages,
    build_recommendation_messages,
)


logger = logging.getLogger(__name__)


class FindingGenerationService:
    def __init__(self) -> None:
        from app.core.config import get_settings

        self.settings = get_settings()

    def generate(
        self,
        *,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        intent: dict[str, Any] | None = None,
        query: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        investigation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not structured_evidence and not document_evidence:
            return self._normalize_finding(
                {
                    "title": "No Significant Findings",
                    "summary": "No structured evidence or supporting document evidence was found.",
                    "risk_reasoning": "No evidence was returned by the current query path.",
                    "evidence_summary": "No evidence was returned by the current query path.",
                    "recommendation": "Continue periodic monitoring.",
                    "narrative": self._build_deterministic_narrative(
                        query=query or "",
                        intent=intent or {},
                        title="No Significant Findings",
                        summary="No structured evidence or supporting document evidence was found.",
                        evidence_summary="No evidence was returned by the current query path.",
                        recommendation="Continue periodic monitoring.",
                    ),
                    "supporting_documents": [],
                }
            )

        deterministic = self._generate_deterministic(
            structured_evidence=structured_evidence,
            document_evidence=document_evidence,
            intent=intent,
            query=query or "",
        )

        if not self.settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not configured. Falling back to deterministic finding generation.")
            return self._normalize_finding(deterministic)

        try:
            llm_finding = self._generate_llm_finding(
                query=query or "",
                intent=intent or {},
                structured_evidence=structured_evidence,
                document_evidence=document_evidence,
                citations=citations or [],
                investigation_context=investigation_context or {},
                deterministic=deterministic,
            )
            return self._normalize_finding({**deterministic, **llm_finding})
        except Exception as exc:
            logger.warning("LLM-based finding generation failed. Falling back to deterministic logic: %s", exc)
            return self._normalize_finding(deterministic)

    def _generate_deterministic(
        self,
        *,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        intent: dict[str, Any] | None = None,
        query: str = "",
    ) -> dict[str, Any]:
        amount_filter = self._amount_filter(intent or {})
        flagged_transactions = self._flagged_transactions(structured_evidence)
        investigation_documents = self._investigation_documents(document_evidence)
        audit_reports = self._audit_reports(document_evidence)

        if amount_filter and structured_evidence:
            return self._build_amount_based_finding(
                structured_evidence=structured_evidence,
                document_evidence=document_evidence,
                amount_filter=amount_filter,
                query=query,
                intent=intent or {},
            )

        if flagged_transactions:
            evidence_summary = self._build_evidence_summary(
                structured_evidence=structured_evidence,
                document_evidence=document_evidence,
                flagged_transactions=flagged_transactions,
                investigation_documents=investigation_documents,
                audit_reports=audit_reports,
            )
            return {
                "title": "Flagged Transactions Detected",
                "summary": self._build_finding_summary(flagged_transactions, audit_reports, investigation_documents),
                "risk_reasoning": evidence_summary,
                "evidence_summary": evidence_summary,
                "recommendation": "",
                "narrative": self._build_deterministic_narrative(
                    query=query,
                    intent=intent or {},
                    title="Flagged Transactions Detected",
                    summary=self._build_finding_summary(flagged_transactions, audit_reports, investigation_documents),
                    evidence_summary=evidence_summary,
                    recommendation="",
                ),
                "supporting_documents": self._supporting_documents(document_evidence),
            }

        if audit_reports or investigation_documents:
            evidence_summary = self._build_document_only_evidence_summary(audit_reports, investigation_documents)
            return {
                "title": "Supporting Audit Documents Retrieved",
                "summary": "Related audit documents were found even though the transaction evidence did not flag a direct issue.",
                "risk_reasoning": evidence_summary,
                "evidence_summary": evidence_summary,
                "recommendation": "",
                "narrative": self._build_deterministic_narrative(
                    query=query,
                    intent=intent or {},
                    title="Supporting Audit Documents Retrieved",
                    summary="Related audit documents were found even though the transaction evidence did not flag a direct issue.",
                    evidence_summary=evidence_summary,
                    recommendation="",
                ),
                "supporting_documents": self._supporting_documents(document_evidence),
            }

        evidence_summary = "Structured evidence was found, but it did not meet the deterministic finding rules."
        summary = "Relevant evidence was retrieved, but no flagged transactions or supporting audit reports were identified."
        return {
            "title": "Evidence Retrieved",
            "summary": summary,
            "risk_reasoning": evidence_summary,
            "evidence_summary": evidence_summary,
            "recommendation": "",
            "narrative": self._build_deterministic_narrative(
                query=query,
                intent=intent or {},
                title="Evidence Retrieved",
                summary=summary,
                evidence_summary=evidence_summary,
                recommendation="",
            ),
            "supporting_documents": self._supporting_documents(document_evidence),
        }

    def _generate_llm_finding(
        self,
        *,
        query: str,
        intent: dict[str, Any],
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        investigation_context: dict[str, Any],
        deterministic: dict[str, Any],
    ) -> dict[str, Any]:
        finding_messages = build_finding_generation_messages(
            query=query,
            intent=intent,
            structured_evidence=structured_evidence,
            document_evidence=document_evidence,
            citations=citations,
            investigation_context=investigation_context,
        )
        recommendation_messages = build_recommendation_messages(
            query=query,
            finding=deterministic,
            structured_evidence=structured_evidence,
            document_evidence=document_evidence,
            policy_context=investigation_context.get("policy_context"),
        )
        narrative_messages = build_narrative_messages(
            query=query,
            finding=deterministic,
            structured_evidence=structured_evidence,
            document_evidence=document_evidence,
            citations=citations,
            investigation_context=investigation_context,
        )

        finding_output = self._call_llm_json(finding_messages)
        recommendation_output = self._call_llm_json(recommendation_messages)
        narrative_output = self._call_llm_json(narrative_messages)

        return {
            "title": str(finding_output.get("title") or deterministic.get("title") or deterministic.get("finding_title") or "Evidence Retrieved"),
            "summary": str(finding_output.get("summary") or deterministic.get("summary") or deterministic.get("finding_summary") or ""),
            "risk_reasoning": str(
                finding_output.get("risk_reasoning")
                or finding_output.get("supporting_evidence_explanation")
                or deterministic.get("risk_reasoning")
                or deterministic.get("evidence_summary")
                or ""
            ),
            "evidence_summary": str(
                finding_output.get("supporting_evidence_explanation")
                or finding_output.get("risk_reasoning")
                or deterministic.get("evidence_summary")
                or ""
            ),
            "recommendation": str(
                recommendation_output.get("recommendation")
                or deterministic.get("recommendation")
                or ""
            ),
            "narrative": str(narrative_output.get("narrative") or deterministic.get("narrative") or ""),
        }

    def _flagged_transactions(self, structured_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in structured_evidence if str(row.get("status", "")).upper() == "FLAGGED"]

    def _audit_reports(self, document_evidence: list[dict[str, Any]]) -> list[str]:
        report_labels: list[str] = []
        for document in document_evidence:
            document_type = str(document.get("document_type", "")).upper()
            if "AUDIT_REPORT" in document_type or str(document.get("document_category", "")).lower() == "audit_reports":
                label = document.get("file_name") or document.get("document_id")
                if label and label not in report_labels:
                    report_labels.append(str(label))
        return report_labels

    def _investigation_documents(self, document_evidence: list[dict[str, Any]]) -> list[str]:
        labels: list[str] = []
        for document in document_evidence:
            document_type = str(document.get("document_type", "")).upper()
            if "INVESTIGATION" in document_type or str(document.get("document_category", "")).lower() == "investigation_reports":
                label = document.get("file_name") or document.get("document_id")
                if label and label not in labels:
                    labels.append(str(label))
        return labels

    def _supporting_documents(self, document_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        supporting_documents: list[dict[str, Any]] = []
        for document in document_evidence:
            supporting_documents.append(
                {
                    "document_id": document.get("document_id"),
                    "linked_transaction": document.get("linked_transaction"),
                    "reason_selected": document.get("reason_selected"),
                    "content_snippet": document.get("content_snippet", ""),
                }
            )
        return supporting_documents

    def _amount_filter(self, intent: dict[str, Any]) -> dict[str, Any] | None:
        filters = intent.get("filters")
        if not isinstance(filters, dict):
            return None
        amount_filter = filters.get("amount")
        if not isinstance(amount_filter, dict):
            return None
        operator = str(amount_filter.get("operator", "")).strip()
        value = amount_filter.get("value")
        if operator not in {"<", "<=", ">", ">="} or value is None:
            return None
        return {"operator": operator, "value": value}

    def _build_amount_based_finding(
        self,
        *,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        amount_filter: dict[str, Any],
        query: str = "",
        intent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        operator = amount_filter["operator"]
        value = amount_filter["value"]
        completed_count = sum(1 for row in structured_evidence if str(row.get("status", "")).upper() == "COMPLETED")
        top_transactions = structured_evidence[:3]
        supporting_documents = self._supporting_documents(document_evidence)

        if operator in {"<", "<="}:
            title = "Low-Value Transactions Identified"
            summary = f"{len(structured_evidence)} transactions below the threshold of {value} were identified."
            recommendation = "Continue monitoring low-value transaction activity. Review the linked escalation email for historical context."
        else:
            title = "High-Value Transactions Identified"
            summary = f"{len(structured_evidence)} transactions above the threshold of {value} were identified."
            recommendation = "Review approval authority and escalation controls."

        evidence_lines = [
            f"{len(structured_evidence)} transactions matched the amount filter.",
        ]
        if completed_count == len(structured_evidence) and structured_evidence:
            evidence_lines.append("All retrieved transactions are completed.")
        if top_transactions:
            top_labels = ", ".join(
                f"{row.get('transaction_id')} ({row.get('amount')})"
                for row in top_transactions
                if row.get("transaction_id")
            )
            if top_labels:
                evidence_lines.append(f"Top 3 transactions: {top_labels}.")
        if supporting_documents:
            evidence_lines.append(f"{len(supporting_documents)} related document(s) were linked.")
            first_document = supporting_documents[0]
            snippet = first_document.get("content_snippet") or ""
            if snippet:
                evidence_lines.append(f"Supporting evidence snippet: {snippet}")

        if any(str(doc.get("document_category", "")).lower() == "emails" for doc in document_evidence):
            evidence_lines.append("One related escalation email was identified.")
            if operator in {"<", "<="}:
                recommendation = (
                    "Continue monitoring low-value transaction activity. Review the linked escalation email for historical context."
                )

        evidence_summary = " ".join(evidence_lines)
        return {
            "title": title,
            "finding_title": title,
            "summary": summary,
            "finding_summary": summary,
            "risk_reasoning": evidence_summary,
            "evidence_summary": evidence_summary,
            "recommendation": recommendation,
            "narrative": self._build_deterministic_narrative(
                query=query,
                intent=intent or {},
                title=title,
                summary=summary,
                evidence_summary=evidence_summary,
                recommendation=recommendation,
            ),
            "supporting_documents": supporting_documents,
        }

    def _build_finding_summary(
        self,
        flagged_transactions: list[dict[str, Any]],
        audit_reports: list[str],
        investigation_documents: list[str],
    ) -> str:
        summary = f"{len(flagged_transactions)} flagged transactions were identified."
        if audit_reports:
            summary += f" Supporting audit reports were linked: {', '.join(audit_reports)}."
        if investigation_documents:
            summary += f" Investigation documents were linked: {', '.join(investigation_documents)}."
        return summary

    def _build_evidence_summary(
        self,
        *,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        flagged_transactions: list[dict[str, Any]],
        investigation_documents: list[str],
        audit_reports: list[str],
    ) -> str:
        top_transactions = flagged_transactions[:3]
        top_labels = ", ".join(
            f"{row.get('transaction_id')} ({row.get('amount')})"
            for row in top_transactions
            if row.get("transaction_id")
        )
        parts = [
            f"{len(structured_evidence)} transaction(s) matched the current criteria.",
        ]
        if top_labels:
            parts.append(f"Top 3 transactions: {top_labels}.")
        if document_evidence:
            parts.append(f"{len(document_evidence)} related document(s) were linked.")
        if audit_reports:
            parts.append(f"Audit reports: {', '.join(audit_reports)}.")
        if investigation_documents:
            parts.append(f"Investigation documents: {', '.join(investigation_documents)}.")
        return " ".join(parts)

    def _build_document_only_evidence_summary(self, audit_reports: list[str], investigation_documents: list[str]) -> str:
        parts: list[str] = []
        if audit_reports:
            parts.append(f"Audit reports: {', '.join(audit_reports)}.")
        if investigation_documents:
            parts.append(f"Investigation documents: {', '.join(investigation_documents)}.")
        return " ".join(parts) if parts else "No supporting documents were linked."

    def _call_llm_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Run pip install -r backend/requirements.txt.") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            messages=messages,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response.")
        return self._parse_llm_json(content)

    @staticmethod
    def _parse_llm_json(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response must be a JSON object.")
        return parsed

    def _normalize_finding(self, finding: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(finding)
        title = str(normalized.get("title") or normalized.get("finding_title") or "Evidence Retrieved").strip()
        summary = str(normalized.get("summary") or normalized.get("finding_summary") or "").strip()
        risk_reasoning = str(normalized.get("risk_reasoning") or normalized.get("evidence_summary") or summary).strip()
        recommendation = str(normalized.get("recommendation") or "").strip()
        narrative = str(normalized.get("narrative") or "").strip()
        if not narrative:
            narrative = self._build_deterministic_narrative(
                query=str(normalized.get("query", "")),
                intent=normalized.get("intent", {}) if isinstance(normalized.get("intent"), dict) else {},
                title=title,
                summary=summary,
                evidence_summary=risk_reasoning,
                recommendation=recommendation,
            )
        supporting_documents = normalized.get("supporting_documents")
        if not isinstance(supporting_documents, list):
            supporting_documents = []

        normalized.update(
            {
                "title": title,
                "finding_title": title,
                "summary": summary,
                "finding_summary": summary,
                "risk_reasoning": risk_reasoning,
                "evidence_summary": str(normalized.get("evidence_summary") or risk_reasoning).strip(),
                "recommendation": recommendation,
                "narrative": narrative,
                "supporting_documents": supporting_documents,
            }
        )
        return normalized

    @staticmethod
    def _build_deterministic_narrative(
        *,
        query: str,
        intent: dict[str, Any],
        title: str,
        summary: str,
        evidence_summary: str,
        recommendation: str,
    ) -> str:
        intent_text = intent.get("intent") or intent.get("query_type") or "audit query"
        parts = [
            f"Query reviewed: {query or 'n/a'}.",
            f"Intent: {intent_text}.",
            f"Finding: {title}.",
            summary or "No summary was generated.",
            f"Evidence basis: {evidence_summary or 'No evidence summary was generated.'}.",
        ]
        if recommendation:
            parts.append(f"Recommendation: {recommendation}.")
        return " ".join(part.strip() for part in parts if part and part.strip())
