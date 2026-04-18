from pathlib import Path
from datetime import datetime, date, time
import logging

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..deps import require_roles
from ..models import (
    User,
    Role,
    CashSession,
    CashSessionStatus,
    CashMovement,
    CashEntryType,
    CashPaymentStatus,
    CashExpenseCategory,
    PaymentMethod,
)
from ..services.admin_list_service import parse_pagination_params, build_pagination_context
from ..services.cash_service import (
    money,
    get_open_cash_session,
    sync_cash_session_totals,
    parse_cash_movement_datetime,
    register_cash_income,
    build_cash_dashboard_query,
    build_cash_report_query,
)
from ..utils.datetime_utils import utcnow_naive

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
logger = logging.getLogger(__name__)


@router.get("", response_class=HTMLResponse)
def cash_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles([Role.ADMINISTRADOR, Role.ADMINISTRATIVO])),
    q: str = "",
    month: str = "",
    status: str = "",
    payment_method: str = "",
    error: str = "",
    ok: str = "",
):
    open_session = get_open_cash_session(db)

    qp = request.query_params
    pagination = parse_pagination_params(
        qp.get("page"),
        qp.get("page_size"),
        default_page_size=50,
        max_page_size=200,
    )

    try:
        stmt = build_cash_dashboard_query(
            q=q,
            month=month,
            status=status,
            payment_method=payment_method,
        )
    except Exception:
        logger.warning("Filtros inválidos en cash_dashboard | month=%s", month)
        stmt = build_cash_dashboard_query(
            q=q,
            month="",
            status=status,
            payment_method=payment_method,
        )

    count_stmt = stmt.with_only_columns(func.count()).order_by(None)
    total = db.scalar(count_stmt) or 0

    movements = db.scalars(
        stmt.offset(pagination.offset).limit(pagination.page_size)
    ).all()

    accredited_total = sum(
        money(m.amount)
        for m in movements
        if m.status == CashPaymentStatus.ACREDITADO and m.entry_type == CashEntryType.INGRESO
    )
    pending_total = sum(
        money(m.amount)
        for m in movements
        if m.status == CashPaymentStatus.PENDIENTE and m.entry_type == CashEntryType.INGRESO
    )
    expense_total = sum(
        money(m.amount)
        for m in movements
        if m.status == CashPaymentStatus.ACREDITADO and m.entry_type == CashEntryType.EGRESO
    )

    sessions = db.scalars(
        select(CashSession)
        .options(joinedload(CashSession.opened_by), joinedload(CashSession.closed_by))
        .order_by(CashSession.opened_at.desc())
        .limit(10)
    ).all()

    pagination_ctx = build_pagination_context(
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )

    return templates.TemplateResponse(
        request,
        "cash_dashboard.html",
        {
            "me": me,
            "q": q,
            "month": month,
            "status": status,
            "payment_method": payment_method,
            "error": error,
            "ok": ok,
            "movements": movements,
            "open_session": open_session,
            "sessions": sessions,
            "accredited_total": accredited_total,
            "pending_total": pending_total,
            "expense_total": expense_total,
            "payment_methods": list(PaymentMethod),
            "movement_statuses": list(CashPaymentStatus),
            **pagination_ctx,
        },
    )


@router.get("/open", response_class=HTMLResponse)
def cash_open_form(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles([Role.ADMINISTRADOR, Role.ADMINISTRATIVO])),
):
    open_session = get_open_cash_session(db)
    return templates.TemplateResponse(
        request,
        "cash_open.html",
        {
            "me": me,
            "open_session": open_session,
            "error": "",
        },
    )


@router.post("/open")
def cash_open_post(
    request: Request,
    opening_amount: float = Form(0),
    description: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles([Role.ADMINISTRADOR, Role.ADMINISTRATIVO])),
):
    logger.info("Intentando abrir caja | opening_amount=%s | user_id=%s", opening_amount, me.id)

    current_open = get_open_cash_session(db)
    if current_open:
        return RedirectResponse("/admin/caja?error=Ya+hay+una+caja+abierta", status_code=303)

    new_session = CashSession(
        status=CashSessionStatus.ABIERTA,
        opened_at=utcnow_naive(),
        opened_by_user_id=me.id,
        opening_amount=opening_amount or 0,
        total_income=0,
        total_expense=0,
        expected_closing_amount=opening_amount or 0,
        notes=description.strip() or "",
    )

    logger.info("Creando nueva cash session")
    db.add(new_session)
    db.commit()

    return RedirectResponse("/admin/caja?ok=Caja+abierta+correctamente", status_code=303)


@router.get("/expense/new", response_class=HTMLResponse)
def cash_expense_form(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles([Role.ADMINISTRADOR, Role.ADMINISTRATIVO])),
):
    open_session = get_open_cash_session(db)
    return templates.TemplateResponse(
        request,
        "cash_expense_form.html",
        {
            "me": me,
            "open_session": open_session,
            "categories": list(CashExpenseCategory),
            "payment_methods": list(PaymentMethod),
            "error": "",
        },
    )


