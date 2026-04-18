from collections import defaultdict
from datetime import date, datetime, time as dtime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import (
    Membership,
    MembershipAssignment,
    MembershipKind,
    MembershipPrice,
    MembershipUsage,
    PaymentMethod,
    ServiceKind,
    User,
)


CHECKBOX_TRUE_VALUES = {"on", "true", "1", "yes"}
QR_ALLOWED_SERVICES = {"FUNCIONAL", "MUSCULACION"}


def membership_kind_values() -> list[str]:
    return [k.value for k in MembershipKind]


def parse_amount(raw: str | None) -> float | None:
    value = (raw or "").strip().replace(",", ".")
    if not value:
        return None

    try:
        return float(Decimal(value))
    except (InvalidOperation, ValueError):
        return None


def parse_checkbox(raw: str | None) -> bool:
    return (raw or "").strip().lower() in CHECKBOX_TRUE_VALUES


def price_map(prices: list[MembershipPrice]) -> dict[str, float]:
    result: dict[str, float] = {}
    for price in prices:
        result[price.payment_method.value] = float(price.amount)
    return result


def prices_by_membership_map(prices: list[MembershipPrice]) -> dict[int, dict[str, float]]:
    result: dict[int, dict[str, float]] = {}
    for price in prices:
        result.setdefault(price.membership_id, {})
        result[price.membership_id][price.payment_method.value] = float(price.amount)
    return result


def load_prices_for_membership_ids(
    db: Session,
    *,
    membership_ids: list[int],
) -> dict[int, dict[str, float]]:
    if not membership_ids:
        return {}

    prices = db.scalars(
        select(MembershipPrice)
        .where(MembershipPrice.membership_id.in_(membership_ids))
        .order_by(MembershipPrice.id.asc())
    ).all()
    return prices_by_membership_map(prices)


def build_membership_payload(
    *,
    name: str,
    kind,
    funcional_classes: int,
    musculacion_classes: int,
    funcional_unlimited_raw: str | None,
    musculacion_unlimited_raw: str | None,
) -> dict:
    fu = parse_checkbox(funcional_unlimited_raw)
    mu = parse_checkbox(musculacion_unlimited_raw)

    fc = None
    mc = None

    if kind.value == "FUNCIONAL":
        fc = None if fu else (funcional_classes if funcional_classes > 0 else None)
        mc = None
        mu = False
    elif kind.value == "MUSCULACION":
        mc = None if mu else (musculacion_classes if musculacion_classes > 0 else None)
        fc = None
        fu = False
    elif kind.value == "COMBINACION":
        fu = False
        mu = False
        fc = funcional_classes if funcional_classes > 0 else None
        mc = musculacion_classes if musculacion_classes > 0 else None
    else:  # CLASE_SUELTA
        fu = False
        mu = False
        fc = None
        mc = None

    return {
        "name": (name or "").strip(),
        "kind": kind,
        "funcional_classes": fc,
        "musculacion_classes": mc,
        "funcional_unlimited": fu,
        "musculacion_unlimited": mu,
    }


def price_inputs_to_method_map(
    *,
    price_lista: str,
    price_efectivo: str,
    price_transferencia: str,
) -> dict[PaymentMethod, float | None]:
    return {
        PaymentMethod.LISTA: parse_amount(price_lista),
        PaymentMethod.EFECTIVO: parse_amount(price_efectivo),
        PaymentMethod.TRANSFERENCIA: parse_amount(price_transferencia),
    }


def sync_membership_prices(
    db: Session,
    *,
    membership_id: int,
    method_amounts: dict[PaymentMethod, float | None],
) -> None:
    existing_rows = db.scalars(
        select(MembershipPrice).where(MembershipPrice.membership_id == membership_id)
    ).all()

    existing_by_method = {row.payment_method: row for row in existing_rows}

    for method, amount in method_amounts.items():
        row = existing_by_method.get(method)

        if amount is None:
            if row:
                db.delete(row)
            continue

        if row:
            row.amount = amount
        else:
            db.add(
                MembershipPrice(
                    membership_id=membership_id,
                    payment_method=method,
                    amount=amount,
                )
            )


