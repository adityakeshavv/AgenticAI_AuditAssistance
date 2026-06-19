from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


expense_category_enum = ENUM(
    "Accommodation",
    "Consulting",
    "Entertainment",
    "Equipment",
    "Marketing",
    "Meals",
    "Office Supplies",
    "Software",
    "Training",
    "Travel",
    name="expense_category_enum",
    create_type=False,
)
expense_approval_status_enum = ENUM(
    "APPROVED",
    "FLAGGED",
    "PENDING",
    "REJECTED",
    name="expense_approval_status_enum",
    create_type=False,
)


class ExpenseClaim(Base):
    __tablename__ = "expense_claim"

    claim_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(30), ForeignKey("employee_master.employee_id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expense_category: Mapped[str] = mapped_column(expense_category_enum, nullable=False)
    claim_date: Mapped[date] = mapped_column(Date, nullable=False)
    submission_date: Mapped[date] = mapped_column(Date, nullable=False)
    receipt_attached: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(20), nullable=False)
    approval_status: Mapped[str] = mapped_column(expense_approval_status_enum, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(30), ForeignKey("employee_master.employee_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    employee = relationship("EmployeeMaster", foreign_keys=[employee_id])
    approver = relationship("EmployeeMaster", foreign_keys=[approved_by])
