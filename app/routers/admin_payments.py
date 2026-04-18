from pathlib import Path
from datetime import date
import os
import uuid
import logging

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..deps import require_roles
from ..models import (
    User,
    MembershipAssignment,
    MembershipPrice,
    CashMovement,
    CashEntryType,
    CashPaymentStatus,
    CashSession,
    CashSessionStatus,
    PaymentMethod,
)
from ..services.admin_list_service import parse_pagination_params, build_pagination_context
from ..services.payment_service import summarize_payment_rows

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
logger = logging.getLogger(__name__)

ALLOWED = ["ADMINISTRADOR", "ADMINISTRATIVO"]

UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "receipts"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _save_receipt(receipt_file: UploadFile | None) -> str | None:
    if not receipt_file or not receipt_file.filename:
        return None

    ext = os.path.splitext(receipt_file.filename)[1].lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    full_path = UPLOAD_DIR / filename

    with open(full_path, "wb") as f:
        f.write(receipt_file.file.read())

    return f"/static/uploads/receipts/{filename}"


def _get_open_cash_session(db: Session) -> CashSession | None:
    return db.scalar(
        select(CashSession)
        .where(CashSession.status == CashSessionStatus.ABIERTA)
        .order_by(CashSession.opened_at.desc())
    )


def _sync_cash_session_totals(db: Session, session_id: int | None) -> None:
    if not session_id:
        return

    cash_session = db.get(CashSession, session_id)
    if not cash_session:
        return

    total_income = db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.session_id == session_id,
            CashMovement.entry_type == CashEntryType.INGRESO,
            CashMovement.status == CashPaymentStatus.ACREDITADO,
        )
    ) or 0

    total_expense = db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.session_id == session_id,
            CashMovement.entry_type == CashEntryType.EGRESO,
            CashMovement.status == CashPaymentStatus.ACREDITADO,
        )
    ) or 0

    cash_session.total_income = float(total_income or 0)
    cash_session.total_expense = float(total_expense or 0)
    cash_session.expected_closing_amount = (
        float(cash_session.opening_amount or 0)
        + float(total_income or 0)
        - float(total_expense or 0)
    )


def _build_cash_list_query(
    *,
    q: str,
    period: str,
    status: str,
    payment_method: str,
):
    stmt = (
        select(CashMovement)
        .order_by(CashMovement.paid_at.desc(), CashMovement.id.desc())
        .options(
            joinedload(CashMovement.student),
            joinedload(CashMovement.created_by),
            joinedload(CashMovement.membership_assignment).joinedload(MembershipAssignment.membership),
        )
    )

    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.join(User, CashMovement.student_id == User.id, isouter=True).where(
            (User.email.ilike(like))
            | (User.first_name.ilike(like))
            | (User.last_name.ilike(like))
            | (User.dni.ilike(like))
            | (CashMovement.concept.ilike(like))
            | (CashMovement.receipt_note.ilike(like))
        )

    if period.strip():
        stmt = stmt.where(CashMovement.period_yyyymm == period.strip())

    if status.strip():
        stmt = stmt.where(CashMovement.status == CashPaymentStatus(status))

    if payment_method.strip():
        stmt = stmt.where(CashMovement.payment_method == PaymentMethod(payment_method))

    return stmt


def _load_student_assignments_with_prices(db: Session, student_id: int):
    assignments = db.scalars(
        select(MembershipAssignment)
        .where(MembershipAssignment.student_id == student_id)
        .order_by(MembershipAssignment.id.desc())
        .options(joinedload(MembershipAssignment.membership))
    ).all()

    assignment_prices = {}
    for a in assignments:
        prices_rows = db.scalars(
            select(MembershipPrice).where(MembershipPrice.membership_id == a.membership_id)
        ).all()
        assignment_prices[a.id] = {
            p.payment_method.value: float(p.amount)
            for p in prices_rows
        }

    return assignments, assignment_prices


def _payment_form_context(
    *,
    me,
    student,
    assignments,
    assignment_prices,
    error: str | None,
):
    return {
        "me": me,
        "student": student,
        "assignments": assignments,
        "assignment_prices": assignment_prices,
        "error": error,
        "today_period": date.today().strftime("%Y-%m"),
        "payment_methods": [pm.value for pm in PaymentMethod if pm.value != "LISTA"],
    }


