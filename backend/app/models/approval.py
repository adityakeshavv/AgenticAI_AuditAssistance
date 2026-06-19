from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


workflow_approval_status_enum = ENUM(
    "APPROVED",
    "ESCALATED",
    "REJECTED",
    name="workflow_approval_status_enum",
    create_type=False,
)


class ApprovalWorkflow(Base):
    __tablename__ = "approval_workflow"

    approval_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("transaction_master.transaction_id"),
        nullable=False,
    )
    transaction_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    approver_employee_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("employee_master.employee_id"),
        nullable=False,
    )
    approval_level: Mapped[int] = mapped_column(Integer, nullable=False)
    approval_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    approval_status: Mapped[str] = mapped_column(workflow_approval_status_enum, nullable=False)
    approval_date: Mapped[date] = mapped_column(Date, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    delegation_ref: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    transaction = relationship("TransactionMaster", back_populates="approval_records")
    approver = relationship("EmployeeMaster", foreign_keys=[approver_employee_id])
