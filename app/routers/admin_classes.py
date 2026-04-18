from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import (
    User,
    Role,
    GymClass,
    ClassGroup,
    ClassEnrollment,
    ClassStatus,
    Weekday,
    EnrollmentStatus,
    PaymentMethod,
    ServiceKind,
)
from ..services.admin_list_service import parse_pagination_params, build_pagination_context
from ..services.class_service import (
    active_enrollment_count,
    active_enrollment_counts_for_group_ids,
    apply_enrollment_state,
    build_enrollment_payload,
    build_extra_enrollment_note,
    build_final_enrollment_notes,
    class_group_detail_context,
    classes_enrollment_context,
    classes_list_context,
    count_classes,
    count_enrollable_groups,
    count_group_enrollments,
    get_existing_enrollment,
    get_group_and_class_for_enrollment,
    is_class_enrollment_duplicate_integrity_error,
    load_classes_with_groups_paginated,
    load_enrollable_groups_paginated,
    load_group_enrollments_paginated,
    load_group_with_detail,
    load_student_active_enrollments,
    load_student_enrollment_map,
    load_student_options,
    normalize_group_name,
    parse_capacity_safe,
    parse_time_safe,
    resolve_student_slot_summary,
    resolve_target_student_id,
    student_available_class_slots,
    validate_enrollment_cancel_permission,
    validate_group_capacity_available,
    validate_group_creation_rules,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ALLOWED_MANAGE = ["ADMINISTRADOR", "ADMINISTRATIVO"]
ALLOWED_ENROLL = ["ADMINISTRADOR", "ADMINISTRATIVO", "ALUMNO"]


def _classes_redirect():
    return RedirectResponse("/admin/classes", status_code=302)


def _classes_enrollments_redirect():
    return RedirectResponse("/admin/classes/enrollments", status_code=302)


def _render_classes_list(
    request: Request,
    *,
    me,
    classes,
    group_counts: dict[int, int],
    q: str,
    status: str,
    service_kind: str,
    pagination_ctx: dict,
):
    return templates.TemplateResponse(
        request,
        "classes_list.html",
        classes_list_context(
            request=request,
            me=me,
            classes=classes,
            group_counts=group_counts,
            statuses=[s.value for s in ClassStatus],
            weekdays=[d.value for d in Weekday],
            service_kinds=[s.value for s in ServiceKind],
            q=q,
            status=status,
            service_kind=service_kind,
            pagination_ctx=pagination_ctx,
        ),
    )


def _render_classes_enrollment(
    request: Request,
    *,
    me,
    groups,
    counts: dict[int, int],
    student_options,
    my_enrollments,
    q: str,
    weekday: str,
    my_active_rows,
    available_slots,
    available_funcional,
    available_musculacion,
    pagination_ctx: dict,
):
    return templates.TemplateResponse(
        request,
        "classes_enrollments.html",
        classes_enrollment_context(
            request=request,
            me=me,
            groups=groups,
            counts=counts,
            student_options=student_options,
            my_enrollments=my_enrollments,
            q=q,
            weekday=weekday,
            weekdays=[d.value for d in Weekday],
            my_active_rows=my_active_rows,
            available_slots=available_slots,
            available_funcional=available_funcional,
            available_musculacion=available_musculacion,
            pagination_ctx=pagination_ctx,
        ),
    )


def _render_class_group_detail(
    request: Request,
    *,
    me,
    group,
    enrollments,
    active_count: int,
    pagination_ctx: dict,
):
    return templates.TemplateResponse(
        request,
        "class_group_detail.html",
        class_group_detail_context(
            request=request,
            me=me,
            group=group,
            enrollments=enrollments,
            active_count=active_count,
            pagination_ctx=pagination_ctx,
        ),
    )


@router.get("/admin/classes", response_class=HTMLResponse)
def classes_list(
    request: Request,
    q: str = "",
    status: str = "",
    service_kind: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED_MANAGE)),
):
    pagination = parse_pagination_params(page, page_size)

    total = count_classes(
        db,
        q=q,
        status=status,
        service_kind=service_kind,
    )
    classes = load_classes_with_groups_paginated(
        db,
        q=q,
        status=status,
        service_kind=service_kind,
        offset=pagination.offset,
        limit=pagination.page_size,
    )

    group_ids: list[int] = []
    for gym_class in classes:
        for group in gym_class.groups:
            group_ids.append(group.id)

    group_counts = active_enrollment_counts_for_group_ids(
        db,
        group_ids=group_ids,
    )

    pagination_ctx = build_pagination_context(
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )

    return _render_classes_list(
        request,
        me=me,
        classes=classes,
        group_counts=group_counts,
        q=q,
        status=status,
        service_kind=service_kind,
        pagination_ctx=pagination_ctx,
    )


