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
contract_type_enum = ENUM(
    "FIXED_PRICE",
    "FRAMEWORK",
    "MASTER_SERVICE",
    "PURCHASE_ORDER",
    "RETAINER",
    "SLA",
    "TIME_AND_MATERIAL",
    name="contract_type_enum",
    create_type=False,
)
contract_status_enum = ENUM(
    "ACTIVE",
    "DRAFT",
    "EXPIRED",
    "SUSPENDED",
    "TERMINATED",
    name="contract_status_enum",
    create_type=False,
)


class Contract(Base):
    __tablename__ = "contract"

    contract_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String(20), ForeignKey("vendor.vendor_id"), nullable=False)
    contract_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(currency_code_enum, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_type: Mapped[str] = mapped_column(contract_type_enum, nullable=False)
    status: Mapped[str] = mapped_column(contract_status_enum, nullable=False)
    created_by_employee_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("employee_master.employee_id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    vendor = relationship("Vendor", back_populates="contracts")
    created_by_employee = relationship("EmployeeMaster", foreign_keys=[created_by_employee_id])