@router.post("/expense/new")
def cash_expense_post(
    concept: str = Form(...),
    amount: float = Form(...),
    category: str = Form(...),
    payment_method: str = Form(""),
    movement_date: str = Form(""),
    movement_time: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles([Role.ADMINISTRADOR, Role.ADMINISTRATIVO])),
):
    open_session = get_open_cash_session(db)
    if not open_session:
        return RedirectResponse("/admin/caja?error=No+hay+una+caja+abierta", status_code=303)

    dt = utcnow_naive()
    if movement_date:
        try:
            dt = parse_cash_movement_datetime(movement_date, movement_time)
        except Exception:
            logger.warning(
                "Fecha/hora inválida en egreso | movement_date=%s | movement_time=%s",
                movement_date,
                movement_time,
            )

    movement = CashMovement(
        session_id=open_session.id,
        entry_type=CashEntryType.EGRESO,
        category=category,
        concept=concept.strip(),
        notes=description.strip() or "",
        amount=amount,
        payment_method=PaymentMethod(payment_method) if payment_method else None,
        status=CashPaymentStatus.ACREDITADO,
        student_id=None,
        created_by_id=me.id,
        movement_date=dt,
        receipt_note="",
    )
    db.add(movement)
    db.flush()

    sync_cash_session_totals(db, open_session)
    db.commit()

    logger.info(
        "Egreso registrado | session_id=%s | concept=%s | amount=%s | created_by_id=%s",
        open_session.id,
        concept,
        amount,
        me.id,
    )

    return RedirectResponse("/admin/caja?ok=Egreso+registrado+correctamente", status_code=303)


@router.get("/close", response_class=HTMLResponse)
def cash_close_form(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles([Role.ADMINISTRADOR, Role.ADMINISTRATIVO])),
):
    open_session = get_open_cash_session(db)
    if open_session:
        sync_cash_session_totals(db, open_session)
        db.commit()

    movements = []
    if open_session:
        movements = db.scalars(
            select(CashMovement)
            .where(CashMovement.session_id == open_session.id)
            .options(joinedload(CashMovement.student), joinedload(CashMovement.created_by))
            .order_by(CashMovement.movement_date.asc())
        ).all()

    return templates.TemplateResponse(
        request,
        "cash_close.html",
        {
            "me": me,
            "open_session": open_session,
            "movements": movements,
            "error": "",
        },
    )


@router.post("/close")
def cash_close_post(
    real_closing_amount: float = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles([Role.ADMINISTRADOR, Role.ADMINISTRATIVO])),
):
    open_session = get_open_cash_session(db)
    if not open_session:
        return RedirectResponse("/admin/caja?error=No+hay+una+caja+abierta", status_code=303)

    sync_cash_session_totals(db, open_session)

    expected = money(open_session.expected_closing_amount)
    real = money(real_closing_amount)

    open_session.real_closing_amount = real
    open_session.difference_amount = real - expected
    open_session.closed_at = utcnow_naive()
    open_session.closed_by_user_id = me.id
    open_session.status = CashSessionStatus.CERRADA
    open_session.notes = ((open_session.notes or "") + "\n" + notes.strip()).strip()

    db.commit()

    logger.info(
        "Caja cerrada | session_id=%s | expected=%s | real=%s | closed_by=%s",
        open_session.id,
        expected,
        real,
        me.id,
    )

    return RedirectResponse("/admin/caja?ok=Caja+cerrada+correctamente", status_code=303)


@router.get("/report", response_class=HTMLResponse)
def cash_report(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles([Role.ADMINISTRADOR, Role.ADMINISTRATIVO])),
    date_from: str = Query(""),
    date_to: str = Query(""),
    entry_type: str = Query(""),
    payment_method: str = Query(""),
    category: str = Query(""),
    user_q: str = Query(""),
):
    try:
        stmt = build_cash_report_query(
            date_from=date_from,
            date_to=date_to,
            entry_type=entry_type,
            payment_method=payment_method,
            category=category,
            user_q=user_q,
        )
    except Exception:
        logger.warning(
            "Filtros inválidos en cash_report | date_from=%s | date_to=%s",
            date_from,
            date_to,
        )
        stmt = build_cash_report_query(
            date_from="",
            date_to="",
            entry_type=entry_type,
            payment_method=payment_method,
            category=category,
            user_q=user_q,
        )

    movements = db.scalars(stmt).all()

    total_income = sum(
        money(m.amount)
        for m in movements
        if m.entry_type == CashEntryType.INGRESO and m.status == CashPaymentStatus.ACREDITADO
    )
    total_expense = sum(
        money(m.amount)
        for m in movements
        if m.entry_type == CashEntryType.EGRESO and m.status == CashPaymentStatus.ACREDITADO
    )
    net_total = total_income - total_expense

    sessions_stmt = (
        select(CashSession)
        .options(joinedload(CashSession.opened_by), joinedload(CashSession.closed_by))
        .order_by(CashSession.opened_at.desc())
    )

    if date_from:
        try:
            sessions_stmt = sessions_stmt.where(
                CashSession.opened_at >= datetime.combine(date.fromisoformat(date_from), time.min)
            )
        except Exception:
            logger.warning("date_from inválido para sesiones en cash_report: %s", date_from)

    if date_to:
        try:
            sessions_stmt = sessions_stmt.where(
                CashSession.opened_at <= datetime.combine(date.fromisoformat(date_to), time.max)
            )
        except Exception:
            logger.warning("date_to inválido para sesiones en cash_report: %s", date_to)

    sessions = db.scalars(sessions_stmt).all()

    return templates.TemplateResponse(
        request,
        "cash_report.html",
        {
            "me": me,
            "date_from": date_from,
            "date_to": date_to,
            "entry_type_selected": entry_type,
            "payment_method": payment_method,
            "category": category,
            "user_q": user_q,
            "movements": movements,
            "sessions": sessions,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_total": net_total,
            "payment_methods": list(PaymentMethod),
            "expense_categories": list(CashExpenseCategory),
            "entry_types": list(CashEntryType),
        },
    )