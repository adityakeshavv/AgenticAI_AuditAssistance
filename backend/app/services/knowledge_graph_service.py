from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import (
    ApprovalWorkflow,
    AuditFinding,
    AuditInvestigation,
    ComplianceRecord,
    Contract,
    DocumentMetadata,
    Evidence,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    TransactionMaster,
    Vendor,
)


class KnowledgeGraphService:
    SUPPORTED_ENTITY_TYPES = {
        "vendor",
        "transaction",
        "contract",
        "compliance_record",
        "document_metadata",
        "audit_investigation",
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    def build_entity_graph(self, entity_type: str, entity_id: str, *, limit: int = 25) -> dict[str, Any]:
        normalized_type = self._normalize_entity_type(entity_type)
        if normalized_type not in self.SUPPORTED_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity type: {entity_type}")

        if normalized_type == "vendor":
            root_node_id = self._materialize_vendor_graph(entity_id, limit=limit)
        elif normalized_type == "transaction":
            root_node_id = self._materialize_transaction_graph(entity_id, limit=limit)
        elif normalized_type == "contract":
            root_node_id = self._materialize_contract_graph(entity_id, limit=limit)
        elif normalized_type == "compliance_record":
            root_node_id = self._materialize_compliance_graph(entity_id, limit=limit)
        elif normalized_type == "document_metadata":
            root_node_id = self._materialize_document_graph(entity_id)
        else:
            root_node_id = self._materialize_investigation_graph(entity_id, limit=limit)

        if not root_node_id:
            raise LookupError(f"{normalized_type.title().replace('_', ' ')} {entity_id} was not found.")

        root_node = self._get_node(root_node_id)
        nodes, edges = self._get_neighborhood(root_node_id)
        summary = self._build_summary(normalized_type, entity_id, root_node_id, nodes, edges)
        return {
            "success": True,
            "entity_type": normalized_type,
            "entity_id": entity_id,
            "root_node": root_node,
            "nodes": nodes,
            "edges": edges,
            "summary": summary,
        }

    def view_entity_graph(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        normalized_type = self._normalize_entity_type(entity_type)
        if normalized_type not in self.SUPPORTED_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity type: {entity_type}")

        root_node_id = self._node_id(normalized_type, entity_id)
        root_node = self._get_node(root_node_id)
        if not root_node:
            raise LookupError(f"{normalized_type.title().replace('_', ' ')} {entity_id} was not found.")

        nodes, edges = self._get_neighborhood(root_node_id)
        summary = self._build_summary(normalized_type, entity_id, root_node_id, nodes, edges)
        return {
            "success": True,
            "entity_type": normalized_type,
            "entity_id": entity_id,
            "root_node": root_node,
            "nodes": nodes,
            "edges": edges,
            "summary": summary,
        }

    def _materialize_vendor_graph(self, vendor_id: str, *, limit: int) -> str | None:
        vendor = self.db.get(Vendor, vendor_id)
        if not vendor:
            return None

        now = datetime.now(timezone.utc)
        vendor_node_id = self._upsert_node(
            entity_type="vendor",
            entity_id=vendor.vendor_id,
            display_label=vendor.vendor_name,
            node_kind="vendor",
            attributes={
                "vendor_type": vendor.vendor_type,
                "country": vendor.country,
                "risk_rating": vendor.risk_rating,
                "status": vendor.status,
                "registration_no": vendor.registration_no,
                "onboarding_date": vendor.onboarding_date.isoformat() if vendor.onboarding_date else None,
            },
            timestamp=now,
        )

        transactions = list(
            self.db.scalars(
                select(TransactionMaster)
                .where(TransactionMaster.vendor_id == vendor_id)
                .order_by(TransactionMaster.transaction_date.desc(), TransactionMaster.created_at.desc())
                .limit(limit)
            ).all()
        )
        contracts = list(
            self.db.scalars(
                select(Contract)
                .where(Contract.vendor_id == vendor_id)
                .order_by(Contract.end_date.desc(), Contract.created_at.desc())
                .limit(limit)
            ).all()
        )
        compliance_records = list(
            self.db.scalars(
                select(ComplianceRecord)
                .where(ComplianceRecord.vendor_id == vendor_id)
                .order_by(ComplianceRecord.assessment_date.desc(), ComplianceRecord.created_at.desc())
                .limit(limit)
            ).all()
        )

        node_lookup: dict[tuple[str, str], str] = {("vendor", vendor_id): vendor_node_id}

        for transaction in transactions:
            node_id = self._upsert_node(
                entity_type="transaction",
                entity_id=transaction.transaction_id,
                display_label=f"{transaction.transaction_id} · {transaction.currency} {float(transaction.amount):,.2f}",
                node_kind="transaction",
                attributes=self._serialize_transaction(transaction),
                timestamp=now,
            )
            node_lookup[("transaction", transaction.transaction_id)] = node_id
            self._upsert_edge(
                source_node_id=vendor_node_id,
                target_node_id=node_id,
                relationship_type="HAS_TRANSACTION",
                metadata={"source": "transaction_master"},
                timestamp=now,
            )

            approvals = list(
                self.db.scalars(
                    select(ApprovalWorkflow)
                    .where(ApprovalWorkflow.transaction_id == transaction.transaction_id)
                    .order_by(ApprovalWorkflow.approval_date.desc(), ApprovalWorkflow.approval_level.desc())
                ).all()
            )
            for approval in approvals:
                approval_node_id = self._upsert_node(
                    entity_type="approval_workflow",
                    entity_id=approval.approval_id,
                    display_label=f"{approval.approval_id} · {approval.approval_status}",
                    node_kind="workflow",
                    attributes=self._serialize_approval(approval),
                    timestamp=now,
                )
                node_lookup[("approval_workflow", approval.approval_id)] = approval_node_id
                self._upsert_edge(
                    source_node_id=node_id,
                    target_node_id=approval_node_id,
                    relationship_type="HAS_APPROVAL",
                    metadata={"source": "approval_workflow"},
                    timestamp=now,
                )

        for contract in contracts:
            node_id = self._upsert_node(
                entity_type="contract",
                entity_id=contract.contract_id,
                display_label=f"{contract.contract_id} · {contract.status}",
                node_kind="contract",
                attributes=self._serialize_contract(contract),
                timestamp=now,
            )
            node_lookup[("contract", contract.contract_id)] = node_id
            self._upsert_edge(
                source_node_id=vendor_node_id,
                target_node_id=node_id,
                relationship_type="HAS_CONTRACT",
                metadata={"source": "contract"},
                timestamp=now,
            )

        for compliance in compliance_records:
            node_id = self._upsert_node(
                entity_type="compliance_record",
                entity_id=compliance.compliance_id,
                display_label=f"{compliance.framework} · {compliance.status}",
                node_kind="compliance",
                attributes=self._serialize_compliance(compliance),
                timestamp=now,
            )
            node_lookup[("compliance_record", compliance.compliance_id)] = node_id
            self._upsert_edge(
                source_node_id=vendor_node_id,
                target_node_id=node_id,
                relationship_type="HAS_COMPLIANCE_RECORD",
                metadata={"source": "compliance_record"},
                timestamp=now,
            )

        documents = self._fetch_related_documents(
            vendor_id=vendor_id,
            transaction_ids=[transaction.transaction_id for transaction in transactions],
            contract_ids=[contract.contract_id for contract in contracts],
            investigation_ids=None,
        )
        for document in documents:
            self._materialize_document_node(
                document=document,
                node_lookup=node_lookup,
                timestamp=now,
            )

        findings = self._fetch_related_findings(
            vendor_id=vendor_id,
            transaction_ids=[transaction.transaction_id for transaction in transactions],
            contract_ids=[contract.contract_id for contract in contracts],
            compliance_ids=[record.compliance_id for record in compliance_records],
        )
        self._attach_findings(
            findings=findings,
            node_lookup=node_lookup,
            timestamp=now,
        )
        return vendor_node_id

    def _materialize_transaction_graph(self, transaction_id: str, *, limit: int) -> str | None:
        transaction = self.db.get(TransactionMaster, transaction_id)
        if not transaction:
            return None

        now = datetime.now(timezone.utc)
        transaction_node_id = self._upsert_node(
            entity_type="transaction",
            entity_id=transaction.transaction_id,
            display_label=f"{transaction.transaction_id} · {transaction.currency} {float(transaction.amount):,.2f}",
            node_kind="transaction",
            attributes=self._serialize_transaction(transaction),
            timestamp=now,
        )
        node_lookup: dict[tuple[str, str], str] = {("transaction", transaction_id): transaction_node_id}

        vendor = self.db.get(Vendor, transaction.vendor_id)
        if vendor:
            vendor_node_id = self._upsert_node(
                entity_type="vendor",
                entity_id=vendor.vendor_id,
                display_label=vendor.vendor_name,
                node_kind="vendor",
                attributes=self._serialize_vendor(vendor),
                timestamp=now,
            )
            node_lookup[("vendor", vendor.vendor_id)] = vendor_node_id
            self._upsert_edge(
                source_node_id=vendor_node_id,
                target_node_id=transaction_node_id,
                relationship_type="HAS_TRANSACTION",
                metadata={"source": "transaction_master"},
                timestamp=now,
            )

            contracts = list(
                self.db.scalars(
                    select(Contract)
                    .where(Contract.vendor_id == vendor.vendor_id)
                    .order_by(Contract.end_date.desc(), Contract.created_at.desc())
                    .limit(limit)
                ).all()
            )
            for contract in contracts:
                contract_node_id = self._upsert_node(
                    entity_type="contract",
                    entity_id=contract.contract_id,
                    display_label=f"{contract.contract_id} · {contract.status}",
                    node_kind="contract",
                    attributes=self._serialize_contract(contract),
                    timestamp=now,
                )
                node_lookup[("contract", contract.contract_id)] = contract_node_id
                self._upsert_edge(
                    source_node_id=vendor_node_id,
                    target_node_id=contract_node_id,
                    relationship_type="HAS_CONTRACT",
                    metadata={"source": "contract"},
                    timestamp=now,
                )

            compliance_records = list(
                self.db.scalars(
                    select(ComplianceRecord)
                    .where(ComplianceRecord.vendor_id == vendor.vendor_id)
                    .order_by(ComplianceRecord.assessment_date.desc(), ComplianceRecord.created_at.desc())
                    .limit(limit)
                ).all()
            )
            for compliance in compliance_records:
                compliance_node_id = self._upsert_node(
                    entity_type="compliance_record",
                    entity_id=compliance.compliance_id,
                    display_label=f"{compliance.framework} · {compliance.status}",
                    node_kind="compliance",
                    attributes=self._serialize_compliance(compliance),
                    timestamp=now,
                )
                node_lookup[("compliance_record", compliance.compliance_id)] = compliance_node_id
                self._upsert_edge(
                    source_node_id=vendor_node_id,
                    target_node_id=compliance_node_id,
                    relationship_type="HAS_COMPLIANCE_RECORD",
                    metadata={"source": "compliance_record"},
                    timestamp=now,
                )

        approvals = list(
            self.db.scalars(
                select(ApprovalWorkflow)
                .where(ApprovalWorkflow.transaction_id == transaction_id)
                .order_by(ApprovalWorkflow.approval_date.desc(), ApprovalWorkflow.approval_level.desc())
                .limit(limit)
            ).all()
        )
        for approval in approvals:
            approval_node_id = self._upsert_node(
                entity_type="approval_workflow",
                entity_id=approval.approval_id,
                display_label=f"{approval.approval_id} · {approval.approval_status}",
                node_kind="workflow",
                attributes=self._serialize_approval(approval),
                timestamp=now,
            )
            node_lookup[("approval_workflow", approval.approval_id)] = approval_node_id
            self._upsert_edge(
                source_node_id=transaction_node_id,
                target_node_id=approval_node_id,
                relationship_type="HAS_APPROVAL",
                metadata={"source": "approval_workflow"},
                timestamp=now,
            )

        documents = self._fetch_related_documents(
            vendor_id=transaction.vendor_id,
            transaction_ids=[transaction.transaction_id],
            contract_ids=None,
            investigation_ids=None,
        )
        for document in documents:
            self._materialize_document_node(document=document, node_lookup=node_lookup, timestamp=now)

        findings = self._fetch_related_findings(
            vendor_id=transaction.vendor_id,
            transaction_ids=[transaction.transaction_id],
            contract_ids=None,
            compliance_ids=None,
            approval_ids=[approval.approval_id for approval in approvals],
        )
        self._attach_findings(findings=findings, node_lookup=node_lookup, timestamp=now)
        return transaction_node_id

    def _materialize_contract_graph(self, contract_id: str, *, limit: int) -> str | None:
        contract = self.db.get(Contract, contract_id)
        if not contract:
            return None

        now = datetime.now(timezone.utc)
        contract_node_id = self._upsert_node(
            entity_type="contract",
            entity_id=contract.contract_id,
            display_label=f"{contract.contract_id} · {contract.status}",
            node_kind="contract",
            attributes=self._serialize_contract(contract),
            timestamp=now,
        )
        node_lookup: dict[tuple[str, str], str] = {("contract", contract.contract_id): contract_node_id}

        vendor = self.db.get(Vendor, contract.vendor_id)
        if vendor:
            vendor_node_id = self._upsert_node(
                entity_type="vendor",
                entity_id=vendor.vendor_id,
                display_label=vendor.vendor_name,
                node_kind="vendor",
                attributes=self._serialize_vendor(vendor),
                timestamp=now,
            )
            node_lookup[("vendor", vendor.vendor_id)] = vendor_node_id
            self._upsert_edge(
                source_node_id=vendor_node_id,
                target_node_id=contract_node_id,
                relationship_type="HAS_CONTRACT",
                metadata={"source": "contract"},
                timestamp=now,
            )

        documents = self._fetch_related_documents(
            vendor_id=contract.vendor_id,
            transaction_ids=None,
            contract_ids=[contract.contract_id],
            investigation_ids=None,
        )
        for document in documents:
            self._materialize_document_node(document=document, node_lookup=node_lookup, timestamp=now)

        findings = self._fetch_related_findings(
            vendor_id=contract.vendor_id,
            transaction_ids=None,
            contract_ids=[contract.contract_id],
            compliance_ids=None,
        )
        self._attach_findings(findings=findings, node_lookup=node_lookup, timestamp=now)
        return contract_node_id

    def _materialize_compliance_graph(self, compliance_id: str, *, limit: int) -> str | None:
        compliance = self.db.get(ComplianceRecord, compliance_id)
        if not compliance:
            return None

        now = datetime.now(timezone.utc)
        compliance_node_id = self._upsert_node(
            entity_type="compliance_record",
            entity_id=compliance.compliance_id,
            display_label=f"{compliance.framework} · {compliance.status}",
            node_kind="compliance",
            attributes=self._serialize_compliance(compliance),
            timestamp=now,
        )
        node_lookup: dict[tuple[str, str], str] = {("compliance_record", compliance.compliance_id): compliance_node_id}

        vendor = self.db.get(Vendor, compliance.vendor_id)
        if vendor:
            vendor_node_id = self._upsert_node(
                entity_type="vendor",
                entity_id=vendor.vendor_id,
                display_label=vendor.vendor_name,
                node_kind="vendor",
                attributes=self._serialize_vendor(vendor),
                timestamp=now,
            )
            node_lookup[("vendor", vendor.vendor_id)] = vendor_node_id
            self._upsert_edge(
                source_node_id=vendor_node_id,
                target_node_id=compliance_node_id,
                relationship_type="HAS_COMPLIANCE_RECORD",
                metadata={"source": "compliance_record"},
                timestamp=now,
            )

        documents = self._fetch_related_documents(
            vendor_id=compliance.vendor_id,
            transaction_ids=None,
            contract_ids=None,
            investigation_ids=None,
        )
        for document in documents:
            self._materialize_document_node(document=document, node_lookup=node_lookup, timestamp=now)

        findings = self._fetch_related_findings(
            vendor_id=compliance.vendor_id,
            transaction_ids=None,
            contract_ids=None,
            compliance_ids=[compliance.compliance_id],
        )
        self._attach_findings(findings=findings, node_lookup=node_lookup, timestamp=now)
        return compliance_node_id

    def _materialize_document_graph(self, document_id: str) -> str | None:
        document = self.db.get(DocumentMetadata, document_id)
        if not document:
            return None

        now = datetime.now(timezone.utc)
        node_lookup: dict[tuple[str, str], str] = {}

        if document.related_vendor_id:
            vendor = self.db.get(Vendor, document.related_vendor_id)
            if vendor:
                node_lookup[("vendor", vendor.vendor_id)] = self._upsert_node(
                    entity_type="vendor",
                    entity_id=vendor.vendor_id,
                    display_label=vendor.vendor_name,
                    node_kind="vendor",
                    attributes=self._serialize_vendor(vendor),
                    timestamp=now,
                )

        if document.related_transaction_id:
            transaction = self.db.get(TransactionMaster, document.related_transaction_id)
            if transaction:
                node_lookup[("transaction", transaction.transaction_id)] = self._upsert_node(
                    entity_type="transaction",
                    entity_id=transaction.transaction_id,
                    display_label=f"{transaction.transaction_id} · {transaction.currency} {float(transaction.amount):,.2f}",
                    node_kind="transaction",
                    attributes=self._serialize_transaction(transaction),
                    timestamp=now,
                )

        if document.related_contract_id:
            contract = self.db.get(Contract, document.related_contract_id)
            if contract:
                node_lookup[("contract", contract.contract_id)] = self._upsert_node(
                    entity_type="contract",
                    entity_id=contract.contract_id,
                    display_label=f"{contract.contract_id} · {contract.status}",
                    node_kind="contract",
                    attributes=self._serialize_contract(contract),
                    timestamp=now,
                )

        if document.related_investigation_id:
            investigation = self.db.get(AuditInvestigation, document.related_investigation_id)
            if investigation:
                node_lookup[("audit_investigation", investigation.investigation_id)] = self._upsert_node(
                    entity_type="audit_investigation",
                    entity_id=investigation.investigation_id,
                    display_label=investigation.audit_question[:80],
                    node_kind="investigation",
                    attributes=self._serialize_investigation(investigation),
                    timestamp=now,
                )

        document_node_id = self._materialize_document_node(document=document, node_lookup=node_lookup, timestamp=now)

        return document_node_id

    def _materialize_investigation_graph(self, investigation_id: str, *, limit: int) -> str | None:
        investigation = self.db.get(AuditInvestigation, investigation_id)
        if not investigation:
            return None

        now = datetime.now(timezone.utc)
        investigation_node_id = self._upsert_node(
            entity_type="audit_investigation",
            entity_id=investigation.investigation_id,
            display_label=investigation.audit_question[:80],
            node_kind="investigation",
            attributes=self._serialize_investigation(investigation),
            timestamp=now,
        )
        node_lookup: dict[tuple[str, str], str] = {("audit_investigation", investigation.investigation_id): investigation_node_id}

        findings = list(
            self.db.scalars(
                select(AuditFinding)
                .where(AuditFinding.investigation_id == investigation_id)
                .order_by(AuditFinding.updated_at.desc(), AuditFinding.created_at.desc())
                .limit(limit)
            ).all()
        )
        for finding in findings:
            finding_node_id = self._upsert_node(
                entity_type="audit_finding",
                entity_id=finding.finding_id,
                display_label=f"{finding.finding_id} · {finding.severity}",
                node_kind="finding",
                attributes=self._serialize_finding(finding),
                timestamp=now,
            )
            node_lookup[("audit_finding", finding.finding_id)] = finding_node_id
            self._upsert_edge(
                source_node_id=investigation_node_id,
                target_node_id=finding_node_id,
                relationship_type="HAS_FINDING",
                metadata={"source": "audit_finding"},
                timestamp=now,
            )

        documents = list(
            self.db.scalars(
                select(DocumentMetadata)
                .where(DocumentMetadata.related_investigation_id == investigation_id)
                .order_by(DocumentMetadata.creation_date.desc(), DocumentMetadata.created_at.desc())
                .limit(limit)
            ).all()
        )
        for document in documents:
            self._materialize_document_node(document=document, node_lookup=node_lookup, timestamp=now)

        return investigation_node_id

    def _materialize_document_node(
        self,
        *,
        document: DocumentMetadata,
        node_lookup: dict[tuple[str, str], str],
        timestamp: datetime,
    ) -> str:
        document_node_id = self._upsert_node(
            entity_type="document_metadata",
            entity_id=document.document_id,
            display_label=document.file_name,
            node_kind="document",
            attributes=self._serialize_document(document),
            timestamp=timestamp,
        )
        node_lookup[("document_metadata", document.document_id)] = document_node_id

        linked_sources = [
            ("vendor", document.related_vendor_id),
            ("transaction", document.related_transaction_id),
            ("contract", document.related_contract_id),
            ("audit_investigation", document.related_investigation_id),
        ]
        for entity_type, entity_id in linked_sources:
            if not entity_id:
                continue
            source_node_id = node_lookup.get((entity_type, entity_id))
            if not source_node_id:
                source_node = self._get_node(self._node_id(entity_type, entity_id))
                if source_node:
                    source_node_id = source_node["node_id"]
                    node_lookup[(entity_type, entity_id)] = source_node_id
            if source_node_id:
                self._upsert_edge(
                    source_node_id=source_node_id,
                    target_node_id=document_node_id,
                    relationship_type="HAS_DOCUMENT",
                    metadata={"source": "document_metadata"},
                    timestamp=timestamp,
                )
        return document_node_id

    def _attach_findings(
        self,
        *,
        findings: list[dict[str, Any]],
        node_lookup: dict[tuple[str, str], str],
        timestamp: datetime,
    ) -> None:
        if not findings:
            return

        finding_ids = [finding["finding_id"] for finding in findings if finding.get("finding_id")]
        if not finding_ids:
            return

        finding_nodes: dict[str, str] = {}
        for finding in findings:
            finding_id = finding.get("finding_id")
            if not finding_id:
                continue
            finding_node_id = self._upsert_node(
                entity_type="audit_finding",
                entity_id=finding_id,
                display_label=f"{finding_id} · {finding.get('severity', 'UNKNOWN')}",
                node_kind="finding",
                attributes=finding,
                timestamp=timestamp,
            )
            finding_nodes[finding_id] = finding_node_id
            node_lookup[("audit_finding", finding_id)] = finding_node_id

        evidence_rows = list(
            self.db.scalars(
                select(Evidence)
                .where(Evidence.finding_id.in_(finding_ids))
                .order_by(Evidence.retrieved_at.desc(), Evidence.created_at.desc())
            ).all()
        )
        for evidence in evidence_rows:
            finding_node_id = finding_nodes.get(evidence.finding_id)
            if not finding_node_id:
                continue
            source_entity_type = self._source_type_to_entity_type(str(evidence.source_type))
            source_node_id = node_lookup.get((source_entity_type, evidence.source_record_id))
            if not source_node_id:
                continue
            self._upsert_edge(
                source_node_id=source_node_id,
                target_node_id=finding_node_id,
                relationship_type="SUPPORTS_FINDING",
                metadata={
                    "source_type": str(evidence.source_type),
                    "source_table": evidence.source_table,
                    "citation_reference": evidence.citation_reference,
                },
                timestamp=timestamp,
            )

    def _fetch_related_documents(
        self,
        *,
        vendor_id: str | None,
        transaction_ids: list[str] | None,
        contract_ids: list[str] | None,
        investigation_ids: list[str] | None,
    ) -> list[DocumentMetadata]:
        clauses = []
        if vendor_id:
            clauses.append(DocumentMetadata.related_vendor_id == vendor_id)
        if transaction_ids:
            clauses.append(DocumentMetadata.related_transaction_id.in_(transaction_ids))
        if contract_ids:
            clauses.append(DocumentMetadata.related_contract_id.in_(contract_ids))
        if investigation_ids:
            clauses.append(DocumentMetadata.related_investigation_id.in_(investigation_ids))
        if not clauses:
            return []

        stmt = select(DocumentMetadata).where(or_(*clauses)).order_by(
            DocumentMetadata.creation_date.desc(),
            DocumentMetadata.created_at.desc(),
        )
        return list(self.db.scalars(stmt).all())

    def _fetch_related_findings(
        self,
        *,
        vendor_id: str | None,
        transaction_ids: list[str] | None,
        contract_ids: list[str] | None,
        compliance_ids: list[str] | None = None,
        approval_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        clauses = []
        if vendor_id:
            clauses.append((Evidence.source_type == "VENDOR_RECORD") & (Evidence.source_record_id == vendor_id))
        if transaction_ids:
            clauses.append((Evidence.source_type == "TRANSACTION_RECORD") & (Evidence.source_record_id.in_(transaction_ids)))
        if contract_ids:
            clauses.append((Evidence.source_type == "CONTRACT_RECORD") & (Evidence.source_record_id.in_(contract_ids)))
        if compliance_ids:
            clauses.append((Evidence.source_type == "COMPLIANCE_RECORD") & (Evidence.source_record_id.in_(compliance_ids)))
        if approval_ids:
            clauses.append((Evidence.source_type == "APPROVAL_RECORD") & (Evidence.source_record_id.in_(approval_ids)))
        if not clauses:
            return []

        stmt = (
            select(AuditFinding)
            .join(Evidence, AuditFinding.finding_id == Evidence.finding_id)
            .where(or_(*clauses))
            .order_by(AuditFinding.updated_at.desc(), AuditFinding.created_at.desc())
        )
        findings = list(self.db.scalars(stmt).unique().all())
        return [self._serialize_finding(finding) for finding in findings]

    def _upsert_node(
        self,
        *,
        entity_type: str,
        entity_id: str,
        display_label: str,
        node_kind: str,
        attributes: dict[str, Any],
        timestamp: datetime,
    ) -> str:
        node_id = self._node_id(entity_type, entity_id)
        stmt = pg_insert(KnowledgeGraphNode).values(
            node_id=node_id,
            entity_type=entity_type,
            entity_id=entity_id,
            display_label=display_label,
            node_kind=node_kind,
            attributes=attributes,
            created_at=timestamp,
            updated_at=timestamp,
        )
        update_columns = {
            "entity_type": stmt.excluded.entity_type,
            "entity_id": stmt.excluded.entity_id,
            "display_label": stmt.excluded.display_label,
            "node_kind": stmt.excluded.node_kind,
            "attributes": stmt.excluded.attributes,
            "updated_at": stmt.excluded.updated_at,
        }
        self.db.execute(stmt.on_conflict_do_update(index_elements=[KnowledgeGraphNode.node_id], set_=update_columns))
        return node_id

    def _upsert_edge(
        self,
        *,
        source_node_id: str,
        target_node_id: str,
        relationship_type: str,
        metadata: dict[str, Any],
        timestamp: datetime,
        strength: float = 1.0,
    ) -> str:
        edge_id = self._edge_id(source_node_id, target_node_id, relationship_type)
        edge_table = KnowledgeGraphEdge.__table__
        stmt = pg_insert(edge_table).values(
            edge_id=edge_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_type=relationship_type,
            strength=strength,
            metadata=metadata,
            created_at=timestamp,
            updated_at=timestamp,
        )
        update_columns = {
            "source_node_id": stmt.excluded.source_node_id,
            "target_node_id": stmt.excluded.target_node_id,
            "relationship_type": stmt.excluded.relationship_type,
            "strength": stmt.excluded.strength,
            "metadata": stmt.excluded.metadata,
            "updated_at": stmt.excluded.updated_at,
        }
        self.db.execute(stmt.on_conflict_do_update(index_elements=[KnowledgeGraphEdge.edge_id], set_=update_columns))
        return edge_id

    def _get_node(self, node_id: str) -> dict[str, Any] | None:
        node = self.db.get(KnowledgeGraphNode, node_id)
        if not node:
            return None
        return self._serialize_node(node)

    def _get_neighborhood(self, root_node_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        edges = list(
            self.db.scalars(
                select(KnowledgeGraphEdge).where(
                    or_(
                        KnowledgeGraphEdge.source_node_id == root_node_id,
                        KnowledgeGraphEdge.target_node_id == root_node_id,
                    )
                ).order_by(KnowledgeGraphEdge.updated_at.desc(), KnowledgeGraphEdge.created_at.desc())
            ).all()
        )
        node_ids = {root_node_id}
        for edge in edges:
            node_ids.add(edge.source_node_id)
            node_ids.add(edge.target_node_id)
        nodes = list(
            self.db.scalars(
                select(KnowledgeGraphNode).where(KnowledgeGraphNode.node_id.in_(node_ids)).order_by(KnowledgeGraphNode.display_label.asc())
            ).all()
        )
        return [self._serialize_node(node) for node in nodes], [self._serialize_edge(edge) for edge in edges]

    def _build_summary(
        self,
        entity_type: str,
        entity_id: str,
        root_node_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> dict[str, Any]:
        relationship_breakdown = Counter(edge["relationship_type"] for edge in edges)
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "root_node_id": root_node_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "relationship_breakdown": dict(relationship_breakdown),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _serialize_vendor(self, vendor: Vendor) -> dict[str, Any]:
        return {
            "vendor_id": vendor.vendor_id,
            "vendor_name": vendor.vendor_name,
            "vendor_type": vendor.vendor_type,
            "country": vendor.country,
            "registration_no": vendor.registration_no,
            "risk_rating": vendor.risk_rating,
            "onboarding_date": vendor.onboarding_date.isoformat() if vendor.onboarding_date else None,
            "status": vendor.status,
        }

    def _serialize_transaction(self, transaction: TransactionMaster) -> dict[str, Any]:
        return {
            "transaction_id": transaction.transaction_id,
            "transaction_date": transaction.transaction_date.isoformat() if transaction.transaction_date else None,
            "vendor_id": transaction.vendor_id,
            "amount": float(transaction.amount) if transaction.amount is not None else None,
            "currency": transaction.currency,
            "transaction_type": transaction.transaction_type,
            "risk_score": float(transaction.risk_score) if transaction.risk_score is not None else None,
            "status": transaction.status,
        }

    def _serialize_contract(self, contract: Contract) -> dict[str, Any]:
        return {
            "contract_id": contract.contract_id,
            "vendor_id": contract.vendor_id,
            "contract_value": float(contract.contract_value) if contract.contract_value is not None else None,
            "currency": contract.currency,
            "start_date": contract.start_date.isoformat() if contract.start_date else None,
            "end_date": contract.end_date.isoformat() if contract.end_date else None,
            "contract_type": contract.contract_type,
            "status": contract.status,
            "created_by_employee_id": contract.created_by_employee_id,
        }

    def _serialize_compliance(self, compliance: ComplianceRecord) -> dict[str, Any]:
        return {
            "compliance_id": compliance.compliance_id,
            "vendor_id": compliance.vendor_id,
            "framework": compliance.framework,
            "status": compliance.status,
            "assessment_date": compliance.assessment_date.isoformat() if compliance.assessment_date else None,
            "expiry_date": compliance.expiry_date.isoformat() if compliance.expiry_date else None,
            "assessed_by": compliance.assessed_by,
            "document_ref": compliance.document_ref,
        }

    def _serialize_approval(self, approval: ApprovalWorkflow) -> dict[str, Any]:
        return {
            "approval_id": approval.approval_id,
            "transaction_id": approval.transaction_id,
            "transaction_amount": float(approval.transaction_amount) if approval.transaction_amount is not None else None,
            "approver_employee_id": approval.approver_employee_id,
            "approval_level": approval.approval_level,
            "approval_limit": float(approval.approval_limit) if approval.approval_limit is not None else None,
            "approval_status": approval.approval_status,
            "approval_date": approval.approval_date.isoformat() if approval.approval_date else None,
            "rejection_reason": approval.rejection_reason,
            "delegation_ref": approval.delegation_ref,
        }

    def _serialize_document(self, document: DocumentMetadata) -> dict[str, Any]:
        return {
            "document_id": document.document_id,
            "document_type": document.document_type,
            "document_category": document.document_category,
            "related_vendor_id": document.related_vendor_id,
            "related_employee_id": document.related_employee_id,
            "related_transaction_id": document.related_transaction_id,
            "related_contract_id": document.related_contract_id,
            "related_investigation_id": document.related_investigation_id,
            "creation_date": document.creation_date.isoformat() if document.creation_date else None,
            "file_name": document.file_name,
            "file_path": document.file_path,
            "source_metadata_file": document.source_metadata_file,
        }

    def _serialize_finding(self, finding: AuditFinding) -> dict[str, Any]:
        return {
            "finding_id": finding.finding_id,
            "investigation_id": finding.investigation_id,
            "severity": finding.severity,
            "category": finding.category,
            "description": finding.description,
            "confidence_score": float(finding.confidence_score) if finding.confidence_score is not None else None,
            "status": finding.status,
        }

    def _serialize_investigation(self, investigation: AuditInvestigation) -> dict[str, Any]:
        return {
            "investigation_id": investigation.investigation_id,
            "audit_question": investigation.audit_question,
            "investigation_type": investigation.investigation_type,
            "status": investigation.status,
            "created_date": investigation.created_date.isoformat() if investigation.created_date else None,
            "completed_date": investigation.completed_date.isoformat() if investigation.completed_date else None,
            "scope_period_start": investigation.scope_period_start.isoformat() if investigation.scope_period_start else None,
            "scope_period_end": investigation.scope_period_end.isoformat() if investigation.scope_period_end else None,
            "created_by_employee_id": investigation.created_by_employee_id,
        }

    def _serialize_node(self, node: KnowledgeGraphNode) -> dict[str, Any]:
        return {
            "node_id": node.node_id,
            "entity_type": node.entity_type,
            "entity_id": node.entity_id,
            "display_label": node.display_label,
            "node_kind": node.node_kind,
            "attributes": dict(node.attributes or {}),
            "created_at": node.created_at.isoformat() if node.created_at else None,
            "updated_at": node.updated_at.isoformat() if node.updated_at else None,
        }

    def _serialize_edge(self, edge: KnowledgeGraphEdge) -> dict[str, Any]:
        return {
            "edge_id": edge.edge_id,
            "source_node_id": edge.source_node_id,
            "target_node_id": edge.target_node_id,
            "relationship_type": edge.relationship_type,
            "strength": float(edge.strength) if edge.strength is not None else 1.0,
            "metadata": dict(edge.edge_metadata or {}),
            "created_at": edge.created_at.isoformat() if edge.created_at else None,
            "updated_at": edge.updated_at.isoformat() if edge.updated_at else None,
        }

    def _node_id(self, entity_type: str, entity_id: str) -> str:
        return f"{self._normalize_entity_type(entity_type)}:{entity_id}"

    def _edge_id(self, source_node_id: str, target_node_id: str, relationship_type: str) -> str:
        return f"{source_node_id}->{target_node_id}:{relationship_type}"

    def _normalize_entity_type(self, entity_type: str) -> str:
        normalized = entity_type.strip().lower().replace(" ", "_")
        aliases = {
            "document": "document_metadata",
            "documents": "document_metadata",
            "audit_investigation": "audit_investigation",
            "investigation": "audit_investigation",
            "investigations": "audit_investigation",
            "compliance": "compliance_record",
        }
        return aliases.get(normalized, normalized)

    def _source_type_to_entity_type(self, source_type: str) -> str:
        mapping = {
            "VENDOR_RECORD": "vendor",
            "TRANSACTION_RECORD": "transaction",
            "CONTRACT_RECORD": "contract",
            "COMPLIANCE_RECORD": "compliance_record",
            "APPROVAL_RECORD": "approval_workflow",
            "AUDIT_REPORT": "audit_investigation",
            "POLICY_DOCUMENT": "document_metadata",
        }
        return mapping.get(source_type, "document_metadata")
