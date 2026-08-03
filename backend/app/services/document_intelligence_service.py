from __future__ import annotations

import re
from typing import Any


class DocumentIntelligenceService:
    DOCUMENT_TYPE_MAP = {
        "audit report": "Audit Report",
        "investigation report": "Investigation Report",
        "escalation email": "Escalation Email",
        "approval email": "Approval Email",
        "meeting minutes": "Meeting Minutes",
        "policy": "Policy",
        "sop": "SOP",
        "contract": "Contract",
        "email": "Escalation Email",
        "spreadsheet": "Spreadsheet",
    }

    SIGNAL_RULES = [
        ("approval limit exceeded", {"approval limit exceeded", "above approval limit", "approval threshold exceeded"}, 2),
        ("escalation requested", {"escalation requested", "please escalate", "escalate this", "urgent escalation"}, 2),
        ("policy violation", {"policy violation", "policy breach", "non-compliance", "contrary to policy", "violated policy"}, 3),
        ("audit exception", {"audit exception", "exception noted", "control exception", "audit issue"}, 3),
        ("investigation opened", {"investigation opened", "opened investigation", "formal investigation", "under investigation"}, 3),
        ("contract expiry", {"contract expiry", "expired contract", "contract expired", "renewal required"}, 2),
        ("missing approval", {"missing approval", "no approval", "without approval", "approval not found"}, 2),
        ("compliance concern", {"compliance concern", "compliance risk", "regulatory concern", "controls concern"}, 2),
    ]

    def classify(self, document: dict[str, Any]) -> dict[str, Any]:
        classification = self._classify_document(document)
        signals = self._extract_signals(document, classification)
        risk_contribution = self._risk_contribution(signals)
        return {
            "document_type": classification,
            "signals": signals,
            "risk_contribution": risk_contribution,
        }

    def summarize_documents(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        classifications: dict[str, int] = {}
        signals: dict[str, int] = {}
        risk_contributions: list[str] = []

        for document in documents:
            intelligence = self.classify(document)
            document_type = intelligence["document_type"]
            classifications[document_type] = classifications.get(document_type, 0) + 1
            for signal in intelligence["signals"]:
                signals[signal] = signals.get(signal, 0) + 1
            for contribution in intelligence["risk_contribution"]:
                if contribution not in risk_contributions:
                    risk_contributions.append(contribution)

        return {
            "document_type_counts": classifications,
            "signal_counts": signals,
            "risk_contribution": risk_contributions,
        }

    def _classify_document(self, document: dict[str, Any]) -> str:
        file_name = str(document.get("file_name") or "").lower()
        document_type = str(document.get("document_type") or "").lower()
        if file_name.endswith((".xlsx", ".xlsm", ".xltx", ".xltm", ".csv")) or document_type in {"xlsx", "xlsm", "xltx", "xltm", "csv", "spreadsheet"}:
            return "Spreadsheet"
        haystack = " ".join(
            str(document.get(field, "")).lower()
            for field in ("document_type", "document_category", "file_name", "reason_selected", "content_snippet")
        )
        for needle, label in self.DOCUMENT_TYPE_MAP.items():
            if needle in haystack:
                return label
        if "minutes" in haystack:
            return "Meeting Minutes"
        return "Policy" if "policy" in haystack else "SOP" if "sop" in haystack else "Contract" if "contract" in haystack else "Audit Report"

    def _extract_signals(self, document: dict[str, Any], classification: str) -> list[str]:
        haystack = " ".join(
            str(document.get(field, "")).lower()
            for field in ("document_type", "document_category", "file_name", "reason_selected", "content_snippet")
        )
        signals: list[str] = []
        for signal_name, keywords, _ in self.SIGNAL_RULES:
            if any(keyword in haystack for keyword in keywords):
                signals.append(signal_name)

        if classification == "Investigation Report" and "investigation" not in signals:
            signals.append("investigation opened")
        return list(dict.fromkeys(signals))

    def _risk_contribution(self, signals: list[str]) -> list[str]:
        contributions: list[str] = []
        for signal in signals:
            if signal == "escalation requested":
                contributions.append("Escalation Requested (+2)")
            elif signal == "policy violation":
                contributions.append("Policy Violation (+3)")
            elif signal == "audit exception":
                contributions.append("Audit Exception (+3)")
            elif signal == "missing approval":
                contributions.append("Missing Approval (+2)")
            elif signal == "investigation opened":
                contributions.append("Investigation Opened (+3)")
            elif signal == "contract expiry":
                contributions.append("Contract Expiry (+2)")
            elif signal == "approval limit exceeded":
                contributions.append("Approval Limit Exceeded (+2)")
            elif signal == "compliance concern":
                contributions.append("Compliance Concern (+2)")
        return contributions
