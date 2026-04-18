from datetime import date, time
from typing import Any

from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session, joinedload

from ..models import (
    ClassEnrollment,
    ClassGroup,
    ClassStatus,
    EnrollmentStatus,
    GymClass,
    Membership,
    MembershipAssignment,
    MembershipUsage,
    Role,
    ServiceKind,
    User,
    Weekday,
)


def parse_time_safe(value: str) -> time:
    raw = (value or "").strip()
    try:
        hh, mm = raw.split(":")
        parsed = time(hour=int(hh), minute=int(mm))
    except Exception as exc:
        raise ValueError("Hora inválida. Usá HH:MM.") from exc

    return parsed


def parse_capacity_safe(value: int | str) -> int:
    try:
        parsed = int(value)
    except Exception as exc:
        raise ValueError("Capacidad inválida.") from exc

    if parsed < 1:
        raise ValueError("La capacidad debe ser mayor o igual a 1.")

    return parsed


def normalize_group_name(value: str | None) -> str:
    return (value or "").strip()


def validate_group_time_range(
    *,
    start_time: time,
    end_time: time,
) -> str | None:
    if end_time <= start_time:
        return "El horario de fin debe ser mayor al horario de inicio."
    return None


def class_has_overlapping_group(
    db: Session,
    *,
    class_id: int,
    weekday: Weekday,
    start_time: time,
    end_time: time,
) -> bool:
    rows = db.scalars(
        select(ClassGroup).where(
            ClassGroup.class_id == class_id,
            ClassGroup.weekday == weekday,
            ClassGroup.is_active == True,
        )
    ).all()

    for row in rows:
        if start_time < row.end_time and end_time > row.start_time:
            return True

    return False


def validate_group_creation_rules(
    db: Session,
    *,
    class_id: int,
    weekday: Weekday,
    start_time: time,
    end_time: time,
) -> str | None:
    time_error = validate_group_time_range(
        start_time=start_time,
        end_time=end_time,
    )
    if time_error:
        return time_error

    if class_has_overlapping_group(
        db,
        class_id=class_id,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
    ):
        return "Ya existe un grupo activo solapado para esa clase en el mismo día."

    return None


def active_enrollment_count(db: Session, group_id: int) -> int:
    return db.scalar(
        select(func.count(ClassEnrollment.id)).where(
            ClassEnrollment.group_id == group_id,
            ClassEnrollment.status == EnrollmentStatus.ACTIVA,
        )
    ) or 0


def active_enrollment_counts_for_group_ids(
    db: Session,
    *,
    group_ids: list[int],
) -> dict[int, int]:
    if not group_ids:
        return {}

    rows = db.execute(
        select(
            ClassEnrollment.group_id,
            func.count(ClassEnrollment.id),
        )
        .where(
            ClassEnrollment.group_id.in_(group_ids),
            ClassEnrollment.status == EnrollmentStatus.ACTIVA,
        )
        .group_by(ClassEnrollment.group_id)
    ).all()

    result = {int(group_id): int(count_value or 0) for group_id, count_value in rows}
    for group_id in group_ids:
        result.setdefault(group_id, 0)
    return result


def build_classes_list_query(
    *,
    q: str = "",
    status: str = "",
    service_kind: str = "",
):
    stmt = select(GymClass)

    if (q or "").strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                GymClass.name.ilike(like),
                GymClass.description.ilike(like),
            )
        )

    if (status or "").strip():
        stmt = stmt.where(GymClass.status == ClassStatus(status.strip()))

    if (service_kind or "").strip():
        stmt = stmt.where(GymClass.service_kind == ServiceKind(service_kind.strip()))

    return stmt


def count_classes(
    db: Session,
    *,
    q: str = "",
    status: str = "",
    service_kind: str = "",
) -> int:
    stmt = build_classes_list_query(
        q=q,
        status=status,
        service_kind=service_kind,
    )
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