@router.post("/admin/classes/new")
def class_create(
    name: str = Form(...),
    description: str = Form(""),
    service_kind: str = Form("FUNCIONAL"),
    status: str = Form("ACTIVA"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED_MANAGE)),
):
    row = GymClass(
        name=(name or "").strip(),
        description=(description or "").strip(),
        service_kind=ServiceKind(service_kind),
        status=ClassStatus(status),
    )
    db.add(row)
    db.commit()
    return _classes_redirect()


@router.post("/admin/classes/{class_id}/groups/new")
def class_group_create(
    class_id: int,
    name: str = Form(""),
    weekday: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    capacity: int = Form(...),
    is_active: str = Form("1"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED_MANAGE)),
):
    gym_class = db.get(GymClass, class_id)
    if not gym_class:
        return _classes_redirect()

    try:
        parsed_start = parse_time_safe(start_time)
        parsed_end = parse_time_safe(end_time)
        parsed_capacity = parse_capacity_safe(capacity)
        parsed_weekday = Weekday(weekday)
    except Exception:
        return _classes_redirect()

    validation_error = validate_group_creation_rules(
        db,
        class_id=gym_class.id,
        weekday=parsed_weekday,
        start_time=parsed_start,
        end_time=parsed_end,
    )
    if validation_error:
        return _classes_redirect()

    row = ClassGroup(
        class_id=gym_class.id,
        name=normalize_group_name(name),
        weekday=parsed_weekday,
        start_time=parsed_start,
        end_time=parsed_end,
        capacity=parsed_capacity,
        is_active=(is_active == "1"),
        created_by_id=me.id,
    )
    db.add(row)
    db.commit()
    return _classes_redirect()


@router.get("/admin/classes/enrollments", response_class=HTMLResponse)
def classes_enrollment_page(
    request: Request,
    q: str = "",
    weekday: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED_ENROLL)),
):
    pagination = parse_pagination_params(page, page_size)

    total = count_enrollable_groups(
        db,
        weekday=weekday,
    )
    groups = load_enrollable_groups_paginated(
        db,
        weekday=weekday,
        offset=pagination.offset,
        limit=pagination.page_size,
    )

    counts = active_enrollment_counts_for_group_ids(
        db,
        group_ids=[g.id for g in groups],
    )

    student_options = []
    if me.role.value in ["ADMINISTRADOR", "ADMINISTRATIVO"]:
        student_options = load_student_options(
            db,
            q=q,
        )

    my_enrollments = {}
    my_active_rows = []
    available_slots = None
    available_funcional = None
    available_musculacion = None

    if me.role == Role.ALUMNO:
        my_enrollments = load_student_enrollment_map(
            db,
            student_id=me.id,
        )
        my_active_rows = load_student_active_enrollments(
            db,
            student_id=me.id,
        )
        slot_summary = resolve_student_slot_summary(
            db,
            student_id=me.id,
        )
        available_slots = slot_summary["available_slots"]
        available_funcional = slot_summary["available_funcional"]
        available_musculacion = slot_summary["available_musculacion"]

    pagination_ctx = build_pagination_context(
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )

    return _render_classes_enrollment(
        request,
        me=me,
        groups=groups,
        counts=counts,
        student_options=student_options,
        my_enrollments=my_enrollments,
        q=q,
        weekday=weekday,
        my_active_rows=my_active_rows,
        available_slots=available_slots,
        available_funcional=available_funcional,
        available_musculacion=available_musculacion,
        pagination_ctx=pagination_ctx,
    )


