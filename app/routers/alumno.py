import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime, date, time as dtime
from calendar import monthrange

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import select, func

from ..db import get_db
from ..deps import require_roles
from ..models import (
    RoutineAssignment,
    Routine,
    RoutineItem,
    RoutineType,
    MembershipAssignment,
    Membership,
    MembershipPrice,
    PaymentMethod,
    MembershipUsage,
    ServiceKind,
    CashMovement,
    CashPaymentStatus,
    GymClass,
    ClassGroup,
    ClassEnrollment,
    EnrollmentStatus,
)
from ..security import qr_verify_payload


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ALUM_ONLY = ["ALUMNO"]


def _day_number(label: str) -> int:
    if not label:
        return 999
    m = re.search(r"(\d+)", label)
    return int(m.group(1)) if m else 999


def _has_present_today(db: Session, student_id: int) -> bool:
    today = date.today()
    found = db.scalar(
        select(MembershipUsage.id)
        .where(MembershipUsage.student_id == student_id, MembershipUsage.used_at == today)
        .limit(1)
    )
    return bool(found)


def _weekday_to_enum(today: date) -> str:
    mapping = {
        0: "LUNES",
        1: "MARTES",
        2: "MIERCOLES",
        3: "JUEVES",
        4: "VIERNES",
        5: "SABADO",
        6: "DOMINGO",
    }
    return mapping[today.weekday()]


def _student_has_valid_class_enrollment_for_service(
    db: Session,
    student_id: int,
    service: ServiceKind,
) -> bool:
    rows = db.scalars(
        select(ClassEnrollment)
        .join(ClassGroup, ClassEnrollment.group_id == ClassGroup.id)
        .join(GymClass, ClassGroup.class_id == GymClass.id)
        .where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.status == EnrollmentStatus.ACTIVA,
            ClassGroup.is_active == True,
            GymClass.status == "ACTIVA",
            GymClass.service_kind == service,
        )
        .order_by(ClassEnrollment.id.desc())
    ).all()

    return len(rows) > 0


def _current_group_for_service_now(
    db: Session,
    service: ServiceKind,
    target_date: date,
    target_time: dtime,
):
    weekday_value = _weekday_to_enum(target_date)

    return db.scalars(
        select(ClassGroup)
        .join(GymClass, ClassGroup.class_id == GymClass.id)
        .options(joinedload(ClassGroup.gym_class))
        .where(
            ClassGroup.is_active == True,
            ClassGroup.weekday == weekday_value,
            ClassGroup.start_time <= target_time,
            ClassGroup.end_time >= target_time,
            GymClass.status == "ACTIVA",
            GymClass.service_kind == service,
        )
        .order_by(ClassGroup.start_time.asc(), ClassGroup.id.asc())
    ).first()


def _student_active_enrollments_for_service(
    db: Session,
    student_id: int,
    service: ServiceKind,
):
    return db.scalars(
        select(ClassEnrollment)
        .join(ClassGroup, ClassEnrollment.group_id == ClassGroup.id)
        .join(GymClass, ClassGroup.class_id == GymClass.id)
        .options(
            joinedload(ClassEnrollment.group).joinedload(ClassGroup.gym_class)
        )
        .where(
            ClassEnrollment.student_id == student_id,
            ClassEnrollment.status == EnrollmentStatus.ACTIVA,
            ClassGroup.is_active == True,
            GymClass.status == "ACTIVA",
            GymClass.service_kind == service,
        )
        .order_by(ClassEnrollment.id.desc())
    ).all()


def _move_student_to_current_group_if_needed(
    db: Session,
    student_id: int,
    service: ServiceKind,
    current_group: ClassGroup,
):
    """
    Si el alumno está inscripto en otra clase/horario del mismo servicio,
    lo mueve al grupo actual:
    - cancela las inscripciones activas del mismo servicio en otros grupos
    - mantiene o crea inscripción activa en el grupo actual
    """
    enrollments = _student_active_enrollments_for_service(db, student_id, service)

    if not enrollments:
        return None

    current_enrollment = None
    for enr in enrollments:
        if enr.group_id == current_group.id:
            current_enrollment = enr
        else:
            enr.status = EnrollmentStatus.CANCELADA
            extra = "Reasignado automáticamente por asistencia QR a otra clase/horario."
            enr.notes = f"{(enr.notes or '').strip()} | {extra}".strip(" |")

    if current_enrollment:
        return current_enrollment

    new_row = ClassEnrollment(
        group_id=current_group.id,
        student_id=student_id,
        status=EnrollmentStatus.ACTIVA,
        notes="Inscripción creada automáticamente por asistencia QR en otra clase/horario.",
        created_by_id=student_id,
    )
    db.add(new_row)
    db.flush()
    return new_row