def load_classes_with_groups_paginated(
    db: Session,
    *,
    q: str = "",
    status: str = "",
    service_kind: str = "",
    offset: int = 0,
    limit: int = 20,
) -> list[GymClass]:
    stmt = (
        build_classes_list_query(
            q=q,
            status=status,
            service_kind=service_kind,
        )
        .options(joinedload(GymClass.groups))
        .order_by(GymClass.name.asc(), GymClass.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return db.execute(stmt).unique().scalars().all()


def build_enrollable_groups_query(
    *,
    weekday: str = "",
):
    stmt = (
        select(ClassGroup)
        .join(GymClass, ClassGroup.class_id == GymClass.id)
        .where(
            ClassGroup.is_active == True,
            GymClass.status == ClassStatus.ACTIVA,
        )
    )

    if (weekday or "").strip():
        stmt = stmt.where(ClassGroup.weekday == Weekday(weekday.strip()))

    return stmt


def count_enrollable_groups(
    db: Session,
    *,
    weekday: str = "",
) -> int:
    stmt = build_enrollable_groups_query(weekday=weekday)
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


def load_enrollable_groups_paginated(
    db: Session,
    *,
    weekday: str = "",
    offset: int = 0,
    limit: int = 20,
) -> list[ClassGroup]:
    stmt = (
        build_enrollable_groups_query(weekday=weekday)
        .options(joinedload(ClassGroup.gym_class))
        .order_by(ClassGroup.weekday.asc(), ClassGroup.start_time.asc(), ClassGroup.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(stmt).all()


def load_student_options(
    db: Session,
    *,
    q: str = "",
) -> list[User]:
    stmt = (
        select(User)
        .where(User.role == Role.ALUMNO)
        .order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc())
    )

    if (q or "").strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.full_name.ilike(like),
                User.email.ilike(like),
                User.dni.ilike(like),
            )
        )

    return db.scalars(stmt).all()


def get_student_latest_assignment(
    db: Session,
    *,
    student_id: int,
):
    return db.scalars(
        select(MembershipAssignment)
        .where(MembershipAssignment.student_id == student_id)
        .order_by(MembershipAssignment.id.desc())
    ).first()


def student_available_class_slots(
    db: Session,
    student_id: int,
    service_kind: ServiceKind | None = None,
) -> int:
    assignment = get_student_latest_assignment(db, student_id=student_id)
    if not assignment:
        return 0

    membership = db.get(Membership, assignment.membership_id)
    if not membership:
        return 0

    period_yyyymm = (assignment.period_yyyymm or "").strip() or date.today().strftime("%Y-%m")

    funcional_total = int(membership.funcional_classes or 0)
    musculacion_total = int(membership.musculacion_classes or 0)

    funcional_used = db.scalar(
        select(func.count(MembershipUsage.id)).where(
            MembershipUsage.student_id == student_id,
            MembershipUsage.period_yyyymm == period_yyyymm,
            MembershipUsage.service == ServiceKind.FUNCIONAL,
        )
    ) or 0

    musculacion_used = db.scalar(
        select(func.count(MembershipUsage.id)).where(
            MembershipUsage.student_id == student_id,
            MembershipUsage.period_yyyymm == period_yyyymm,
            MembershipUsage.service == ServiceKind.MUSCULACION,
        )
    ) or 0

    funcional_left = 999999 if membership.funcional_unlimited else max(0, funcional_total - funcional_used)
    musculacion_left = 999999 if membership.musculacion_unlimited else max(0, musculacion_total - musculacion_used)

    if service_kind == ServiceKind.FUNCIONAL:
        return funcional_left
    if service_kind == ServiceKind.MUSCULACION:
        return musculacion_left

    return funcional_left + musculacion_left


def student_has_available_slots(db: Session, student_id: int) -> bool:
    return student_available_class_slots(db, student_id) > 0


def load_student_enrollment_map(
    db: Session,
    *,
    student_id: int,
) -> dict[int, ClassEnrollment]:
    rows = db.scalars(
        select(ClassEnrollment).where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.status == EnrollmentStatus.ACTIVA,
        )
    ).all()
    return {row.group_id: row for row in rows}


def load_student_active_enrollments(
    db: Session,
    *,
    student_id: int,
) -> list[ClassEnrollment]:
    return db.scalars(
        select(ClassEnrollment)
        .options(joinedload(ClassEnrollment.group).joinedload(ClassGroup.gym_class))
        .where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.status == EnrollmentStatus.ACTIVA,
        )
        .order_by(ClassEnrollment.created_at.desc(), ClassEnrollment.id.desc())
    ).all()


def resolve_student_slot_summary(
    db: Session,
    *,
    student_id: int,
) -> dict[str, int]:
    funcional = student_available_class_slots(
        db,
        student_id,
        ServiceKind.FUNCIONAL,
    )
    musculacion = student_available_class_slots(
        db,
        student_id,
        ServiceKind.MUSCULACION,
    )
    return {
        "available_funcional": funcional,
        "available_musculacion": musculacion,
        "available_slots": (funcional or 0) + (musculacion or 0),
    }


def build_extra_enrollment_note(
    *,
    has_slots: bool,
    gym_class_service_kind: ServiceKind,
    actor_role_value: str,
) -> str:
    if actor_role_value in ["ADMINISTRADOR", "ADMINISTRATIVO"] and not has_slots:
        return f"INSCRIPTO SIN CLASES DISPONIBLES PARA {gym_class_service_kind.value}. DEBE PAGAR EL MES."
    return ""


def build_final_enrollment_notes(
    *,
    notes: str,
    extra_note: str,
) -> str:
    final_notes = (notes or "").strip()
    if extra_note:
        final_notes = f"{final_notes} | {extra_note}".strip(" |")
    return final_notes


