from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.utils.datetime_utils import utcnow_naive
from ..models import (
    CashEntryType,
    CashExpenseCategory,
    CashMovement,
    CashPaymentStatus,
    CashSession,
    CashSessionStatus,
    PaymentMethod,
    User,
)


def money(v) -> float:
    return float(v or 0)


def get_open_cash_session(db: Session) -> CashSession | None:
    return db.scalar(
        select(CashSession)
        .where(CashSession.status == CashSessionStatus.ABIERTA)
        .options(
            joinedload(CashSession.opened_by),
            joinedload(CashSession.movements),
        )
        .order_by(CashSession.opened_at.desc())
    )


def sync_cash_session_totals(db: Session, cash_session: CashSession) -> None:
    income = db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.session_id == cash_session.id,
            CashMovement.entry_type == CashEntryType.INGRESO,
            CashMovement.status == CashPaymentStatus.ACREDITADO,
        )
    ) or 0

    expense = db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.session_id == cash_session.id,
            CashMovement.entry_type == CashEntryType.EGRESO,
            CashMovement.status == CashPaymentStatus.ACREDITADO,
        )
    ) or 0

    cash_session.total_income = income
    cash_session.total_expense = expense
    cash_session.expected_closing_amount = (
        money(cash_session.opening_amount) + money(income) - money(expense)
    )


def parse_cash_movement_datetime(
    movement_date: str,
    movement_time: str,
) -> datetime:
    if not movement_date:
        return utcnow_naive()

    d = date.fromisoformat(movement_date)
    t = time.fromisoformat(movement_time) if movement_time else time(0, 0)
    return datetime.combine(d, t)


def register_cash_income(
    db: Session,
    *,
    concept: str,
    amount: float,
    payment_method: PaymentMethod | None,
    created_by_id: int,
    student_id: int | None = None,
    category: str = "MEMBRESIA",
    movement_date: datetime | None = None,
    description: str | None = None,
    status: CashPaymentStatus = CashPaymentStatus.ACREDITADO,
) -> CashMovement:
    cash_session = get_open_cash_session(db)
    if not cash_session:
        raise ValueError("No hay caja abierta.")

    movement = CashMovement(
        session_id=cash_session.id,
        entry_type=CashEntryType.INGRESO,
        category=category,
        concept=concept.strip(),
        amount=amount,
        payment_method=payment_method,
        student_id=student_id,
        created_by_id=created_by_id,
        movement_date=movement_date or utcnow_naive(),
        notes=(description or "").strip(),
        status=status,
    )
    db.add(movement)
    db.flush()

    sync_cash_session_totals(db, cash_session)
    db.flush()

    return movement


def build_cash_dashboard_query(
    *,
    q: str,
    month: str,
    status: str,
    payment_method: str,
):
    stmt = (
        select(CashMovement)
        .options(
            joinedload(CashMovement.student),
            joinedload(CashMovement.created_by),
            joinedload(CashMovement.session),
        )
        .order_by(CashMovement.movement_date.desc())
    )

    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.join(User, CashMovement.student_id == User.id, isouter=True).where(
            or_(
                CashMovement.concept.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
                User.dni.ilike(like),
            )
        )

    if month:
        y, m = month.split("-")
        y = int(y)
        m = int(m)
        start_dt = datetime(y, m, 1)
        end_dt = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
        stmt = stmt.where(
            CashMovement.movement_date >= start_dt,
            CashMovement.movement_date < end_dt,
        )

    if status:
        stmt = stmt.where(CashMovement.status == status)

    if payment_method:
        stmt = stmt.where(CashMovement.payment_method == payment_method)

    return stmt


def build_cash_report_query(
    *,
    date_from: str,
    date_to: str,
    entry_type: str,
    payment_method: str,
    category: str,
    user_q: str,
):
    stmt = (
        select(CashMovement)
        .options(
            joinedload(CashMovement.student),
            joinedload(CashMovement.created_by),
            joinedload(CashMovement.session),
        )
        .order_by(CashMovement.movement_date.desc())
    )

    if date_from:
        stmt = stmt.where(
            CashMovement.movement_date >= datetime.combine(date.fromisoformat(date_from), time.min)
        )

    if date_to:
        stmt = stmt.where(
            CashMovement.movement_date <= datetime.combine(date.fromisoformat(date_to), time.max)
        )

    if entry_type:
        stmt = stmt.where(CashMovement.entry_type == entry_type)

    if payment_method:
        stmt = stmt.where(CashMovement.payment_method == payment_method)

    if category:
        stmt = stmt.where(CashMovement.category == category)

    if user_q:
        like = f"%{user_q.strip()}%"
        stmt = stmt.join(User, CashMovement.created_by_id == User.id).where(
            or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
            )
        )

    return stmt