from __future__ import annotations

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from app.models import AuditFinding, Contract, Evidence, TransactionMaster, Vendor


def get_vendor_by_id(db: Session, vendor_id: str) -> Vendor | None:
    return db.get(Vendor, vendor_id)


def get_vendor_transactions(db: Session, vendor_id: str) -> list[TransactionMaster]:
    stmt = (
        select(TransactionMaster)
        .where(TransactionMaster.vendor_id == vendor_id)
        .order_by(desc(TransactionMaster.transaction_date), desc(TransactionMaster.risk_score), desc(TransactionMaster.amount))
    )
    return list(db.scalars(stmt).all())


def get_vendor_contracts(db: Session, vendor_id: str) -> list[Contract]:
    stmt = (
        select(Contract)
        .where(Contract.vendor_id == vendor_id)
        .order_by(desc(Contract.end_date), desc(Contract.contract_value))
    )
    return list(db.scalars(stmt).all())


def get_vendor_evidence(
    db: Session,
    vendor_id: str,
    *,
    transaction_ids: list[str] | None = None,
    contract_ids: list[str] | None = None,
) -> list[Evidence]:
    conditions = [and_(Evidence.source_type == "VENDOR_RECORD", Evidence.source_record_id == vendor_id)]
    if transaction_ids:
        conditions.append(and_(Evidence.source_type == "TRANSACTION_RECORD", Evidence.source_record_id.in_(transaction_ids)))
    if contract_ids:
        conditions.append(and_(Evidence.source_type == "CONTRACT_RECORD", Evidence.source_record_id.in_(contract_ids)))

    stmt = select(Evidence).where(or_(*conditions)).order_by(desc(Evidence.created_at), desc(Evidence.updated_at))
    return list(db.scalars(stmt).all())


def get_vendor_findings(
    db: Session,
    vendor_id: str,
    *,
    transaction_ids: list[str] | None = None,
    contract_ids: list[str] | None = None,
) -> list[AuditFinding]:
    conditions = [and_(Evidence.source_type == "VENDOR_RECORD", Evidence.source_record_id == vendor_id)]
    if transaction_ids:
        conditions.append(and_(Evidence.source_type == "TRANSACTION_RECORD", Evidence.source_record_id.in_(transaction_ids)))
    if contract_ids:
        conditions.append(and_(Evidence.source_type == "CONTRACT_RECORD", Evidence.source_record_id.in_(contract_ids)))

    stmt = (
        select(AuditFinding)
        .join(Evidence, AuditFinding.finding_id == Evidence.finding_id)
        .where(or_(*conditions))
        .order_by(desc(AuditFinding.created_at), desc(AuditFinding.updated_at))
    )
    return list(db.scalars(stmt).unique().all())
