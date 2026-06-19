from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


employee_status_enum = ENUM(
    "ACTIVE",
    name="employee_status_enum",
    create_type=False,
)


class EmployeeMaster(Base):
    __tablename__ = "employee_master"

    employee_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    employee_name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("department_master.department_id", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    manager_id: Mapped[str | None] = mapped_column(
        String(30),
        ForeignKey("employee_master.employee_id", deferrable=True, initially="DEFERRED"),
    )
    designation: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    joining_date: Mapped[date] = mapped_column(Date, nullable=False)
    employment_status: Mapped[str] = mapped_column(employee_status_enum, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    department = relationship(
        "DepartmentMaster",
        back_populates="employees",
        foreign_keys=[department_id],
    )
    manager = relationship(
        "EmployeeMaster",
        remote_side=[employee_id],
        foreign_keys=[manager_id],
    )
