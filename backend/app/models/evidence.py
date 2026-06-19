from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


evidence_source_type_enum = ENUM(
    "APPROVAL_RECORD",
    "AUDIT_REPORT",
    "COMPLIANCE_RECORD",
    "CONTRACT_RECORD",
    "DNS_LOG",
    "EXPENSE_CLAIM",
    "HR_RECORD",
    "POLICY_DOCUMENT",
    "TRANSACTION_RECORD",
    "VENDOR_RECORD",
    name="evidence_source_type_enum",
    create_type=False,
)


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    finding_id: Mapped[str] = mapped_column(String(20), ForeignKey("audit_finding.finding_id"), nullable=False)
    source_type: Mapped[str] = mapped_column(evidence_source_type_enum, nullable=False)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    alignment_score: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    citation_reference: Mapped[str] = mapped_column(String(50), nullable=False)
    retrieved_at: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    finding = relationship("AuditFinding", back_populates="evidence_items")
