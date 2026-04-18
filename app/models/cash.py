from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..db import Base
from .enums import (
    CashEntryType,
    CashExpenseCategory,
    CashPaymentStatus,
    CashSessionStatus,
    PaymentMethod,
)


class CashSession(Base):
    __tablename__ = "cash_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    status: Mapped[CashSessionStatus] = mapped_column(
        SAEnum(CashSessionStatus, name="cash_session_status"),
        default=CashSessionStatus.ABIERTA,
        index=True,
    )

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opened_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    closed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    opening_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_income: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_expense: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    expected_closing_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    real_closing_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    difference_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    notes: Mapped[str] = mapped_column(String(1000), default="")

    opened_by: Mapped["User"] = relationship(
        back_populates="cash_sessions_opened",
        foreign_keys=[opened_by_user_id],
    )
    closed_by: Mapped["User | None"] = relationship(
        back_populates="cash_sessions_closed",
        foreign_keys=[closed_by_user_id],
    )

    movements: Mapped[list["CashMovement"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class CashMovement(Base):
    __tablename__ = "cash_movements"

    id: Mapped[int] = mapped_column(primary_key=True)

    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("cash_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    entry_type: Mapped[CashEntryType] = mapped_column(
        SAEnum(CashEntryType, name="cash_entry_type"),
        default=CashEntryType.INGRESO,
        index=True,
    )

    category: Mapped[str] = mapped_column(String(60), default=CashExpenseCategory.MEMBRESIA.value, index=True)

    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    membership_assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("membership_assignments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    concept: Mapped[str] = mapped_column(String(150), default="Pago membresía")
    notes: Mapped[str] = mapped_column(String(500), default="")

    period_yyyymm: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)

    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method"),
        nullable=True,
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    status: Mapped[CashPaymentStatus] = mapped_column(
        SAEnum(CashPaymentStatus, name="cash_payment_status"),
        default=CashPaymentStatus.ACREDITADO,
        index=True,
    )

    receipt_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt_note: Mapped[str] = mapped_column(String(255), default="")
    movement_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["CashSession | None"] = relationship(back_populates="movements")
    student: Mapped["User | None"] = relationship(foreign_keys=[student_id])
    created_by: Mapped["User | None"] = relationship(
        back_populates="cash_movements_created",
        foreign_keys=[created_by_id],
    )
    membership_assignment: Mapped["MembershipAssignment | None"] = relationship(foreign_keys=[membership_assignment_id])    