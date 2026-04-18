from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import (
    MembershipAssignment,
    MembershipUsage,
    ProfesorAlumno,
    Role,
    User,
)


@dataclass(slots=True)
class DashboardDateRange:
    date_from: date
    date_to: date


def current_period_yyyymm(today: date | None = None) -> str:
    base = today or date.today()
    return base.strftime("%Y-%m")


def months_between(last_date: date, today: date) -> int:
    return (today.year - last_date.year) * 12 + (today.month - last_date.month)


def add_months(base: date, delta: int) -> date:
    month = base.month - 1 + delta
    year = base.year + month // 12
    month = month % 12 + 1
    day = min(base.day, 28)
    return date(year, month, day)


def month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def month_label(yyyymm: str) -> str:
    y, m = yyyymm.split("-")
    meses = {
        "01": "Ene",
        "02": "Feb",
        "03": "Mar",
        "04": "Abr",
        "05": "May",
        "06": "Jun",
        "07": "Jul",
        "08": "Ago",
        "09": "Sep",
        "10": "Oct",
        "11": "Nov",
        "12": "Dic",
    }
    return f"{meses.get(m, m)} {y}"


def parse_date_or_default(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat((value or "").strip())
    except Exception:
        return fallback


def normalize_date_range(date_from: str, date_to: str, *, today: date | None = None) -> DashboardDateRange:
    current_day = today or date.today()
    default_from = current_day.replace(day=1)
    default_to = current_day

    dt_from = parse_date_or_default(date_from, default_from)
    dt_to = parse_date_or_default(date_to, default_to)

    if dt_from > dt_to:
        dt_from, dt_to = dt_to, dt_from

    return DashboardDateRange(date_from=dt_from, date_to=dt_to)


def load_active_students(db: Session) -> list[User]:
    return db.scalars(
        select(User)
        .where(
            User.role == Role.ALUMNO,
            User.is_active.is_(True),
        )
        .order_by(User.last_name.asc(), User.first_name.asc(), User.email.asc())
    ).all()


def count_presencias_hoy(db: Session, today: date) -> int:
    return db.scalar(
        select(func.count(MembershipUsage.id))
        .where(MembershipUsage.used_at == today)
    ) or 0


def load_usages_in_range(db: Session, date_from: date, date_to: date) -> list[MembershipUsage]:
    return db.scalars(
        select(MembershipUsage)
        .options(joinedload(MembershipUsage.student))
        .where(
            MembershipUsage.used_at >= date_from,
            MembershipUsage.used_at <= date_to,
        )
        .order_by(MembershipUsage.used_at.asc(), MembershipUsage.id.asc())
    ).all()


def load_last_usage_map(db: Session) -> dict[int, date]:
    rows = db.execute(
        select(
            MembershipUsage.student_id,
            func.max(MembershipUsage.used_at).label("last_used_at"),
        )
        .group_by(MembershipUsage.student_id)
    ).all()
    return {row.student_id: row.last_used_at for row in rows}


def build_inactivity_details(
    alumnos: list[User],
    last_usage_map: dict[int, date],
    *,
    today: date,
) -> tuple[dict[str, list[User]], list[dict], int, int]:
    inactivos_bucket = {
        "0": [],
        "1": [],
        "2": [],
        "3": [],
        "4": [],
        "5": [],
        "6+": [],
        "nunca": [],
    }

    detalles_inactivos = []

    for alumno in alumnos:
        last_used = last_usage_map.get(alumno.id)

        if not last_used:
            inactivos_bucket["nunca"].append(alumno)
            detalles_inactivos.append(
                {
                    "alumno": alumno,
                    "last_used_at": None,
                    "months": None,
                    "bucket": "nunca",
                    "severity": "alta",
                }
            )
            continue

        diff = months_between(last_used, today)

        if diff <= 0:
            bucket = "0"
            severity = "ok"
        elif diff == 1:
            bucket = "1"
            severity = "baja"
        elif diff == 2:
            bucket = "2"
            severity = "media"
        elif diff == 3:
            bucket = "3"
            severity = "media"
        elif diff == 4:
            bucket = "4"
            severity = "alta"
        elif diff == 5:
            bucket = "5"
            severity = "alta"
        else:
            bucket = "6+"
            severity = "critica"

        inactivos_bucket[bucket].append(alumno)
        detalles_inactivos.append(
            {
                "alumno": alumno,
                "last_used_at": last_used,
                "months": diff,
                "bucket": bucket,
                "severity": severity,
            }
        )

    activos_recientes = len(inactivos_bucket["0"])
    total_inactivos = sum(len(v) for k, v in inactivos_bucket.items() if k != "0")

    return inactivos_bucket, detalles_inactivos, activos_recientes, total_inactivos


def load_latest_active_assignment_by_student(db: Session) -> dict[int, MembershipAssignment]:
    assignments = db.scalars(
        select(MembershipAssignment)
        .where(MembershipAssignment.is_active.is_(True))
        .options(
            joinedload(MembershipAssignment.membership),
            joinedload(MembershipAssignment.student),
        )
        .order_by(MembershipAssignment.student_id.asc(), MembershipAssignment.id.desc())
    ).all()

    latest_assignment_by_student: dict[int, MembershipAssignment] = {}

    for assignment in assignments:
        prev = latest_assignment_by_student.get(assignment.student_id)
        if prev is None:
            latest_assignment_by_student[assignment.student_id] = assignment
            continue

        prev_period = (prev.period_yyyymm or "").strip()
        new_period = (assignment.period_yyyymm or "").strip()

        if new_period > prev_period:
            latest_assignment_by_student[assignment.student_id] = assignment
        elif new_period == prev_period and assignment.id > prev.id:
            latest_assignment_by_student[assignment.student_id] = assignment

    return latest_assignment_by_student


def build_membership_status(
    alumnos: list[User],
    latest_assignment_by_student: dict[int, MembershipAssignment],
    *,
    current_period: str,
    today: date,
) -> tuple[list[dict], list[dict]]:
    cuotas_vencidas = []
    cuotas_al_dia = []

    for alumno in alumnos:
        ass = latest_assignment_by_student.get(alumno.id)

        if not ass:
            cuotas_vencidas.append(
                {
                    "alumno": alumno,
                    "motivo": "Sin membresía activa asignada",
                    "periodo": "-",
                    "membership_name": "-",
                    "severity": "alta",
                }
            )
            continue

        ass_period = (ass.period_yyyymm or "").strip()
        membership_name = ass.membership.name if ass.membership else "-"

        if not ass_period:
            cuotas_vencidas.append(
                {
                    "alumno": alumno,
                    "motivo": "Asignación sin período",
                    "periodo": "-",
                    "membership_name": membership_name,
                    "severity": "alta",
                }
            )
            continue

        if ass_period < current_period:
            year_str, month_str = ass_period.split("-")
            diff_months = (today.year - int(year_str)) * 12 + (today.month - int(month_str))
            severity = "media" if diff_months == 1 else "alta"
            cuotas_vencidas.append(
                {
                    "alumno": alumno,
                    "motivo": "Período vencido",
                    "periodo": ass_period,
                    "membership_name": membership_name,
                    "severity": severity,
                }
            )
        else:
            cuotas_al_dia.append(
                {
                    "alumno": alumno,
                    "periodo": ass_period,
                    "membership_name": membership_name,
                }
            )

    return cuotas_vencidas, cuotas_al_dia


def load_latest_presencias(db: Session, limit: int = 12) -> list[MembershipUsage]:
    return db.scalars(
        select(MembershipUsage)
        .options(joinedload(MembershipUsage.student))
        .order_by(MembershipUsage.created_at.desc(), MembershipUsage.id.desc())
        .limit(limit)
    ).all()


def build_presence_breakdowns(usages_rango: list[MembershipUsage], date_from: date, date_to: date):
    per_day_counter = Counter()
    service_counter = Counter()
    hour_counter = Counter()

    for usage in usages_rango:
        per_day_counter[usage.used_at.isoformat()] += 1
        service_value = usage.service.value if hasattr(usage.service, "value") else str(usage.service)
        service_counter[service_value] += 1
        if usage.used_at_time:
            hour_counter[usage.used_at_time.strftime("%H:%M")] += 1

    presencias_por_dia = []
    day_cursor = date_from
    while day_cursor <= date_to:
        key = day_cursor.isoformat()
        presencias_por_dia.append(
            {
                "day": day_cursor.strftime("%d/%m"),
                "count": per_day_counter.get(key, 0),
            }
        )
        day_cursor += timedelta(days=1)

    servicios = [
        {"label": "FUNCIONAL", "count": service_counter.get("FUNCIONAL", 0)},
        {"label": "MUSCULACION", "count": service_counter.get("MUSCULACION", 0)},
    ]

    horarios_top = sorted(
        [{"hour": hour, "count": count} for hour, count in hour_counter.items()],
        key=lambda x: (-x["count"], x["hour"]),
    )[:10]

    return presencias_por_dia, servicios, horarios_top


def load_monthly_comparison(db: Session, today: date) -> list[dict]:
    base_month = date(today.year, today.month, 1)
    months = [add_months(base_month, delta) for delta in range(-5, 1)]
    month_keys = [month_key(m) for m in months]

    monthly_counts = db.execute(
        select(
            MembershipUsage.period_yyyymm,
            func.count(MembershipUsage.id),
        )
        .where(MembershipUsage.period_yyyymm.in_(month_keys))
        .group_by(MembershipUsage.period_yyyymm)
    ).all()

    monthly_map = {row[0]: row[1] for row in monthly_counts}

    return [
        {
            "period": mk,
            "label": month_label(mk),
            "count": int(monthly_map.get(mk, 0)),
        }
        for mk in month_keys
    ]


def load_profesores_top(db: Session, usages_rango: list[MembershipUsage], limit: int = 10) -> list[dict]:
    profesor_alumno_rows = db.execute(
        select(ProfesorAlumno.profesor_id, ProfesorAlumno.alumno_id)
    ).all()

    alumno_to_profesores = defaultdict(list)
    for profesor_id, alumno_id in profesor_alumno_rows:
        alumno_to_profesores[alumno_id].append(profesor_id)

    profesor_counter = Counter()
    for usage in usages_rango:
        for profesor_id in alumno_to_profesores.get(usage.student_id, []):
            profesor_counter[profesor_id] += 1

    profesores = db.scalars(
        select(User).where(User.role == Role.PROFESOR)
    ).all()
    profesor_map = {prof.id: prof for prof in profesores}

    profesores_top = []
    for profesor_id, count in profesor_counter.most_common(limit):
        prof = profesor_map.get(profesor_id)
        if prof:
            profesores_top.append(
                {
                    "profesor": prof,
                    "count": count,
                }
            )

    return profesores_top


def load_alumnos_nuevos_mes(db: Session, today: date) -> list[User]:
    first_day_month = date(today.year, today.month, 1)

    return db.scalars(
        select(User)
        .where(
            User.role == Role.ALUMNO,
            User.is_active.is_(True),
            User.created_at >= datetime.combine(first_day_month, datetime.min.time()),
        )
        .order_by(User.created_at.desc())
    ).all()


def build_alertas(
    *,
    cuotas_vencidas: list[dict],
    inactivos_bucket: dict[str, list[User]],
    alumnos_nuevos_mes: list[User],
) -> tuple[dict, list[dict]]:
    activos_recientes = len(inactivos_bucket["0"])

    seguimiento = {
        "total_contactar": len(cuotas_vencidas) + len(inactivos_bucket["6+"]) + len(inactivos_bucket["nunca"]),
        "morosos_alta": len([row for row in cuotas_vencidas if row["severity"] == "alta"]),
        "inactivos_criticos": len(inactivos_bucket["6+"]) + len(inactivos_bucket["nunca"]),
        "alumnos_nuevos_mes": len(alumnos_nuevos_mes),
        "activos_recientes": activos_recientes,
    }

    alertas = []

    if seguimiento["morosos_alta"] > 0:
        alertas.append(
            {
                "title": "Morosidad alta",
                "text": f'{seguimiento["morosos_alta"]} alumnos con deuda prioritaria.',
                "level": "alta",
                "href": "/admin/home/morosos",
            }
        )

    if seguimiento["inactivos_criticos"] > 0:
        alertas.append(
            {
                "title": "Inactividad crítica",
                "text": f'{seguimiento["inactivos_criticos"]} alumnos sin venir hace 6+ meses o nunca.',
                "level": "alta",
                "href": "/admin/home/inactivos?bucket=6+",
            }
        )

    if len(alumnos_nuevos_mes) > 0:
        alertas.append(
            {
                "title": "Alumnos nuevos",
                "text": f'{len(alumnos_nuevos_mes)} alumnos nuevos este mes.',
                "level": "info",
                "href": "/admin/users",
            }
        )

    return seguimiento, alertas


def build_dashboard_data(db: Session, date_from: date, date_to: date) -> dict:
    today = date.today()
    current_period = current_period_yyyymm(today=today)

    alumnos = load_active_students(db)
    presencias_hoy = count_presencias_hoy(db, today)
    usages_rango = load_usages_in_range(db, date_from, date_to)
    last_usage_map = load_last_usage_map(db)

    inactivos_bucket, detalles_inactivos, activos_recientes, total_inactivos = build_inactivity_details(
        alumnos,
        last_usage_map,
        today=today,
    )

    latest_assignment_by_student = load_latest_active_assignment_by_student(db)
    cuotas_vencidas, cuotas_al_dia = build_membership_status(
        alumnos,
        latest_assignment_by_student,
        current_period=current_period,
        today=today,
    )

    ultimas_presencias = load_latest_presencias(db, limit=12)
    presencias_por_dia, servicios, horarios_top = build_presence_breakdowns(usages_rango, date_from, date_to)
    comparativo_mensual = load_monthly_comparison(db, today)
    profesores_top = load_profesores_top(db, usages_rango, limit=10)
    alumnos_nuevos_mes = load_alumnos_nuevos_mes(db, today)
    seguimiento, alertas = build_alertas(
        cuotas_vencidas=cuotas_vencidas,
        inactivos_bucket=inactivos_bucket,
        alumnos_nuevos_mes=alumnos_nuevos_mes,
    )

    return {
        "today": today,
        "period": current_period,
        "date_from": date_from,
        "date_to": date_to,
        "total_alumnos": len(alumnos),
        "presencias_hoy": presencias_hoy,
        "presencias_rango": len(usages_rango),
        "activos_recientes": activos_recientes,
        "total_inactivos": total_inactivos,
        "inactivos_bucket": inactivos_bucket,
        "detalles_inactivos": detalles_inactivos,
        "cuotas_vencidas": cuotas_vencidas,
        "cuotas_vencidas_count": len(cuotas_vencidas),
        "cuotas_al_dia_count": len(cuotas_al_dia),
        "ultimas_presencias": ultimas_presencias,
        "presencias_por_dia": presencias_por_dia,
        "servicios": servicios,
        "horarios_top": horarios_top,
        "comparativo_mensual": comparativo_mensual,
        "profesores_top": profesores_top,
        "alumnos_nuevos_mes": alumnos_nuevos_mes,
        "seguimiento": seguimiento,
        "alertas": alertas,
    }


def build_inactivos_rows(db: Session, *, today: date | None = None, bucket: str = "") -> dict:
    current_day = today or date.today()
    alumnos = load_active_students(db)
    last_usage_map = load_last_usage_map(db)

    _, detalles_inactivos, _, _ = build_inactivity_details(
        alumnos,
        last_usage_map,
        today=current_day,
    )

    rows = detalles_inactivos
    if bucket:
        rows = [row for row in rows if row["bucket"] == bucket]

    rows = sorted(
        rows,
        key=lambda row: (
            -999 if row["months"] is None else -row["months"],
            (row["alumno"].last_name or ""),
            (row["alumno"].first_name or ""),
            (row["alumno"].email or ""),
        ),
    )

    return {
        "rows": rows,
        "bucket": bucket,
        "period": current_period_yyyymm(today=current_day),
    }


def build_morosos_rows(db: Session, *, today: date | None = None) -> dict:
    current_day = today or date.today()
    alumnos = load_active_students(db)
    latest_assignment_by_student = load_latest_active_assignment_by_student(db)
    cuotas_vencidas, _ = build_membership_status(
        alumnos,
        latest_assignment_by_student,
        current_period=current_period_yyyymm(today=current_day),
        today=current_day,
    )

    return {
        "rows": cuotas_vencidas,
        "period": current_period_yyyymm(today=current_day),
    }