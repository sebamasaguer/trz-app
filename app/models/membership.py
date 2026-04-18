from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..db import Base
from .enums import MembershipKind, PaymentMethod, ServiceKind


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(180))
    kind: Mapped[MembershipKind] = mapped_column(SAEnum(MembershipKind, name="membership_kind"))

    funcional_classes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    musculacion_classes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    funcional_unlimited: Mapped[bool] = mapped_column(Boolean, default=False)
    musculacion_unlimited: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prices: Mapped[list["MembershipPrice"]] = relationship(
        back_populates="membership",
        cascade="all, delete-orphan",
    )


class MembershipPrice(Base):
    __tablename__ = "membership_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id", ondelete="CASCADE"), index=True)

    payment_method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, name="payment_method"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))

    membership: Mapped["Membership"] = relationship(back_populates="prices")


class MembershipAssignment(Base):
    __tablename__ = "membership_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)

    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method"),
        nullable=True,
    )
    amount_snapshot: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    period_yyyymm: Mapped[str | None] = mapped_column(String(7), nullable=True)

    membership: Mapped["Membership"] = relationship()
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    assigned_by_user: Mapped["User"] = relationship(foreign_keys=[assigned_by])


class MembershipUsage(Base):
    __tablename__ = "membership_usages"

    id: Mapped[int] = mapped_column(primary_key=True)

    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("membership_assignments.id", ondelete="CASCADE"),
        index=True,
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    service: Mapped[ServiceKind] = mapped_column(SAEnum(ServiceKind, name="service_kind"))

    used_at: Mapped[date] = mapped_column(Date, nullable=False)
    used_at_time: Mapped[time | None] = mapped_column(nullable=True)
    period_yyyymm: Mapped[str] = mapped_column(String(7), index=True)

    notes: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assignment: Mapped["MembershipAssignment"] = relationship()
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    created_by_user: Mapped["User"] = relationship(foreign_keys=[created_by])