def validate_enrollment_cancel_permission(
    *,
    enrollment,
    actor,
) -> bool:
    if not enrollment:
        return False
    if actor.role == Role.ALUMNO and enrollment.student_id != actor.id:
        return False
    return True


def get_group_and_class_for_enrollment(
    db: Session,
    *,
    group_id: int,
):
    group = db.get(ClassGroup, group_id)
    if not group or not group.is_active:
        return None, None

    gym_class = db.get(GymClass, group.class_id)
    if not gym_class or gym_class.status != ClassStatus.ACTIVA:
        return group, None

    return group, gym_class


def resolve_target_student_id(
    *,
    actor,
    posted_student_id: int | None,
) -> int:
    if actor.role == Role.ALUMNO:
        return actor.id
    return int(posted_student_id or 0)


def get_existing_enrollment(
    db: Session,
    *,
    group_id: int,
    student_id: int,
):
    return db.scalars(
        select(ClassEnrollment).where(
            ClassEnrollment.group_id == group_id,
            ClassEnrollment.student_id == student_id,
        )
    ).first()


def validate_group_capacity_available(
    db: Session,
    *,
    group_id: int,
    capacity: int,
) -> bool:
    current = active_enrollment_count(db, group_id)
    return current < capacity


def build_enrollment_payload(
    *,
    group_id: int,
    student_id: int,
    notes: str,
    created_by_id: int,
):
    return ClassEnrollment(
        group_id=group_id,
        student_id=student_id,
        status=EnrollmentStatus.ACTIVA,
        notes=notes,
        created_by_id=created_by_id,
    )


def apply_enrollment_state(
    *,
    enrollment,
    notes: str,
    created_by_id: int,
):
    enrollment.status = EnrollmentStatus.ACTIVA
    enrollment.notes = notes
    enrollment.created_by_id = created_by_id
    return enrollment


def is_class_enrollment_duplicate_integrity_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    if "unique" not in text:
        return False

    duplicate_markers = (
        "uq_class_enrollment_group_student",
        "class_enrollments",
        "group_id",
        "student_id",
    )
    return any(marker in text for marker in duplicate_markers)


def load_group_with_detail(db: Session, *, group_id: int):
    return db.scalar(
        select(ClassGroup)
        .options(
            joinedload(ClassGroup.gym_class),
            joinedload(ClassGroup.created_by),
        )
        .where(ClassGroup.id == group_id)
    )


def count_group_enrollments(
    db: Session,
    *,
    group_id: int,
) -> int:
    return db.scalar(
        select(func.count(ClassEnrollment.id)).where(
            ClassEnrollment.group_id == group_id
        )
    ) or 0


def load_group_enrollments_paginated(
    db: Session,
    *,
    group_id: int,
    offset: int = 0,
    limit: int = 20,
) -> list[ClassEnrollment]:
    return db.scalars(
        select(ClassEnrollment)
        .options(
            joinedload(ClassEnrollment.student),
            joinedload(ClassEnrollment.created_by),
        )
        .where(ClassEnrollment.group_id == group_id)
        .order_by(ClassEnrollment.created_at.desc(), ClassEnrollment.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()


def classes_list_context(
    *,
    request,
    me,
    classes,
    group_counts: dict[int, int],
    statuses: list[str],
    weekdays: list[str],
    service_kinds: list[str],
    q: str,
    status: str,
    service_kind: str,
    pagination_ctx: dict,
) -> dict[str, Any]:
    return {
        "request": request,
        "me": me,
        "classes": classes,
        "group_counts": group_counts,
        "statuses": statuses,
        "weekdays": weekdays,
        "service_kinds": service_kinds,
        "q": q,
        "status_filter": status,
        "service_kind_filter": service_kind,
        **pagination_ctx,
    }


def classes_enrollment_context(
    *,
    request,
    me,
    groups,
    counts: dict[int, int],
    student_options,
    my_enrollments,
    q: str,
    weekday: str,
    weekdays: list[str],
    my_active_rows,
    available_slots,
    available_funcional,
    available_musculacion,
    pagination_ctx: dict,
) -> dict[str, Any]:
    return {
        "request": request,
        "me": me,
        "groups": groups,
        "counts": counts,
        "student_options": student_options,
        "my_enrollments": my_enrollments,
        "q": q,
        "weekday": weekday,
        "weekdays": weekdays,
        "my_active_rows": my_active_rows,
        "available_slots": available_slots,
        "available_funcional": available_funcional,
        "available_musculacion": available_musculacion,
        **pagination_ctx,
    }


def class_group_detail_context(
    *,
    request,
    me,
    group,
    enrollments,
    active_count: int,
    pagination_ctx: dict,
) -> dict[str, Any]:
    return {
        "request": request,
        "me": me,
        "group": group,
        "enrollments": enrollments,
        "active_count": active_count,
        **pagination_ctx,
    }