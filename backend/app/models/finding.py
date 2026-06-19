from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


finding_severity_enum = ENUM(
    "CRITICAL",
    "HIGH",
    "LOW",
    "MEDIUM",
    name="finding_severity_enum",
    create_type=False,
)
finding_category_enum = ENUM(
    "APPROVAL_LIMIT",
    "EXPIRED_COMPLIANCE",
    "FRAUD_PATTERN",
    "MISSING_RECEIPT",
    "POLICY_BREACH",
    "VENDOR_RISK",
    name="finding_category_enum",
    create_type=False,
)
finding_status_enum = ENUM(
    "ESCALATED",
    "FALSE_POSITIVE",
    "OPEN",
    "RESOLVED",
    "VALIDATED",
    name="finding_status_enum",
    create_type=False,
)


class AuditFinding(Base):
    __tablename__ = "audit_finding"

    finding_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("audit_investigation.investigation_id"),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(finding_severity_enum, nullable=False)
    category: Mapped[str] = mapped_column(finding_category_enum, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    status: Mapped[str] = mapped_column(finding_status_enum, nullable=False)
    created_at: Mapped[date] = mapped_column(Date, nullable=False)
    validated_at: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    investigation = relationship("AuditInvestigation", back_populates="findings")
    evidence_items = relationship("Evidence", back_populates="finding")
