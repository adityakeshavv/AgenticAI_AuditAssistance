from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.crud import vendor_crud
from app.models import AuditFinding, Contract, Evidence, TransactionMaster, Vendor
from app.services.transaction_service import serialize_transaction


def serialize_vendor(vendor: Vendor) -> dict[str, Any]:
    return {
        "vendor_id": vendor.vendor_id,
        "vendor_name": vendor.vendor_name,
        "vendor_type": vendor.vendor_type,
        "country": vendor.country,
        "registration_no": vendor.registration_no,
        "risk_rating": vendor.risk_rating,
        "onboarding_date": vendor.onboarding_date.isoformat() if isinstance(vendor.onboarding_date, date) else vendor.onboarding_date,
        "status": vendor.status,
        "created_at": vendor.created_at.isoformat() if isinstance(vendor.created_at, datetime) else vendor.created_at,
        "updated_at": vendor.updated_at.isoformat() if isinstance(vendor.updated_at, datetime) else vendor.updated_at,
    }


def serialize_contract(contract: Contract) -> dict[str, Any]:
    return {
        "contract_id": contract.contract_id,
        "vendor_id": contract.vendor_id,
        "contract_value": float(contract.contract_value) if isinstance(contract.contract_value, Decimal) else contract.contract_value,
        "currency": contract.currency,
        "start_date": contract.start_date.isoformat() if isinstance(contract.start_date, date) else contract.start_date,
        "end_date": contract.end_date.isoformat() if isinstance(contract.end_date, date) else contract.end_date,
        "contract_type": contract.contract_type,
        "status": contract.status,
        "created_by_employee_id": contract.created_by_employee_id,
        "created_at": contract.created_at.isoformat() if isinstance(contract.created_at, datetime) else contract.created_at,
        "updated_at": contract.updated_at.isoformat() if isinstance(contract.updated_at, datetime) else contract.updated_at,
    }


def serialize_finding(finding: AuditFinding) -> dict[str, Any]:
    return {
        "finding_id": finding.finding_id,
        "investigation_id": finding.investigation_id,
        "severity": finding.severity,
        "category": finding.category,
        "description": finding.description,
        "confidence_score": float(finding.confidence_score) if finding.confidence_score is not None else None,
        "status": finding.status,
        "created_at": finding.created_at.isoformat() if isinstance(finding.created_at, date) else finding.created_at,
        "validated_at": finding.validated_at.isoformat() if isinstance(finding.validated_at, date) else finding.validated_at,
        "updated_at": finding.updated_at.isoformat() if isinstance(finding.updated_at, datetime) else finding.updated_at,
    }


def serialize_evidence(evidence: Evidence) -> dict[str, Any]:
    return {
        "evidence_id": evidence.evidence_id,
        "finding_id": evidence.finding_id,
        "source_type": evidence.source_type,
        "source_table": evidence.source_table,
        "source_record_id": evidence.source_record_id,
        "evidence_text": evidence.evidence_text,
        "alignment_score": float(evidence.alignment_score) if evidence.alignment_score is not None else None,
        "citation_reference": evidence.citation_reference,
        "retrieved_at": evidence.retrieved_at.isoformat() if isinstance(evidence.retrieved_at, date) else evidence.retrieved_at,
        "created_at": evidence.created_at.isoformat() if isinstance(evidence.created_at, datetime) else evidence.created_at,
        "updated_at": evidence.updated_at.isoformat() if isinstance(evidence.updated_at, datetime) else evidence.updated_at,
    }


class VendorService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_vendor_profile(self, vendor_id: str) -> dict[str, Any] | None:
        vendor = vendor_crud.get_vendor_by_id(self.db, vendor_id)
        return serialize_vendor(vendor) if vendor else None

    def get_vendor_transactions(self, vendor_id: str) -> list[dict[str, Any]]:
        return [serialize_transaction(transaction) for transaction in vendor_crud.get_vendor_transactions(self.db, vendor_id)]

    def get_vendor_contracts(self, vendor_id: str) -> list[dict[str, Any]]:
        return [serialize_contract(contract) for contract in vendor_crud.get_vendor_contracts(self.db, vendor_id)]

    def get_vendor_evidence(
        self,
        vendor_id: str,
        *,
        transaction_ids: list[str] | None = None,
        contract_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            serialize_evidence(evidence)
            for evidence in vendor_crud.get_vendor_evidence(
                self.db,
                vendor_id,
                transaction_ids=transaction_ids,
                contract_ids=contract_ids,
            )
        ]

    def get_vendor_findings(
        self,
        vendor_id: str,
        *,
        transaction_ids: list[str] | None = None,
        contract_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            serialize_finding(finding)
            for finding in vendor_crud.get_vendor_findings(
                self.db,
                vendor_id,
                transaction_ids=transaction_ids,
                contract_ids=contract_ids,
            )
        ]

    def build_bundle(self, vendor_id: str) -> dict[str, Any]:
        vendor = self.get_vendor_profile(vendor_id)
        transactions = self.get_vendor_transactions(vendor_id)
        contracts = self.get_vendor_contracts(vendor_id)
        transaction_ids = [transaction["transaction_id"] for transaction in transactions if transaction.get("transaction_id")]
        contract_ids = [contract["contract_id"] for contract in contracts if contract.get("contract_id")]
        evidence = self.get_vendor_evidence(vendor_id, transaction_ids=transaction_ids, contract_ids=contract_ids)
        findings = self.get_vendor_findings(vendor_id, transaction_ids=transaction_ids, contract_ids=contract_ids)

        return {
            "vendor": vendor,
            "transactions": transactions,
            "contracts": contracts,
            "evidence": evidence,
            "findings": findings,
        }
