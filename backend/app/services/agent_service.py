from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.document_retrieval_agent_service import DocumentRetrievalAgent
from app.services.evidence_aggregator_service import EvidenceAggregatorService
from app.services.llm_router_service import StructuredIntentService
from app.services.response_composer_service import ResponseComposerService
from app.services.traceability_service import TraceabilityService
from app.services.transaction_service import TRANSACTION_ALLOWED_INTENTS, execute_transaction_query


class AgentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.intent_service = StructuredIntentService()
        self.traceability_service = TraceabilityService()
        self.document_agent = DocumentRetrievalAgent(db)
        self.evidence_aggregator = EvidenceAggregatorService()
        self.response_composer = ResponseComposerService()

    def run(self, *, query: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        traceability = self.traceability_service.initialize()
        response_contract: dict[str, Any] = {
            "success": True,
            "query": query,
            "intent": {},
            "agents_used": [],
            "structured_evidence": [],
            "document_evidence": [],
            "sources": [],
            "reasoning": [],
            "finding": "",
            "final_response": "",
            "traceability": traceability,
            "message": None,
        }

        structured_intent = self.intent_service.extract(
            query,
            domain="transaction",
            entity="transaction",
            allowed_intents=TRANSACTION_ALLOWED_INTENTS,
        )
        response_contract["intent"] = structured_intent
        self.traceability_service.record_reasoning(
            traceability,
            "Structured intent extracted for the transaction audit workflow.",
        )

        if not structured_intent.get("supported"):
            response_contract["success"] = False
            response_contract["finding"] = "This query does not appear to be related to the supported audit workflow."
            response_contract["final_response"] = response_contract["finding"]
            self.traceability_service.record_reasoning(
                traceability,
                "Query was rejected because the extracted intent was unsupported.",
            )
            return self.response_composer.compose(response_contract)

        self.traceability_service.record_agent(
            traceability,
            "transaction_agent",
            "Structured intent mapped to transaction retrieval.",
        )

        transaction_result = execute_transaction_query(self.db, query, page=page, page_size=page_size)
        response_contract["structured_evidence"] = list(transaction_result.get("results", []))

        if not transaction_result.get("success", False):
            response_contract["success"] = False
            response_contract["message"] = transaction_result.get("message")
            response_contract["finding"] = transaction_result.get("message") or "Transaction retrieval failed."
            self.traceability_service.record_reasoning(
                traceability,
                "Transaction retrieval did not return a supported result set.",
            )
            return self.response_composer.compose(response_contract)

        self.traceability_service.record_source(traceability, "transaction_master")
        self.traceability_service.record_reasoning(
            traceability,
            f"Transaction agent returned {len(response_contract['structured_evidence'])} record(s).",
        )

        document_result = self.document_agent.retrieve(
            query=query,
            structured_intent=structured_intent,
            transaction_results=response_contract["structured_evidence"],
        )
        response_contract["document_evidence"] = list(document_result.get("documents", []))

        if response_contract["document_evidence"]:
            self.traceability_service.record_agent(
                traceability,
                "document_retrieval_agent",
                "Related document metadata was available for the retrieved structured records.",
            )
            self.traceability_service.record_source(traceability, "document_metadata")
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
        )
        response_contract["structured_evidence"] = aggregator_output["structured_evidence"]
        response_contract["document_evidence"] = aggregator_output["document_evidence"]
        response_contract["sources"] = aggregator_output["sources"]

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

        response_contract = self.response_composer.compose(response_contract)
        response_contract["agents_used"] = list(traceability.get("agents_invoked", []))
        return response_contract
