from __future__ import annotations

from typing import Any


class RiskScoringService:
    def score(
        self,
        *,
        finding: dict[str, Any] | None = None,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
        trace_context: Any | None = None,
    ) -> dict[str, Any]:
        span = trace_context.begin_span(
            "risk_scoring",
            input_payload={
                "finding_title": (finding or {}).get("finding_title") if isinstance(finding, dict) else None,
                "structured_count": len(structured_evidence),
                "document_count": len(document_evidence),
            },
            metadata={"service": "RiskScoringService"},
        ) if trace_context else None

        risk_score = 0
        risk_drivers: list[str] = []

        flagged_transactions = self._flagged_transactions(structured_evidence)
        high_risk_transactions = self._high_risk_transactions(structured_evidence)
        investigation_documents = self._documents_by_category(document_evidence, {"investigation_reports"})
        escalation_emails = self._documents_by_keywords(document_evidence, {"emails"}, {"ESCALATION", "ESC", "ALERT"})
        audit_documents = self._documents_by_category(document_evidence, {"audit_reports"})
        approval_emails = self._documents_by_keywords(document_evidence, {"emails"}, {"APPROVAL"})
        meeting_minutes = self._documents_by_category(document_evidence, {"meeting_minutes"})
        document_signals = self._document_signals(document_evidence)
        amount_band = self._amount_band(structured_evidence)
        evidence_volume_score, evidence_volume_driver = self._evidence_volume_score(len(structured_evidence))

        if not self._has_meaningful_evidence(finding, structured_evidence, document_evidence):
            result = {
                "risk_rating": "LOW",
                "risk_score": 0,
                "risk_drivers": [],
            }
            if span:
                span.finish(output=result, metadata=result)
            return result

        if flagged_transactions:
            flagged_score, flagged_driver = self._flagged_transaction_score(len(flagged_transactions))
            risk_score += flagged_score
            risk_drivers.append(flagged_driver)

        if high_risk_transactions:
            high_risk_score, high_risk_driver = self._high_risk_transaction_score(len(high_risk_transactions))
            risk_score += high_risk_score
            risk_drivers.append(high_risk_driver)

        if amount_band:
            amount_score, amount_driver = self._amount_score(amount_band)
            risk_score += amount_score
            risk_drivers.append(amount_driver)

        if evidence_volume_score:
            risk_score += evidence_volume_score
            risk_drivers.append(evidence_volume_driver)

        if investigation_documents:
            risk_score += 3
            risk_drivers.append(
                "Investigation report detected: " + ", ".join(self._document_labels(investigation_documents))
            )

        if escalation_emails:
            risk_score += 2
            risk_drivers.append("Escalation email detected: " + ", ".join(self._document_labels(escalation_emails)))

        if audit_documents:
            risk_score += 2
            risk_drivers.append("Audit report detected: " + ", ".join(self._document_labels(audit_documents)))

        if approval_emails:
            risk_score += 1
            risk_drivers.append("Approval email detected: " + ", ".join(self._document_labels(approval_emails)))

        if meeting_minutes:
            risk_score += 1
            risk_drivers.append("Meeting minutes detected: " + ", ".join(self._document_labels(meeting_minutes)))

        signal_score, signal_drivers = self._signal_score(document_signals)
        risk_score += signal_score
        risk_drivers.extend(signal_drivers)

        if len(document_evidence) > 3:
            risk_score += 1
            risk_drivers.append("Multiple supporting documents identified")

        risk_rating = self._rating_from_score(risk_score)
        result = {
            "risk_rating": risk_rating,
            "risk_score": risk_score,
            "risk_drivers": risk_drivers,
        }
        if span:
            span.finish(output=result, metadata=result)
        return result

    def _flagged_transactions(self, structured_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in structured_evidence if str(row.get("status", "")).upper() == "FLAGGED"]

    def _high_risk_transactions(self, structured_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        high_risk_rows: list[dict[str, Any]] = []
        for row in structured_evidence:
            try:
                risk_score = float(row.get("risk_score") or 0)
            except (TypeError, ValueError):
                continue
            if risk_score > 0.8:
                high_risk_rows.append(row)
        return high_risk_rows

    def _amount_band(self, structured_evidence: list[dict[str, Any]]) -> str | None:
        max_amount = 0.0
        for row in structured_evidence:
            try:
                amount = float(row.get("amount") or 0)
            except (TypeError, ValueError):
                continue
            if amount > max_amount:
                max_amount = amount

        if max_amount > 1_000_000:
            return "gt_1000000"
        if max_amount > 500_000:
            return "gt_500000"
        if max_amount > 50_000:
            return "gt_50000"
        return None

    def _amount_score(self, amount_band: str) -> tuple[int, str]:
        if amount_band == "gt_1000000":
            return 3, "Maximum transaction amount exceeded 1,000,000"
        if amount_band == "gt_500000":
            return 2, "Maximum transaction amount exceeded 500,000"
        if amount_band == "gt_50000":
            return 1, "Maximum transaction amount exceeded 50,000"
        return 0, ""

    def _flagged_transaction_score(self, count: int) -> tuple[int, str]:
        if count <= 2:
            return 1, f"{count} flagged transaction(s) detected"
        if count <= 5:
            return 2, f"{count} flagged transaction(s) detected"
        return 3, f"{count} flagged transaction(s) detected"

    def _high_risk_transaction_score(self, count: int) -> tuple[int, str]:
        if count <= 2:
            return 1, f"{count} transaction(s) exceeded risk threshold 0.8"
        if count <= 5:
            return 2, f"{count} transaction(s) exceeded risk threshold 0.8"
        return 3, f"{count} transaction(s) exceeded risk threshold 0.8"

    def _evidence_volume_score(self, count: int) -> tuple[int, str]:
        if count > 25:
            return 2, f"{count} matching transactions identified"
        if count > 10:
            return 1, f"{count} matching transactions identified"
        return 0, ""

    def _documents_by_category(self, document_evidence: list[dict[str, Any]], categories: set[str]) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for document in document_evidence:
            category = str(document.get("document_category", "")).strip().lower()
            if category in categories:
                matches.append(document)
        return matches

    def _document_signals(self, document_evidence: list[dict[str, Any]]) -> list[str]:
        signals: list[str] = []
        for document in document_evidence:
            intelligence = document.get("document_intelligence")
            if not isinstance(intelligence, dict):
                continue
            for signal in intelligence.get("signals", []):
                if signal not in signals:
                    signals.append(signal)
        return signals

    def _signal_score(self, signals: list[str]) -> tuple[int, list[str]]:
        score = 0
        drivers: list[str] = []
        for signal in signals:
            if signal == "escalation requested":
                score += 2
                drivers.append("Escalation requested in supporting document")
            elif signal == "policy violation":
                score += 3
                drivers.append("Policy violation identified in supporting document")
            elif signal == "audit exception":
                score += 3
                drivers.append("Audit exception identified in supporting document")
            elif signal == "missing approval":
                score += 2
                drivers.append("Missing approval identified in supporting document")
            elif signal == "investigation opened":
                score += 3
                drivers.append("Investigation opened in supporting document")
            elif signal == "contract expiry":
                score += 2
                drivers.append("Contract expiry identified in supporting document")
            elif signal == "approval limit exceeded":
                score += 2
                drivers.append("Approval limit exceeded in supporting document")
            elif signal == "compliance concern":
                score += 2
                drivers.append("Compliance concern identified in supporting document")
        return score, drivers

    def _documents_by_keywords(
        self,
        document_evidence: list[dict[str, Any]],
        categories: set[str],
        keywords: set[str],
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for document in document_evidence:
            category = str(document.get("document_category", "")).strip().lower()
            if category not in categories:
                continue
            haystack = " ".join(
                str(document.get(field, "")).upper()
                for field in ("document_id", "file_name", "reason_selected", "content_snippet")
            )
            if any(keyword in haystack for keyword in keywords):
                matches.append(document)
        return matches

    def _document_labels(self, documents: list[dict[str, Any]]) -> list[str]:
        labels: list[str] = []
        for document in documents:
            label = document.get("document_id") or document.get("file_name")
            if label:
                labels.append(str(label))
        return labels

    def _rating_from_score(self, risk_score: int) -> str:
        if risk_score <= 2:
            return "LOW"
        if risk_score <= 5:
            return "MEDIUM"
        if risk_score <= 8:
            return "HIGH"
        return "CRITICAL"

    def _has_meaningful_evidence(
        self,
        finding: dict[str, Any] | None,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
    ) -> bool:
        if structured_evidence or document_evidence:
            return True
        if not finding:
            return False
        title = str(finding.get("finding_title", "")).strip().lower()
        summary = str(finding.get("finding_summary", "")).strip().lower()
        return bool(title or summary)
