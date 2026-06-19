from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


compliance_framework_enum = ENUM(
    "CIS Controls",
    "CMMC",
    "GDPR",
    "HIPAA",
    "ISO 27001",
    "ISO 9001",
    "NIST CSF",
    "PCI-DSS",
    "SOC 2 Type II",
    "SOX",
    name="compliance_framework_enum",
    create_type=False,
)
compliance_status_enum = ENUM(
    "COMPLIANT",
    "EXPIRED",
    "NON_COMPLIANT",
    "PENDING",
    name="compliance_status_enum",
    create_type=False,
)


class ComplianceRecord(Base):
    __tablename__ = "compliance_record"

    compliance_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String(20), ForeignKey("vendor.vendor_id"), nullable=False)
    framework: Mapped[str] = mapped_column(compliance_framework_enum, nullable=False)
    status: Mapped[str] = mapped_column(compliance_status_enum, nullable=False)
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    findings_summary: Mapped[str] = mapped_column(Text, nullable=False)
    document_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    vendor = relationship("Vendor", back_populates="compliance_records")