def membership_form_context(
    *,
    request,
    me,
    item,
    error: str | None,
    kinds: list[str],
    pmap: dict[str, float] | None = None,
) -> dict:
    return {
        "request": request,
        "me": me,
        "item": item,
        "error": error,
        "kinds": kinds,
        "pmap": pmap or {},
    }


def membership_list_context(
    *,
    request,
    me,
    items,
    q: str,
    prices_by_mid: dict[int, dict[str, float]],
    pagination_ctx: dict,
) -> dict:
    return {
        "request": request,
        "me": me,
        "items": items,
        "q": q,
        "prices_by_mid": prices_by_mid,
        **pagination_ctx,
    }


def consume_page_context(
    *,
    request,
    me,
    students,
    period: str,
    error: str | None,
    ok: str | None,
) -> dict:
    return {
        "request": request,
        "me": me,
        "students": students,
        "period": period,
        "error": error,
        "ok": ok,
    }


def assign_page_context(
    *,
    request,
    me,
    memberships,
    students,
    ok: str | None,
    error: str | None,
) -> dict:
    return {
        "request": request,
        "me": me,
        "memberships": memberships,
        "students": students,
        "ok": ok,
        "error": error,
    }


def report_page_context(
    *,
    request,
    me,
    period: str,
    rows,
) -> dict:
    return {
        "request": request,
        "me": me,
        "period": period,
        "rows": rows,
    }


def qr_page_context(
    *,
    request,
    me,
    service: str,
    payload: str,
) -> dict:
    return {
        "request": request,
        "me": me,
        "service": service,
        "payload": payload,
    }


def load_active_students(db: Session) -> list[User]:
    return db.scalars(
        select(User)
        .where(User.role == "ALUMNO", User.is_active == True)
        .order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc())
    ).all()


def load_active_memberships(db: Session) -> list[Membership]:
    return db.scalars(
        select(Membership)
        .where(Membership.is_active == True)
        .order_by(Membership.name.asc(), Membership.id.asc())
    ).all()


def current_membership_period(today: date | None = None) -> str:
    base = today or date.today()
    return base.strftime("%Y-%m")


def normalize_period_input(period: str | None, *, today: date | None = None) -> str:
    value = (period or "").strip()
    if not value:
        return current_membership_period(today=today)

    try:
        parsed = datetime.strptime(value, "%Y-%m")
        return parsed.strftime("%Y-%m")
    except ValueError:
        return current_membership_period(today=today)


def normalize_qr_service(service: str | None) -> str:
    value = (service or "").upper().strip()
    if value not in QR_ALLOWED_SERVICES:
        return "FUNCIONAL"
    return value


def summarize_membership_report(
    db: Session,
    *,
    period: str,
) -> list[dict]:
    assignments = db.scalars(
        select(MembershipAssignment)
        .where(
            MembershipAssignment.period_yyyymm == period,
            MembershipAssignment.is_active == True,
        )
        .order_by(MembershipAssignment.id.desc())
    ).all()

    if not assignments:
        return []

    usage_rows = db.execute(
        select(
            MembershipUsage.student_id,
            MembershipUsage.service,
            func.count(MembershipUsage.id),
        )
        .where(MembershipUsage.period_yyyymm == period)
        .group_by(MembershipUsage.student_id, MembershipUsage.service)
    ).all()

    usage_map: dict[tuple[int, str], int] = defaultdict(int)
    for student_id, service, count_value in usage_rows:
        service_value = service.value if hasattr(service, "value") else str(service)
        usage_map[(student_id, service_value)] = int(count_value or 0)

    rows: list[dict] = []
    for assignment in assignments:
        student = assignment.student
        membership = assignment.membership

        used_f = usage_map.get((student.id, ServiceKind.FUNCIONAL.value), 0)
        used_m = usage_map.get((student.id, ServiceKind.MUSCULACION.value), 0)

        rem_f = (
            "Libre"
            if membership.funcional_unlimited
            else (membership.funcional_classes or 0) - used_f
        )
        rem_m = (
            "Libre"
            if membership.musculacion_unlimited
            else (membership.musculacion_classes or 0) - used_m
        )

        rows.append(
            {
                "student": student,
                "membership": membership,
                "used_f": used_f,
                "used_m": used_m,
                "rem_f": rem_f,
                "rem_m": rem_m,
            }
        )

    return rows


