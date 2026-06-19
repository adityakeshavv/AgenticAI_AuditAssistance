from __future__ import annotations

from typing import Any


class ResponseComposerService:
    def compose(self, response_contract: dict[str, Any]) -> dict[str, Any]:
        structured_count = len(response_contract.get("structured_evidence", []))
        document_count = len(response_contract.get("document_evidence", []))
        intent = response_contract.get("intent", {})
        query = response_contract.get("query", "")

        if not response_contract.get("success", True):
            finding = response_contract.get(
                "finding",
                "This query could not be mapped to the currently supported audit workflow.",
            )
        elif structured_count and document_count:
            finding = f"Retrieved {structured_count} structured record(s) and {document_count} related document reference(s)."
        elif structured_count:
            finding = f"Retrieved {structured_count} structured record(s) from the transaction workflow."
        elif document_count:
            finding = f"Retrieved {document_count} related document reference(s)."
        else:
            finding = "No matching records or related document references were found."

        reasoning = list(response_contract.get("traceability", {}).get("reasoning_path", []))
        if not reasoning:
            reasoning = [
                "Intent was extracted from the user query.",
                "Agents were invoked based on the extracted intent.",
                "Structured evidence and document evidence were combined.",
            ]

        final_response = (
            f"Query: {query}. "
            f"Intent: {intent.get('intent') or 'unsupported'}. "
            f"{finding}"
        )

        response_contract["finding"] = finding
        response_contract["reasoning"] = reasoning
        response_contract["final_response"] = final_response
        return response_contract
