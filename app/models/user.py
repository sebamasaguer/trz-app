from datetime import date, datetime
from app.utils.datetime_utils import utcnow_naive

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .enums import Role


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "ix_users_role_is_active_last_name_first_name_id",
            "role",
            "is_active",
            "last_name",
            "first_name",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    first_name: Mapped[str] = mapped_column(String(120), default="")
    last_name: Mapped[str] = mapped_column(String(120), default="")
    dni: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    emergency_contact_name: Mapped[str] = mapped_column(String(120), default="")
    emergency_contact_phone: Mapped[str] = mapped_column(String(30), default="")

    full_name: Mapped[str] = mapped_column(String(255), default="")

    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SAEnum(Role, name="role_enum"), default=Role.ALUMNO)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    cash_sessions_opened: Mapped[list["CashSession"]] = relationship(
        back_populates="opened_by",
        foreign_keys="CashSession.opened_by_user_id",
    )
    cash_sessions_closed: Mapped[list["CashSession"]] = relationship(
        back_populates="closed_by",
        foreign_keys="CashSession.closed_by_user_id",
    )
    cash_movements_created: Mapped[list["CashMovement"]] = relationship(
        back_populates="created_by",
        foreign_keys="CashMovement.created_by_id",
    )

    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        today = date.today()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years