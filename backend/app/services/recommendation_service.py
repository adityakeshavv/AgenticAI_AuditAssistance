from __future__ import annotations

from typing import Any


class RecommendationService:
    """Deterministic, evidence-grounded recommendation fallback.

    This is only invoked when the LLM-driven recommendation path
    (app.prompts.recommendation_prompt + the OpenAI call in
    base_investigation_service / finding_generation_service) is unavailable
    or returns nothing. It must still produce a recommendation that is
    specific to what was actually found, not a single canned sentence.
    """

    def recommend(
        self,
        *,
        finding_title: str,
        structured_evidence: list[dict[str, Any]],
        document_evidence: list[dict[str, Any]],
    ) -> str:
        if not structured_evidence and not document_evidence:
            return "No evidence was retrieved for this query; broaden the search criteria or verify the entity identifiers before drawing a conclusion."

        source_types = {str(row.get("source_type", "")).lower() for row in structured_evidence}

        if "compliance_record" in source_types:
            return self._compliance_recommendation(structured_evidence)
        if "approval_workflow" in source_types:
            return self._approval_recommendation(structured_evidence)
        if "expense_claim" in source_types:
            return self._expense_recommendation(structured_evidence)

        flagged_transactions = self._flagged_transactions(structured_evidence)
        investigation_documents = self._documents_by_category(document_evidence, {"investigation_reports"})
        audit_documents = self._documents_by_category(document_evidence, {"audit_reports"})

        if not flagged_transactions:
            if structured_evidence:
                return f"Reviewed {len(structured_evidence)} record(s) with no flagged items; continue periodic monitoring at the standard audit cadence."
            return "Continue periodic monitoring; no high-risk indicators were identified in the retrieved evidence."

        vendor_ids = sorted({str(row.get("vendor_id")) for row in flagged_transactions if row.get("vendor_id")})
        transaction_ids = sorted({str(row.get("transaction_id")) for row in flagged_transactions if row.get("transaction_id")})
        entity_ref = vendor_ids[0] if vendor_ids else (transaction_ids[0] if transaction_ids else None)
        entity_clause = f" related to {entity_ref}" if entity_ref else ""

        if investigation_documents:
            return (
                f"Escalate the {len(flagged_transactions)} flagged transaction(s){entity_clause} for immediate review; "
                f"an existing investigation report is already on file and should be cross-referenced before closing this finding."
            )

        if audit_documents:
            return (
                f"Review the approval workflow and supporting audit documentation for the {len(flagged_transactions)} "
                f"flagged transaction(s){entity_clause}; corroborate against the linked audit report before escalating."
            )

        if "approval" in finding_title.lower():
            return f"Verify approval authority and escalation controls for the {len(flagged_transactions)} flagged transaction(s){entity_clause}."

        return (
            f"Review the approval workflow and request supporting documentation for the {len(flagged_transactions)} "
            f"flagged transaction(s){entity_clause}, as no corroborating report was found in the document store."
        )

    def _compliance_recommendation(self, structured_evidence: list[dict[str, Any]]) -> str:
        records = [r for r in structured_evidence if str(r.get("source_type", "")).lower() == "compliance_record"]
        expired = [r for r in records if str(r.get("status", "")).upper() == "EXPIRED"]
        non_compliant = [r for r in records if str(r.get("status", "")).upper() == "NON_COMPLIANT"]
        vendor_ids = sorted({str(r.get("vendor_id")) for r in records if r.get("vendor_id")})
        entity_clause = f" for vendor {vendor_ids[0]}" if len(vendor_ids) == 1 else (f" across {len(vendor_ids)} vendors" if vendor_ids else "")

        if expired:
            frameworks = sorted({str(r.get("framework")) for r in expired if r.get("framework")})
            framework_clause = f" ({', '.join(frameworks)})" if frameworks else ""
            return f"Re-certify the {len(expired)} expired compliance record(s){framework_clause}{entity_clause} before approving further transactions with the affected vendor(s)."
        if non_compliant:
            return f"Suspend new commitments{entity_clause} until the {len(non_compliant)} non-compliant record(s) are remediated and re-assessed."
        return f"Confirm the current compliance status{entity_clause} is up to date and properly documented."

    def _approval_recommendation(self, structured_evidence: list[dict[str, Any]]) -> str:
        records = [r for r in structured_evidence if str(r.get("source_type", "")).lower() == "approval_workflow"]
        exceeded = [r for r in records if r.get("exceeded_authority")]
        rejected = [r for r in records if str(r.get("approval_status", "")).upper() == "REJECTED"]
        escalated = [r for r in records if str(r.get("approval_status", "")).upper() == "ESCALATED"]

        if exceeded:
            tx_ids = sorted({str(r.get("transaction_id")) for r in exceeded if r.get("transaction_id")})
            tx_clause = f" ({', '.join(tx_ids[:3])}{'…' if len(tx_ids) > 3 else ''})" if tx_ids else ""
            return f"Escalate the {len(exceeded)} approval(s) that exceeded the approver's authorized limit{tx_clause} to the next approval tier and review delegation controls."
        if escalated:
            return f"Confirm resolution status for the {len(escalated)} escalated approval(s) and document the final approving authority."
        if rejected:
            return f"Confirm that the {len(rejected)} rejected approval(s) did not proceed to payment and that the rejection reason was properly logged."
        return "Verify the approval chain is complete and properly authorized for the retrieved transactions."

    def _expense_recommendation(self, structured_evidence: list[dict[str, Any]]) -> str:
        records = [r for r in structured_evidence if str(r.get("source_type", "")).lower() == "expense_claim"]
        flagged = [r for r in records if str(r.get("approval_status", "")).upper() == "FLAGGED"]
        missing_receipt = [r for r in records if r.get("receipt_attached") is False]

        if flagged:
            return f"Review the {len(flagged)} flagged expense claim(s) against company travel/expense policy before reimbursement is finalized."
        if missing_receipt:
            return f"Request supporting receipts for the {len(missing_receipt)} claim(s) currently missing documentation before approval."
        return "Confirm all retrieved expense claims have valid receipts and conform to the applicable expense policy."

    def _flagged_transactions(self, structured_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in structured_evidence if str(row.get("status", "")).upper() == "FLAGGED"]

    def _documents_by_category(self, document_evidence: list[dict[str, Any]], categories: set[str]) -> list[dict[str, Any]]:
        return [
            document
            for document in document_evidence
            if str(document.get("document_category", "")).strip().lower() in categories
        ]
