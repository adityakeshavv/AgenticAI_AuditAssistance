from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


investigation_type_enum = ENUM(
    "APPROVAL_LIMIT_REVIEW",
    "COMPLIANCE_REVIEW",
    "CONTRACT_AUDIT",
    "EXPENSE_AUDIT",
    "FINANCIAL_INVESTIGATION",
    "FRAUD_INVESTIGATION",
    "POLICY_BREACH_REVIEW",
    "VENDOR_RISK_ASSESSMENT",
    name="investigation_type_enum",
    create_type=False,
)
investigation_status_enum = ENUM(
    "COMPLETED",
    "IN_PROGRESS",
    "ON_HOLD",
    "OPEN",
    name="investigation_status_enum",
    create_type=False,
)


class AuditInvestigation(Base):
    __tablename__ = "audit_investigation"

    investigation_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    audit_question: Mapped[str] = mapped_column(Text, nullable=False)
    investigation_type: Mapped[str] = mapped_column(investigation_type_enum, nullable=False)
    status: Mapped[str] = mapped_column(investigation_status_enum, nullable=False)
    created_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_date: Mapped[date | None] = mapped_column(Date)
    scope_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    scope_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    created_by_employee_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("employee_master.employee_id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_by_employee = relationship("EmployeeMaster", foreign_keys=[created_by_employee_id])
    findings = relationship("AuditFinding", back_populates="investigation")