def parse_usage_date(raw: str | None, *, today: date | None = None) -> date:
    if (raw or "").strip():
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    return today or date.today()


def parse_usage_time(raw: str | None, *, now: datetime | None = None) -> dtime:
    if (raw or "").strip():
        hh, mm = raw.strip().split(":")
        return dtime(int(hh), int(mm))

    current = now or datetime.now()
    return dtime(current.hour, current.minute)


def validate_usage_date_for_current_period(
    used_date: date,
    *,
    current_period: str,
) -> str | None:
    if used_date.weekday() == 6:
        return "No se puede registrar consumo en domingo (gimnasio cerrado)."

    used_period = used_date.strftime("%Y-%m")
    if used_period != current_period:
        return f"Solo se permite registrar consumos del mes actual ({current_period})."

    return None


def validate_usage_time_window(used_clock: dtime) -> str | None:
    if not (dtime(7, 0) <= used_clock <= dtime(22, 0)):
        return "Fuera de horario. Solo 07:00 a 22:00."
    return None


def get_active_assignment_for_period(
    db: Session,
    *,
    student_id: int,
    period: str,
):
    return db.scalars(
        select(MembershipAssignment)
        .where(
            MembershipAssignment.student_id == student_id,
            MembershipAssignment.is_active == True,
            MembershipAssignment.period_yyyymm == period,
        )
        .order_by(MembershipAssignment.created_at.desc())
        .options(joinedload(MembershipAssignment.membership))
    ).first()


def usage_duplicate_exists(
    db: Session,
    *,
    student_id: int,
    service,
    used_date: date,
) -> bool:
    duplicate = db.scalar(
        select(MembershipUsage.id).where(
            MembershipUsage.student_id == student_id,
            MembershipUsage.used_at == used_date,
            MembershipUsage.service == service,
        ).limit(1)
    )
    return bool(duplicate)


def resolve_membership_service_limits(
    membership,
    *,
    service,
) -> tuple[bool, int | None]:
    if service == ServiceKind.FUNCIONAL:
        unlimited = bool(membership.funcional_unlimited)
        allowed = None if unlimited else (membership.funcional_classes or 0)
        return unlimited, allowed

    unlimited = bool(membership.musculacion_unlimited)
    allowed = None if unlimited else (membership.musculacion_classes or 0)
    return unlimited, allowed


def count_usage_for_period(
    db: Session,
    *,
    student_id: int,
    period: str,
    service,
) -> int:
    return db.scalar(
        select(func.count(MembershipUsage.id)).where(
            MembershipUsage.student_id == student_id,
            MembershipUsage.period_yyyymm == period,
            MembershipUsage.service == service,
        )
    ) or 0


def validate_membership_usage_capacity(
    db: Session,
    *,
    student_id: int,
    membership,
    period: str,
    service,
) -> tuple[str | None, int]:
    unlimited, allowed = resolve_membership_service_limits(membership, service=service)
    used_count = count_usage_for_period(
        db,
        student_id=student_id,
        period=period,
        service=service,
    )

    if unlimited:
        return None, used_count

    if (allowed or 0) <= 0:
        return f"No hay cupo configurado para {service.value} en la membresía.", used_count

    if used_count >= allowed:
        return f"Cupo agotado para {service.value}. Usadas {used_count}/{allowed}.", used_count

    return None, used_count


def register_membership_usage(
    db: Session,
    *,
    assignment,
    student,
    service,
    used_date: date,
    used_clock: dtime,
    period: str,
    notes: str,
    created_by: int,
):
    usage = MembershipUsage(
        assignment_id=assignment.id,
        student_id=student.id,
        service=service,
        used_at=used_date,
        used_at_time=used_clock,
        period_yyyymm=period,
        notes=(notes or "").strip(),
        created_by=created_by,
    )
    db.add(usage)
    db.flush()
    return usage