@router.get("/admin/alumnos/{student_id}/payments", response_class=HTMLResponse)
def alumno_payments(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    student = db.get(User, student_id)
    if not student or student.role.value != "ALUMNO":
        return RedirectResponse(url="/admin/users", status_code=302)

    rows = db.scalars(
        select(CashMovement)
        .where(CashMovement.student_id == student.id)
        .order_by(CashMovement.paid_at.desc(), CashMovement.id.desc())
        .options(
            joinedload(CashMovement.created_by),
            joinedload(CashMovement.membership_assignment).joinedload(MembershipAssignment.membership),
        )
    ).all()

    total_acreditado = sum(
        float(r.amount or 0)
        for r in rows
        if r.status == CashPaymentStatus.ACREDITADO and r.entry_type == CashEntryType.INGRESO
    )

    return templates.TemplateResponse(
        request,
        "alumno_payments.html",
        {
            "me": me,
            "student": student,
            "rows": rows,
            "total_acreditado": total_acreditado,
        },
    )


@router.get("/admin/alumnos/{student_id}/payments/new", response_class=HTMLResponse)
def payment_new_page(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    student = db.get(User, student_id)
    if not student or student.role.value != "ALUMNO":
        return RedirectResponse(url="/admin/users", status_code=302)

    assignments, assignment_prices = _load_student_assignments_with_prices(db, student.id)

    return templates.TemplateResponse(
        request,
        "payment_form.html",
        _payment_form_context(
            me=me,
            student=student,
            assignments=assignments,
            assignment_prices=assignment_prices,
            error=None,
        ),
    )


@router.post("/admin/alumnos/{student_id}/payments/new", response_class=HTMLResponse)
def payment_new_do(
    request: Request,
    student_id: int,
    concept: str = Form("Pago membresía"),
    description: str = Form(""),
    amount: str = Form(""),
    payment_method: str = Form(...),
    membership_assignment_id: str = Form(""),
    period_yyyymm: str = Form(""),
    receipt_note: str = Form(""),
    receipt_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    student = db.get(User, student_id)
    if not student or student.role.value != "ALUMNO":
        return RedirectResponse(url="/admin/users", status_code=302)

    assignments, assignment_prices = _load_student_assignments_with_prices(db, student.id)

    try:
        pm = PaymentMethod(payment_method)
    except Exception:
        return templates.TemplateResponse(
            request,
            "payment_form.html",
            _payment_form_context(
                me=me,
                student=student,
                assignments=assignments,
                assignment_prices=assignment_prices,
                error="Método de pago inválido.",
            ),
            status_code=400,
        )

    assignment = None
    if membership_assignment_id.strip():
        assignment = db.get(MembershipAssignment, int(membership_assignment_id))
        if assignment and assignment.student_id != student.id:
            assignment = None

    if not assignment:
        return templates.TemplateResponse(
            request,
            "payment_form.html",
            _payment_form_context(
                me=me,
                student=student,
                assignments=assignments,
                assignment_prices=assignment_prices,
                error="Debés seleccionar una asignación de membresía válida.",
            ),
            status_code=400,
        )

    prices_rows = db.scalars(
        select(MembershipPrice).where(MembershipPrice.membership_id == assignment.membership_id)
    ).all()
    prices_map = {p.payment_method.value: float(p.amount) for p in prices_rows}

    amount_val = prices_map.get(pm.value)
    if amount_val is None:
        return templates.TemplateResponse(
            request,
            "payment_form.html",
            _payment_form_context(
                me=me,
                student=student,
                assignments=assignments,
                assignment_prices=assignment_prices,
                error=f"No hay un precio configurado para el método {pm.value}.",
            ),
            status_code=400,
        )

    receipt_path = _save_receipt(receipt_file)

    status = CashPaymentStatus.ACREDITADO
    if pm == PaymentMethod.TRANSFERENCIA:
        status = CashPaymentStatus.PENDIENTE

    open_session = _get_open_cash_session(db)

    row = CashMovement(
        session_id=open_session.id if open_session else None,
        entry_type=CashEntryType.INGRESO,
        category="MEMBRESIA",
        student_id=student.id,
        membership_assignment_id=assignment.id,
        created_by_id=me.id,
        concept=(concept or "").strip() or "Pago membresía",
        period_yyyymm=(period_yyyymm or "").strip() or None,
        payment_method=pm,
        amount=amount_val,
        status=status,
        receipt_image_path=receipt_path,
        receipt_note=((receipt_note or "").strip() or (description or "").strip()),
    )
    db.add(row)
    db.flush()

    if open_session and status == CashPaymentStatus.ACREDITADO:
        _sync_cash_session_totals(db, open_session.id)

    db.commit()

    return RedirectResponse(url=f"/admin/alumnos/{student.id}/payments", status_code=302)


@router.get("/admin/caja", response_class=HTMLResponse)
def cash_list(
    request: Request,
    q: str = "",
    period: str = "",
    status: str = "",
    payment_method: str = "",
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    qp = request.query_params
    pagination = parse_pagination_params(
        qp.get("page"),
        qp.get("page_size"),
        default_page_size=50,
        max_page_size=200,
    )

    try:
        stmt = _build_cash_list_query(
            q=q,
            period=period,
            status=status,
            payment_method=payment_method,
        )
    except Exception:
        logger.warning(
            "Filtros inválidos en cash_list | period=%s | status=%s | payment_method=%s",
            period,
            status,
            payment_method,
        )
        stmt = _build_cash_list_query(
            q=q,
            period="",
            status="",
            payment_method="",
        )

    count_stmt = stmt.with_only_columns(func.count()).order_by(None)
    total = db.scalar(count_stmt) or 0

    rows = db.scalars(
        stmt.offset(pagination.offset).limit(pagination.page_size)
    ).all()

    summary = summarize_payment_rows(rows)
    total_ingresos = summary["accredited_total"]
    total_pendiente = summary["pending_total"]

    total_egresos = sum(
        float(r.amount or 0)
        for r in rows
        if r.status == CashPaymentStatus.ACREDITADO and r.entry_type == CashEntryType.EGRESO
    )

    saldo_neto = total_ingresos - total_egresos

    pagination_ctx = build_pagination_context(
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )

    return templates.TemplateResponse(
        request,
        "cash_list.html",
        {
            "me": me,
            "rows": rows,
            "q": q,
            "period": period,
            "status": status,
            "payment_method": payment_method,
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "total_pendiente": total_pendiente,
            "saldo_neto": saldo_neto,
            "statuses": [s.value for s in CashPaymentStatus],
            "payment_methods": [pm.value for pm in PaymentMethod if pm.value != "LISTA"],
            **pagination_ctx,
        },
    )


@router.post("/admin/payments/{payment_id}/confirm")
def payment_confirm(
    payment_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = db.get(CashMovement, payment_id)
    if not row:
        logger.warning("admin_payments_confirm_not_found payment_id=%s user_id=%s", payment_id, me.id)
        return RedirectResponse(url="/admin/caja", status_code=302)

    if row.status == CashPaymentStatus.ACREDITADO:
        logger.info("admin_payments_confirm_already_accredited payment_id=%s user_id=%s", row.id, me.id)
    else:
        row.status = CashPaymentStatus.ACREDITADO
        if row.session_id:
            _sync_cash_session_totals(db, row.session_id)
        db.commit()

        logger.info(
            "admin_payments_confirm payment_id=%s session_id=%s student_id=%s user_id=%s",
            row.id,
            row.session_id,
            row.student_id,
            me.id,
        )

    if row.student_id:
        return RedirectResponse(url=f"/admin/alumnos/{row.student_id}/payments", status_code=302)
    return RedirectResponse(url="/admin/caja", status_code=302)


@router.post("/admin/payments/{payment_id}/cancel")
def payment_cancel(
    payment_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = db.get(CashMovement, payment_id)
    if not row:
        logger.warning("admin_payments_cancel_not_found payment_id=%s user_id=%s", payment_id, me.id)
        return RedirectResponse(url="/admin/caja", status_code=302)

    if row.status == CashPaymentStatus.ANULADO:
        logger.info("admin_payments_cancel_already_cancelled payment_id=%s user_id=%s", row.id, me.id)
    else:
        row.status = CashPaymentStatus.ANULADO
        if row.session_id:
            _sync_cash_session_totals(db, row.session_id)
        db.commit()

        logger.info(
            "admin_payments_cancel payment_id=%s session_id=%s student_id=%s user_id=%s",
            row.id,
            row.session_id,
            row.student_id,
            me.id,
        )

    if row.student_id:
        return RedirectResponse(url=f"/admin/alumnos/{row.student_id}/payments", status_code=302)
    return RedirectResponse(url="/admin/caja", status_code=302)