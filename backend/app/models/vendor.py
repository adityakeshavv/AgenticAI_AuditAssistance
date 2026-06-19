from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


vendor_type_enum = ENUM(
    "CONSULTANT",
    "CONTRACTOR",
    "DISTRIBUTOR",
    "LOGISTICS",
    "MANUFACTURER",
    "SERVICE_PROVIDER",
    "SUPPLIER",
    name="vendor_type_enum",
    create_type=False,
)
vendor_risk_rating_enum = ENUM(
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
    name="vendor_risk_rating_enum",
    create_type=False,
)
vendor_status_enum = ENUM(
    "ACTIVE",
    "INACTIVE",
    "BLACKLISTED",
    name="vendor_status_enum",
    create_type=False,
)


class Vendor(Base):
    __tablename__ = "vendor"

    vendor_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    vendor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    vendor_type: Mapped[str] = mapped_column(vendor_type_enum, nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    registration_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    risk_rating: Mapped[str] = mapped_column(vendor_risk_rating_enum, nullable=False)
    onboarding_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(vendor_status_enum, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    contracts = relationship("Contract", back_populates="vendor")
    compliance_records = relationship("ComplianceRecord", back_populates="vendor")
    transactions = relationship("TransactionMaster", back_populates="vendor")
