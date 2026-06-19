from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


currency_code_enum = ENUM(
    "AUD",
    "CAD",
    "EUR",
    "GBP",
    "INR",
    "SGD",
    "USD",
    name="currency_code_enum",
    create_type=False,
)
transaction_type_enum = ENUM(
    "ADVANCE",
    "INVOICE",
    "PAYMENT",
    "PURCHASE",
    "REFUND",
    "REIMBURSEMENT",
    "SETTLEMENT",
    "TRANSFER",
    name="transaction_type_enum",
    create_type=False,
)
transaction_status_enum = ENUM(
    "COMPLETED",
    "FLAGGED",
    "PENDING",
    "REVERSED",
    name="transaction_status_enum",
    create_type=False,
)


class TransactionMaster(Base):
    __tablename__ = "transaction_master"

    transaction_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    vendor_id: Mapped[str] = mapped_column(String(20), ForeignKey("vendor.vendor_id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(currency_code_enum, nullable=False)
    transaction_type: Mapped[str] = mapped_column(transaction_type_enum, nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    status: Mapped[str] = mapped_column(transaction_status_enum, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    vendor = relationship("Vendor", back_populates="transactions")
    approval_records = relationship("ApprovalWorkflow", back_populates="transaction")