def _group_items(routine: Routine):
    items = list(routine.items or [])
    items.sort(key=lambda it: ((it.day_label or ""), (it.weekday or ""), it.order_index or 0, it.id))

    if routine.routine_type == RoutineType.SEMANAS:
        weeks = defaultdict(list)
        for it in items:
            weeks[it.day_label or "Semana"].append(it)

        groups = []
        for wk_label in sorted(weeks.keys()):
            wk_items = weeks[wk_label]
            by_day = defaultdict(list)
            for it in wk_items:
                by_day[it.weekday or "Día"].append(it)

            subgroups = []
            for day in sorted(by_day.keys(), key=_day_number):
                rows = by_day[day]
                rows.sort(key=lambda it: (it.order_index or 0, it.id))
                subgroups.append({"label": day, "rows": rows})

            groups.append({"label": wk_label, "subgroups": subgroups})
        return {"mode": "SEMANAS", "groups": groups}

    by_day = defaultdict(list)
    for it in items:
        by_day[it.weekday or "Día"].append(it)

    groups = []
    for day in sorted(by_day.keys(), key=_day_number):
        rows = by_day[day]
        rows.sort(key=lambda it: (it.order_index or 0, it.id))
        groups.append({"label": day, "rows": rows})

    return {"mode": "DIAS", "groups": groups}


@router.get("/alumno/rutina", response_class=HTMLResponse)
def alumno_rutina_activa(
    request: Request,
    db: Session = Depends(get_db),
    me=Depends(require_roles(ALUM_ONLY)),
):
    if not _has_present_today(db, me.id):
        return RedirectResponse(url="/alumno/app?need=1", status_code=302)

    stmt = (
        select(RoutineAssignment)
        .where(
            RoutineAssignment.student_id == me.id,
            RoutineAssignment.is_active == True,
        )
        .order_by(RoutineAssignment.created_at.desc())
        .options(
            joinedload(RoutineAssignment.professor),
            selectinload(RoutineAssignment.routine).selectinload(Routine.items).joinedload(RoutineItem.exercise),
        )
    )

    assignment = db.scalars(stmt).first()

    if not assignment:
        return templates.TemplateResponse(
            request,
            "alumno_rutina.html",
            {
                "request": request,
                "me": me,
                "assignment": None,
                "routine": None,
                "view": None,
                "msg": "Todavía no tenés una rutina activa asignada.",
            },
        )

    routine = assignment.routine
    view = _group_items(routine)

    return templates.TemplateResponse(
        request,
        "alumno_rutina.html",
        {
            "request": request,
            "me": me,
            "assignment": assignment,
            "routine": routine,
            "view": view,
            "msg": None,
        },
    )


