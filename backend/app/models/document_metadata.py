from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    document_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    document_category: Mapped[str] = mapped_column(String(100), nullable=False)
    related_vendor_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    related_employee_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    related_transaction_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_contract_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    related_investigation_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    creation_date: Mapped[date] = mapped_column(Date, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source_metadata_file: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
