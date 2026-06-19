from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DepartmentMaster(Base):
    __tablename__ = "department_master"

    department_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    department_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cost_center: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    head_employee_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("employee_master.employee_id", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    employees = relationship(
        "EmployeeMaster",
        back_populates="department",
        foreign_keys="EmployeeMaster.department_id",
    )
    head_employee = relationship(
        "EmployeeMaster",
        foreign_keys=[head_employee_id],
    )