@router.get("/alumno/membresia", response_class=HTMLResponse)
def alumno_membresia(
    request: Request,
    db: Session = Depends(get_db),
    me=Depends(require_roles(["ALUMNO"])),
):
    period = date.today().strftime("%Y-%m")

    a = db.scalars(
        select(MembershipAssignment)
        .where(
            MembershipAssignment.student_id == me.id,
            MembershipAssignment.is_active == True,
            MembershipAssignment.period_yyyymm == period,
        )
        .order_by(MembershipAssignment.created_at.desc())
        .options(joinedload(MembershipAssignment.membership))
    ).first()

    payments = db.scalars(
        select(CashMovement)
        .where(CashMovement.student_id == me.id)
        .order_by(CashMovement.paid_at.desc(), CashMovement.id.desc())
        .options(
            joinedload(CashMovement.membership_assignment).joinedload(MembershipAssignment.membership),
            joinedload(CashMovement.created_by),
        )
    ).all()

    total_acreditado = sum(
        float(p.amount or 0)
        for p in payments
        if p.status == CashPaymentStatus.ACREDITADO
    )

    if not a:
        return templates.TemplateResponse(
            request,
            "alumno_membresia.html",
            {
                "request": request,
                "me": me,
                "assignment": None,
                "membership": None,
                "period": period,
                "prices": {},
                "payments": payments,
                "total_acreditado": total_acreditado,
            },
        )

    m = a.membership

    prices_rows = db.scalars(
        select(MembershipPrice).where(MembershipPrice.membership_id == m.id)
    ).all()
    prices = {p.payment_method.value: float(p.amount) for p in prices_rows}

    funcional_left = "Libre" if m.funcional_unlimited else max(
        0,
        (m.funcional_classes or 0)
        - (
            db.scalar(
                select(func.count(MembershipUsage.id)).where(
                    MembershipUsage.student_id == me.id,
                    MembershipUsage.period_yyyymm == period,
                    MembershipUsage.service == ServiceKind.FUNCIONAL,
                )
            )
            or 0
        ),
    )

    muscu_left = "Libre" if m.musculacion_unlimited else max(
        0,
        (m.musculacion_classes or 0)
        - (
            db.scalar(
                select(func.count(MembershipUsage.id)).where(
                    MembershipUsage.student_id == me.id,
                    MembershipUsage.period_yyyymm == period,
                    MembershipUsage.service == ServiceKind.MUSCULACION,
                )
            )
            or 0
        ),
    )

    return templates.TemplateResponse(
        request,
        "alumno_membresia.html",
        {
            "request": request,
            "me": me,
            "assignment": a,
            "membership": m,
            "period": period,
            "prices": prices,
            "payments": payments,
            "total_acreditado": total_acreditado,
            "funcional_left": funcional_left,
            "muscu_left": muscu_left,
        },
    )


@router.post("/api/alumno/checkin")
def alumno_checkin(
    qr: str = Form(...),
    db: Session = Depends(get_db),
    me=Depends(require_roles(["ALUMNO"])),
):
    ok, service_str, d_qr = qr_verify_payload(qr)
    if not ok:
        return JSONResponse({"ok": False, "error": "QR inválido."}, status_code=400)

    today = date.today()
    if d_qr != today:
        return JSONResponse({"ok": False, "error": "QR vencido (no corresponde a hoy)."}, status_code=400)

    if today.weekday() == 6:
        return JSONResponse({"ok": False, "error": "Domingo: gimnasio cerrado."}, status_code=400)

    now_t = datetime.now().time()
    t = dtime(now_t.hour, now_t.minute)

    if not (dtime(7, 0) <= t <= dtime(22, 0)):
        return JSONResponse({"ok": False, "error": "Fuera de horario (07:00–22:00)."}, status_code=400)

    period = today.strftime("%Y-%m")
    svc = ServiceKind.FUNCIONAL if service_str == "FUNCIONAL" else ServiceKind.MUSCULACION

    # 1) membresía activa
    a = db.scalars(
        select(MembershipAssignment)
        .where(
            MembershipAssignment.student_id == me.id,
            MembershipAssignment.is_active == True,
            MembershipAssignment.period_yyyymm == period,
        )
        .order_by(MembershipAssignment.created_at.desc())
        .options(joinedload(MembershipAssignment.membership))
    ).first()

    if not a:
        return JSONResponse({"ok": False, "error": f"No tenés membresía activa para {period}."}, status_code=400)

    # 2) el alumno debe tener al menos una inscripción activa en ese servicio
    active_service_enrollments = _student_active_enrollments_for_service(
        db=db,
        student_id=me.id,
        service=svc,
    )
    if not active_service_enrollments:
        return JSONResponse(
            {"ok": False, "error": f"No estás inscripto en ninguna clase activa de {service_str}."},
            status_code=400,
        )

    # 3) ubicar el grupo actual por servicio/día/hora
    current_group = _current_group_for_service_now(
        db=db,
        service=svc,
        target_date=today,
        target_time=t,
    )
    if not current_group:
        return JSONResponse(
            {"ok": False, "error": f"No hay una clase activa de {service_str} en este horario."},
            status_code=400,
        )

    # 4) si estaba en otro grupo/horario del mismo servicio, moverlo al actual
    _move_student_to_current_group_if_needed(
        db=db,
        student_id=me.id,
        service=svc,
        current_group=current_group,
    )

    # 5) evitar doble check-in del mismo servicio el mismo día
    dup = db.scalar(
        select(MembershipUsage.id).where(
            MembershipUsage.student_id == me.id,
            MembershipUsage.used_at == today,
            MembershipUsage.service == svc,
        ).limit(1)
    )
    if dup:
        return JSONResponse({"ok": False, "error": "Ya registraste asistencia hoy para ese servicio."}, status_code=400)

    m = a.membership

    if svc == ServiceKind.FUNCIONAL:
        unlimited = bool(m.funcional_unlimited)
        allowed = None if unlimited else (m.funcional_classes or 0)
    else:
        unlimited = bool(m.musculacion_unlimited)
        allowed = None if unlimited else (m.musculacion_classes or 0)

    used_count = db.scalar(
        select(func.count(MembershipUsage.id)).where(
            MembershipUsage.student_id == me.id,
            MembershipUsage.period_yyyymm == period,
            MembershipUsage.service == svc,
        )
    ) or 0

    # 6) validar saldo
    if not unlimited:
        if allowed <= 0:
            return JSONResponse({"ok": False, "error": "Tu membresía no tiene cupo para este servicio."}, status_code=400)
        if used_count >= allowed:
            return JSONResponse(
                {"ok": False, "error": f"No tenés clases disponibles para {service_str}. Regularizá el mes."},
                status_code=400,
            )

    # 7) registrar uso/presente
    u = MembershipUsage(
        assignment_id=a.id,
        student_id=me.id,
        service=svc,
        used_at=today,
        used_at_time=t,
        period_yyyymm=period,
        notes=f"Check-in QR (alumno) en grupo {current_group.id} - {current_group.gym_class.name}",
        created_by=me.id,
    )
    db.add(u)
    db.commit()

    used_new = used_count + 1
    remaining = "Libre" if unlimited else max(0, allowed - used_new)

    return {
        "ok": True,
        "service": service_str,
        "group_id": current_group.id,
        "group_name": current_group.name or "Grupo",
        "class_name": current_group.gym_class.name,
        "period": period,
        "used": used_new,
        "allowed": (None if unlimited else allowed),
        "remaining": remaining,
    }