@router.post("/admin/classes/groups/{group_id}/enroll")
def class_group_enroll(
    group_id: int,
    student_id: int = Form(0),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED_ENROLL)),
):
    group, gym_class = get_group_and_class_for_enrollment(
        db,
        group_id=group_id,
    )
    if not group or not gym_class:
        return _classes_enrollments_redirect()

    target_student_id = resolve_target_student_id(
        actor=me,
        posted_student_id=student_id,
    )
    if not target_student_id:
        return _classes_enrollments_redirect()

    student = db.get(User, target_student_id)
    if not student:
        return _classes_enrollments_redirect()

    if not validate_group_capacity_available(
        db,
        group_id=group.id,
        capacity=group.capacity,
    ):
        return _classes_enrollments_redirect()

    available_slots = student_available_class_slots(
        db,
        student.id,
        gym_class.service_kind,
    )
    has_slots = available_slots > 0

    if me.role == Role.ALUMNO and not has_slots:
        return _classes_enrollments_redirect()

    existing = get_existing_enrollment(
        db,
        group_id=group.id,
        student_id=student.id,
    )

    extra_note = build_extra_enrollment_note(
        has_slots=has_slots,
        gym_class_service_kind=gym_class.service_kind,
        actor_role_value=me.role.value,
    )
    final_notes = build_final_enrollment_notes(
        notes=notes,
        extra_note=extra_note,
    )

    if existing:
        apply_enrollment_state(
            enrollment=existing,
            notes=final_notes,
            created_by_id=me.id,
        )
        db.commit()
        return _classes_enrollments_redirect()

    try:
        row = build_enrollment_payload(
            group_id=group.id,
            student_id=student.id,
            notes=final_notes,
            created_by_id=me.id,
        )
        db.add(row)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not is_class_enrollment_duplicate_integrity_error(exc):
            raise

        existing = get_existing_enrollment(
            db,
            group_id=group.id,
            student_id=student.id,
        )
        if existing:
            apply_enrollment_state(
                enrollment=existing,
                notes=final_notes,
                created_by_id=me.id,
            )
            db.commit()
            return _classes_enrollments_redirect()
        raise

    return _classes_enrollments_redirect()


@router.post("/admin/classes/enrollments/{enrollment_id}/cancel")
def class_enrollment_cancel(
    enrollment_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED_ENROLL)),
):
    row = db.get(ClassEnrollment, enrollment_id)
    if not validate_enrollment_cancel_permission(
        enrollment=row,
        actor=me,
    ):
        return _classes_enrollments_redirect()

    row.status = EnrollmentStatus.CANCELADA
    db.commit()
    return _classes_enrollments_redirect()


@router.get("/admin/classes/groups/{group_id}", response_class=HTMLResponse)
def class_group_detail(
    request: Request,
    group_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED_MANAGE)),
):
    group = load_group_with_detail(
        db,
        group_id=group_id,
    )
    if not group:
        return _classes_redirect()

    pagination = parse_pagination_params(page, page_size)
    total = count_group_enrollments(
        db,
        group_id=group.id,
    )
    enrollments = load_group_enrollments_paginated(
        db,
        group_id=group.id,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    active_count = active_enrollment_count(db, group.id)

    pagination_ctx = build_pagination_context(
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )

    return _render_class_group_detail(
        request,
        me=me,
        group=group,
        enrollments=enrollments,
        active_count=active_count,
        pagination_ctx=pagination_ctx,
    )