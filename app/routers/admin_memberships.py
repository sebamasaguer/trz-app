from pathlib import Path
from datetime import date

from fastapi import APIRouter, Request, Depends, Form, Path as FPath
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..db import get_db
from ..deps import require_roles
from ..models import (
    User,
    Role,
    Membership,
    MembershipKind,
    MembershipPrice,
    PaymentMethod,
    ServiceKind,
)
from ..security import qr_make_payload
from ..services.admin_list_service import parse_pagination_params, build_pagination_context
from ..services.membership_service import (
    assignment_active_duplicate_exists,
    assign_page_context,
    build_assignment_duplicate_message,
    build_assignment_success_message,
    build_consume_success_message,
    build_duplicate_usage_message,
    build_membership_assignment,
    build_membership_payload,
    build_missing_assignment_message,
    consume_page_context,
    current_membership_period,
    deactivate_active_assignments_for_period,
    get_active_assignment_for_period,
    is_membership_assignment_duplicate_integrity_error,
    is_membership_usage_duplicate_integrity_error,
    load_active_memberships,
    load_active_students,
    load_prices_for_membership_ids,
    membership_form_context,
    membership_kind_values,
    membership_list_context,
    normalize_period_input,
    normalize_qr_service,
    parse_assignment_start_date,
    parse_optional_payment_method,
    parse_usage_date,
    parse_usage_time,
    price_inputs_to_method_map,
    price_map,
    qr_page_context,
    register_membership_usage,
    report_page_context,
    resolve_assignment_amount_snapshot,
    resolve_assignment_period,
    summarize_membership_report,
    sync_membership_prices,
    usage_duplicate_exists,
    validate_assignment_entities,
    validate_membership_usage_capacity,
    validate_usage_date_for_current_period,
    validate_usage_time_window,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ALLOWED = ["ADMINISTRADOR", "ADMINISTRATIVO"]


def _membership_redirect():
    return RedirectResponse(url="/admin/memberships", status_code=302)


def _render_membership_form(
    request: Request,
    *,
    me,
    item,
    error: str | None = None,
    pmap: dict[str, float] | None = None,
):
    return templates.TemplateResponse(
        request,
        "membership_form.html",
        membership_form_context(
            request=request,
            me=me,
            item=item,
            error=error,
            kinds=membership_kind_values(),
            pmap=pmap,
        ),
    )


def _load_membership_price_map(
    db: Session,
    *,
    membership_id: int,
) -> dict[str, float]:
    prices = db.scalars(
        select(MembershipPrice).where(MembershipPrice.membership_id == membership_id)
    ).all()
    return price_map(prices)


@router.get("/admin/memberships", response_class=HTMLResponse)
def memberships_list(
    request: Request,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    pagination = parse_pagination_params(page, page_size)

    base_stmt = select(Membership)
    if q.strip():
        like = f"%{q.strip()}%"
        base_stmt = base_stmt.where(Membership.name.ilike(like))

    total = db.scalar(
        select(func.count()).select_from(base_stmt.order_by(None).subquery())
    ) or 0

    items = db.scalars(
        base_stmt
        .order_by(Membership.id.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    ).all()

    membership_ids = [item.id for item in items]
    prices_by_mid = load_prices_for_membership_ids(
        db,
        membership_ids=membership_ids,
    )

    pagination_ctx = build_pagination_context(
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )

    return templates.TemplateResponse(
        request,
        "admin_memberships.html",
        membership_list_context(
            request=request,
            me=me,
            items=items,
            q=q,
            prices_by_mid=prices_by_mid,
            pagination_ctx=pagination_ctx,
        ),
    )


@router.get("/admin/memberships/new", response_class=HTMLResponse)
def membership_new_page(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    return _render_membership_form(
        request,
        me=me,
        item=None,
        error=None,
        pmap=None,
    )


@router.post("/admin/memberships/new")
def membership_new(
    name: str = Form(...),
    kind: str = Form(...),
    funcional_classes: int = Form(0),
    musculacion_classes: int = Form(0),
    funcional_unlimited: str = Form(""),
    musculacion_unlimited: str = Form(""),
    price_lista: str = Form(""),
    price_efectivo: str = Form(""),
    price_transferencia: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    membership_kind = MembershipKind(kind)

    payload = build_membership_payload(
        name=name,
        kind=membership_kind,
        funcional_classes=funcional_classes,
        musculacion_classes=musculacion_classes,
        funcional_unlimited_raw=funcional_unlimited,
        musculacion_unlimited_raw=musculacion_unlimited,
    )

    item = Membership(
        **payload,
        is_active=True,
    )
    db.add(item)
    db.commit()

    sync_membership_prices(
        db,
        membership_id=item.id,
        method_amounts=price_inputs_to_method_map(
            price_lista=price_lista,
            price_efectivo=price_efectivo,
            price_transferencia=price_transferencia,
        ),
    )
    db.commit()

    return _membership_redirect()


@router.get("/admin/memberships/{mid}/edit", response_class=HTMLResponse)
def membership_edit_page(
    request: Request,
    mid: int = FPath(...),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    item = db.get(Membership, mid)
    if not item:
        return _membership_redirect()

    return _render_membership_form(
        request,
        me=me,
        item=item,
        error=None,
        pmap=_load_membership_price_map(db, membership_id=item.id),
    )


@router.post("/admin/memberships/{mid}/edit")
def membership_edit(
    mid: int,
    name: str = Form(...),
    kind: str = Form(...),
    funcional_classes: int = Form(0),
    musculacion_classes: int = Form(0),
    funcional_unlimited: str = Form(""),
    musculacion_unlimited: str = Form(""),
    price_lista: str = Form(""),
    price_efectivo: str = Form(""),
    price_transferencia: str = Form(""),
    is_active: str = Form("true"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    item = db.get(Membership, mid)
    if not item:
        return _membership_redirect()

    membership_kind = MembershipKind(kind)

    payload = build_membership_payload(
        name=name,
        kind=membership_kind,
        funcional_classes=funcional_classes,
        musculacion_classes=musculacion_classes,
        funcional_unlimited_raw=funcional_unlimited,
        musculacion_unlimited_raw=musculacion_unlimited,
    )

    item.name = payload["name"]
    item.kind = payload["kind"]
    item.funcional_classes = payload["funcional_classes"]
    item.musculacion_classes = payload["musculacion_classes"]
    item.funcional_unlimited = payload["funcional_unlimited"]
    item.musculacion_unlimited = payload["musculacion_unlimited"]
    item.is_active = (is_active or "").strip().lower() in ("true", "1", "on", "yes")

    sync_membership_prices(
        db,
        membership_id=item.id,
        method_amounts=price_inputs_to_method_map(
            price_lista=price_lista,
            price_efectivo=price_efectivo,
            price_transferencia=price_transferencia,
        ),
    )

    db.commit()
    return _membership_redirect()


def _render_assign(
    request: Request,
    *,
    me,
    memberships,
    students,
    error: str | None = None,
    ok: str | None = None,
):
    return templates.TemplateResponse(
        request,
        "membership_assign.html",
        assign_page_context(
            request=request,
            me=me,
            memberships=memberships,
            students=students,
            ok=ok,
            error=error,
        ),
    )


@router.get("/admin/memberships/assign", response_class=HTMLResponse)
def membership_assign_page(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    memberships = load_active_memberships(db)
    students = load_active_students(db)

    return _render_assign(
        request,
        me=me,
        memberships=memberships,
        students=students,
        error=None,
        ok=None,
    )


@router.post("/admin/memberships/assign", response_class=HTMLResponse)
def membership_assign_do(
    request: Request,
    student_id: int = Form(...),
    membership_id: int = Form(...),
    start_date: str = Form(""),
    payment_method: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    memberships = load_active_memberships(db)
    students = load_active_students(db)

    student = db.get(User, student_id)
    item = db.get(Membership, membership_id)

    entity_error = validate_assignment_entities(
        student=student,
        membership=item,
        alumno_role=Role.ALUMNO,
    )
    if entity_error:
        return _render_assign(
            request,
            me=me,
            memberships=memberships,
            students=students,
            error=entity_error,
            ok=None,
        )

    try:
        sd = parse_assignment_start_date(start_date)
    except Exception:
        return _render_assign(
            request,
            me=me,
            memberships=memberships,
            students=students,
            error="Fecha inválida. Usá YYYY-MM-DD.",
            ok=None,
        )

    try:
        pm = parse_optional_payment_method(payment_method)
    except Exception:
        return _render_assign(
            request,
            me=me,
            memberships=memberships,
            students=students,
            error="Método de pago inválido.",
            ok=None,
        )

    period = resolve_assignment_period(sd)

    if assignment_active_duplicate_exists(
        db,
        student_id=student.id,
        period=period,
    ):
        deactivate_active_assignments_for_period(
            db,
            student_id=student.id,
            period=period,
        )

    snap = resolve_assignment_amount_snapshot(
        db,
        membership_id=item.id,
        payment_method=pm,
    )

    try:
        assignment = build_membership_assignment(
            membership_id=item.id,
            student_id=student.id,
            assigned_by=me.id,
            start_date=sd,
            period=period,
            payment_method=pm,
            amount_snapshot=snap,
        )
        db.add(assignment)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if is_membership_assignment_duplicate_integrity_error(exc):
            return _render_assign(
                request,
                me=me,
                memberships=memberships,
                students=students,
                error=build_assignment_duplicate_message(
                    student_full_name=student.full_name,
                    period=period,
                ),
                ok=None,
            )
        raise

    return _render_assign(
        request,
        me=me,
        memberships=memberships,
        students=students,
        error=None,
        ok=build_assignment_success_message(
            student_full_name=student.full_name,
            period=period,
        ),
    )


def _render_consume(
    request: Request,
    *,
    me,
    students,
    period: str,
    error: str | None = None,
    ok: str | None = None,
):
    return templates.TemplateResponse(
        request,
        "membership_consume.html",
        consume_page_context(
            request=request,
            me=me,
            students=students,
            period=period,
            error=error,
            ok=ok,
        ),
    )


@router.get("/admin/memberships/consume", response_class=HTMLResponse)
def consume_page(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    students = load_active_students(db)
    period = current_membership_period()

    return _render_consume(
        request,
        me=me,
        students=students,
        period=period,
        error=None,
        ok=None,
    )


@router.post("/admin/memberships/consume", response_class=HTMLResponse)
def consume_do(
    request: Request,
    student_id: int = Form(...),
    service: str = Form(...),
    used_at: str = Form(""),
    used_time: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    students = load_active_students(db)
    current_period = current_membership_period()

    student = db.get(User, student_id)
    if (not student) or (student.role != Role.ALUMNO):
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error="Alumno inválido.",
            ok=None,
        )

    try:
        used_date = parse_usage_date(used_at)
    except Exception:
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error="Fecha inválida. Usá YYYY-MM-DD.",
            ok=None,
        )

    date_error = validate_usage_date_for_current_period(
        used_date,
        current_period=current_period,
    )
    if date_error:
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error=date_error,
            ok=None,
        )

    try:
        svc = ServiceKind(service)
    except Exception:
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error="Servicio inválido.",
            ok=None,
        )

    try:
        used_clock = parse_usage_time(used_time)
    except Exception:
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error="Hora inválida. Usá HH:MM (ej: 07:30).",
            ok=None,
        )

    time_error = validate_usage_time_window(used_clock)
    if time_error:
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error=time_error,
            ok=None,
        )

    assignment = get_active_assignment_for_period(
        db,
        student_id=student.id,
        period=current_period,
    )
    if not assignment:
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error=build_missing_assignment_message(period=current_period),
            ok=None,
        )

    if usage_duplicate_exists(
        db,
        student_id=student.id,
        service=svc,
        used_date=used_date,
    ):
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error=build_duplicate_usage_message(
                service_value=svc.value,
                student_full_name=student.full_name,
                used_date=used_date,
            ),
            ok=None,
        )

    capacity_error, _used_count = validate_membership_usage_capacity(
        db,
        student_id=student.id,
        membership=assignment.membership,
        period=current_period,
        service=svc,
    )
    if capacity_error:
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error=capacity_error,
            ok=None,
        )

    if usage_duplicate_exists(
        db,
        student_id=student.id,
        service=svc,
        used_date=used_date,
    ):
        return _render_consume(
            request,
            me=me,
            students=students,
            period=current_period,
            error=build_duplicate_usage_message(
                service_value=svc.value,
                student_full_name=student.full_name,
                used_date=used_date,
            ),
            ok=None,
        )

    try:
        register_membership_usage(
            db,
            assignment=assignment,
            student=student,
            service=svc,
            used_date=used_date,
            used_clock=used_clock,
            period=current_period,
            notes=notes,
            created_by=me.id,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if is_membership_usage_duplicate_integrity_error(exc):
            return _render_consume(
                request,
                me=me,
                students=students,
                period=current_period,
                error=build_duplicate_usage_message(
                    service_value=svc.value,
                    student_full_name=student.full_name,
                    used_date=used_date,
                ),
                ok=None,
            )
        raise

    return _render_consume(
        request,
        me=me,
        students=students,
        period=current_period,
        error=None,
        ok=build_consume_success_message(
            service_value=svc.value,
            student_full_name=student.full_name,
            used_date=used_date,
            used_clock=used_clock,
        ),
    )


@router.get("/admin/memberships/report", response_class=HTMLResponse)
def report_page(
    request: Request,
    period: str = "",
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    normalized_period = normalize_period_input(period)
    rows = summarize_membership_report(db, period=normalized_period)

    return templates.TemplateResponse(
        request,
        "membership_report.html",
        report_page_context(
            request=request,
            me=me,
            period=normalized_period,
            rows=rows,
        ),
    )


@router.get("/admin/qr", response_class=HTMLResponse)
def admin_qr_page(
    request: Request,
    service: str = "FUNCIONAL",
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    normalized_service = normalize_qr_service(service)
    payload = qr_make_payload(service=normalized_service, d=date.today())

    return templates.TemplateResponse(
        request,
        "admin_qr.html",
        qr_page_context(
            request=request,
            me=me,
            service=normalized_service,
            payload=payload,
        ),
    )