@router.get("/alumno/app", response_class=HTMLResponse)
def alumno_app(
    request: Request,
    db: Session = Depends(get_db),
    me=Depends(require_roles(["ALUMNO"])),
):
    today = date.today()
    period = today.strftime("%Y-%m")

    banner = None

    need = request.query_params.get("need")
    if need == "1":
        banner = "📌 Primero tenés que escanear el QR para dar presente. Después se habilita tu rutina."

    a = db.scalars(
        select(MembershipAssignment)
        .where(
            MembershipAssignment.student_id == me.id,
            MembershipAssignment.is_active == True,
            MembershipAssignment.period_yyyymm == period,
        )
        .order_by(MembershipAssignment.created_at.desc())
        .options(joinedload(MembershipAssignment.membership))
    ).first()

    funcional_rem = "-"
    muscu_rem = "-"

    last_day = monthrange(today.year, today.month)[1]
    days_left = last_day - today.day
    if days_left <= 7:
        banner = banner or f"⚠️ Faltan {days_left} días para que termine el mes. Recordá usar tus clases."

    if a:
        m = a.membership

        used_f = db.scalar(
            select(func.count(MembershipUsage.id)).where(
                MembershipUsage.student_id == me.id,
                MembershipUsage.period_yyyymm == period,
                MembershipUsage.service == ServiceKind.FUNCIONAL,
            )
        ) or 0

        used_m = db.scalar(
            select(func.count(MembershipUsage.id)).where(
                MembershipUsage.student_id == me.id,
                MembershipUsage.period_yyyymm == period,
                MembershipUsage.service == ServiceKind.MUSCULACION,
            )
        ) or 0

        if m.funcional_unlimited:
            funcional_rem = "Libre"
        else:
            total_f = m.funcional_classes or 0
            funcional_rem = max(0, total_f - used_f)
            if total_f > 0 and funcional_rem <= 2:
                banner = banner or "⚠️ Te quedan pocas clases de Funcional. Aprovechalas antes de fin de mes."

        if m.musculacion_unlimited:
            muscu_rem = "Libre"
        else:
            total_m = m.musculacion_classes or 0
            muscu_rem = max(0, total_m - used_m)
            if total_m > 0 and muscu_rem <= 2:
                banner = banner or "⚠️ Te quedan pocas clases de Musculación. Aprovechalas antes de fin de mes."

    return templates.TemplateResponse(
        request,
        "alumno_app.html",
        {
            "request": request,
            "me": me,
            "period": period,
            "funcional_rem": funcional_rem,
            "muscu_rem": muscu_rem,
            "banner": banner,
        },
    )