def build_assignment_success_message(*, student_full_name: str, period: str) -> str:
    return f"Membresía asignada correctamente para {student_full_name} en {period}."


def build_consume_success_message(
    *,
    service_value: str,
    student_full_name: str,
    used_date: date,
    used_clock: dtime,
) -> str:
    return (
        f"OK: registrado {service_value} para {student_full_name} "
        f"({used_date} {used_clock.strftime('%H:%M')})."
    )


def build_duplicate_usage_message(
    *,
    service_value: str,
    student_full_name: str,
    used_date: date,
) -> str:
    return f"Ya existe un consumo de {service_value} para {student_full_name} en {used_date}."


def build_missing_assignment_message(*, period: str) -> str:
    return f"El alumno no tiene membresía activa para {period}."


def build_assignment_duplicate_message(*, student_full_name: str, period: str) -> str:
    return f"Ya existe una membresía activa para {student_full_name} en {period}."


def is_membership_usage_duplicate_integrity_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    if "unique" not in text:
        return False

    duplicate_markers = (
        "uq_membership_usage_student_date_service",
        "membership_usages",
        "student_id",
        "used_at",
        "service",
    )
    return any(marker in text for marker in duplicate_markers)


def parse_assignment_start_date(raw: str | None, *, today: date | None = None) -> date | None:
    if not (raw or "").strip():
        return None
    return datetime.strptime(raw.strip(), "%Y-%m-%d").date()


def resolve_assignment_period(start_date: date | None, *, today: date | None = None) -> str:
    base = start_date or today or date.today()
    return base.strftime("%Y-%m")


def parse_optional_payment_method(raw: str | None):
    value = (raw or "").strip()
    if not value:
        return None
    return PaymentMethod(value)


def get_membership_price_for_method(
    db: Session,
    *,
    membership_id: int,
    payment_method,
):
    if payment_method is None:
        return None

    return db.scalars(
        select(MembershipPrice).where(
            MembershipPrice.membership_id == membership_id,
            MembershipPrice.payment_method == payment_method,
        )
    ).first()


def deactivate_active_assignments_for_period(
    db: Session,
    *,
    student_id: int,
    period: str,
) -> int:
    return db.query(MembershipAssignment).filter(
        MembershipAssignment.student_id == student_id,
        MembershipAssignment.is_active == True,
        MembershipAssignment.period_yyyymm == period,
    ).update({"is_active": False})


def build_membership_assignment(
    *,
    membership_id: int,
    student_id: int,
    assigned_by: int,
    start_date: date | None,
    period: str,
    payment_method,
    amount_snapshot: float | None,
):
    return MembershipAssignment(
        membership_id=membership_id,
        student_id=student_id,
        assigned_by=assigned_by,
        start_date=start_date,
        is_active=True,
        period_yyyymm=period,
        payment_method=payment_method,
        amount_snapshot=amount_snapshot,
    )


def resolve_assignment_amount_snapshot(
    db: Session,
    *,
    membership_id: int,
    payment_method,
) -> float | None:
    price = get_membership_price_for_method(
        db,
        membership_id=membership_id,
        payment_method=payment_method,
    )
    if not price:
        return None
    return float(price.amount)


def validate_assignment_entities(*, student, membership, alumno_role) -> str | None:
    if not student:
        return "Alumno inválido."
    if student.role != alumno_role:
        return "Alumno inválido."
    if not membership:
        return "Membresía inválida."
    if not membership.is_active:
        return "La membresía seleccionada está inactiva."
    return None


def assignment_active_duplicate_exists(
    db: Session,
    *,
    student_id: int,
    period: str,
) -> bool:
    duplicate = db.scalar(
        select(MembershipAssignment.id).where(
            MembershipAssignment.student_id == student_id,
            MembershipAssignment.period_yyyymm == period,
            MembershipAssignment.is_active == True,
        ).limit(1)
    )
    return bool(duplicate)


def is_membership_assignment_duplicate_integrity_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    if "unique" not in text:
        return False

    duplicate_markers = (
        "uq_membership_assignment_student_period_active",
        "membership_assignments",
        "student_id",
        "period_yyyymm",
        "is_active",
    )
    return any(marker in text for marker in duplicate_markers)