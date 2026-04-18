from __future__ import annotations

from datetime import date, timedelta
from app.utils.datetime_utils import utcnow_naive
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..models import (
    User,
    StudentFollowup,
    FollowupKind,
    FollowupStatus,
    FollowupPriority,
    FollowupChannel,
    FollowupAction,
    FollowupActionType,
)
from ..services.followup_helpers import (
    infer_priority,
    status_group_title,
    build_followup_message,
    whatsapp_url,
    email_url,
    serialize_followup_for_actions,
)
from ..services.followup_ops import (
    append_followup_action,
    safe_kind,
    safe_priority,
    safe_status,
)
from ..utils.pagination import page_meta


def get_followup_or_none(db: Session, followup_id: int) -> StudentFollowup | None:
    return db.get(StudentFollowup, followup_id)


def get_followup_or_404(db: Session, followup_id: int) -> StudentFollowup:
    row = db.get(StudentFollowup, followup_id)
    if not row:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")
    return row


def get_student_or_none(db: Session, student_id: int) -> User | None:
    return db.get(User, student_id)


def build_row_actions_map(db: Session, rows: list[StudentFollowup]) -> dict[int, dict[str, Any]]:
    row_actions: dict[int, dict[str, Any]] = {}
    for row in rows:
        row_actions[row.id] = serialize_followup_for_actions(db, row)
    return row_actions


def _followups_base_stmt(
    *,
    q: str = "",
    kind: str = "",
    status: str = "",
    priority: str = "",
):
    stmt = select(StudentFollowup)

    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.join(User, StudentFollowup.student_id == User.id).where(
            or_(
                User.full_name.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
                User.dni.ilike(like),
                StudentFollowup.title.ilike(like),
                StudentFollowup.notes.ilike(like),
                StudentFollowup.result_summary.ilike(like),
            )
        )

    kind_enum = safe_kind(kind)
    if kind_enum:
        stmt = stmt.where(StudentFollowup.kind == kind_enum)

    status_enum = safe_status(status)
    if status_enum:
        stmt = stmt.where(StudentFollowup.status == status_enum)

    priority_enum = safe_priority(priority)
    if priority_enum:
        stmt = stmt.where(StudentFollowup.priority == priority_enum)

    return stmt


def list_followups(
    db: Session,
    *,
    q: str = "",
    kind: str = "",
    status: str = "",
    priority: str = "",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    base_stmt = _followups_base_stmt(q=q, kind=kind, status=status, priority=priority)

    total = db.scalar(
        select(func.count()).select_from(base_stmt.order_by(None).subquery())
    ) or 0

    pagination = page_meta(total=total, page=page, page_size=page_size)

    rows = db.scalars(
        base_stmt
        .options(
            joinedload(StudentFollowup.student),
            joinedload(StudentFollowup.created_by),
        )
        .order_by(StudentFollowup.created_at.desc(), StudentFollowup.id.desc())
        .offset(pagination["offset"])
        .limit(pagination["page_size"])
    ).all()

    return {
        "rows": rows,
        "row_actions": build_row_actions_map(db, rows),
        "pagination": pagination,
    }


def get_dashboard_data(db: Session) -> dict[str, Any]:
    counts_rows = db.execute(
        select(
            StudentFollowup.kind,
            StudentFollowup.status,
            func.count(StudentFollowup.id),
        )
        .group_by(StudentFollowup.kind, StudentFollowup.status)
    ).all()

    totals_by_status = {
        FollowupStatus.PENDIENTE.value: 0,
        FollowupStatus.CONTACTADO.value: 0,
        FollowupStatus.RESPONDIO.value: 0,
        FollowupStatus.REACTIVADO.value: 0,
        FollowupStatus.DESCARTADO.value: 0,
    }

    by_kind: dict[str, dict[str, int]] = {
        kind.value: {
            "total": 0,
            "reactivados": 0,
            "descartados": 0,
            "respondidos": 0,
        }
        for kind in FollowupKind
    }

    total = 0

    for kind, status, count in counts_rows:
        k = kind.value
        s = status.value
        c = int(count or 0)

        total += c
        totals_by_status[s] += c

        by_kind[k]["total"] += c
        if s == FollowupStatus.REACTIVADO.value:
            by_kind[k]["reactivados"] += c
            by_kind[k]["respondidos"] += c
        elif s == FollowupStatus.DESCARTADO.value:
            by_kind[k]["descartados"] += c
            by_kind[k]["respondidos"] += c
        elif s == FollowupStatus.RESPONDIO.value:
            by_kind[k]["respondidos"] += c

    pendientes = totals_by_status[FollowupStatus.PENDIENTE.value]
    contactados = totals_by_status[FollowupStatus.CONTACTADO.value]
    respondidos = totals_by_status[FollowupStatus.RESPONDIO.value]
    reactivados = totals_by_status[FollowupStatus.REACTIVADO.value]
    descartados = totals_by_status[FollowupStatus.DESCARTADO.value]

    tasa_respuesta = round((respondidos + reactivados + descartados) * 100 / total, 1) if total else 0
    tasa_reactivacion = round(reactivados * 100 / total, 1) if total else 0
    tasa_conversion_sobre_respondidos = round(
        reactivados * 100 / max(1, (respondidos + reactivados + descartados)),
        1,
    )

    recent_reactivated = db.scalars(
        select(StudentFollowup)
        .where(StudentFollowup.status == FollowupStatus.REACTIVADO)
        .options(joinedload(StudentFollowup.student))
        .order_by(StudentFollowup.updated_at.desc(), StudentFollowup.id.desc())
        .limit(10)
    ).all()

    recent_negative = db.scalars(
        select(StudentFollowup)
        .where(StudentFollowup.status == FollowupStatus.DESCARTADO)
        .options(joinedload(StudentFollowup.student))
        .order_by(StudentFollowup.updated_at.desc(), StudentFollowup.id.desc())
        .limit(10)
    ).all()

    return {
        "total": total,
        "pendientes": pendientes,
        "contactados": contactados,
        "respondidos": respondidos,
        "reactivados": reactivados,
        "descartados": descartados,
        "tasa_respuesta": tasa_respuesta,
        "tasa_reactivacion": tasa_reactivacion,
        "tasa_conversion_sobre_respondidos": tasa_conversion_sobre_respondidos,
        "by_kind": by_kind,
        "recent_reactivated": recent_reactivated,
        "recent_negative": recent_negative,
    }


def get_automation_data(db: Session) -> dict[str, Any]:
    cutoff = utcnow_naive() - timedelta(days=3)

    rows = db.scalars(
        select(StudentFollowup)
        .where(StudentFollowup.status == FollowupStatus.CONTACTADO)
        .options(joinedload(StudentFollowup.student))
        .order_by(StudentFollowup.id.desc())
        .limit(100)
    ).all()

    candidates_no_response = db.scalars(
        select(StudentFollowup)
        .where(
            StudentFollowup.status == FollowupStatus.CONTACTADO,
            StudentFollowup.contacted_at.is_not(None),
            StudentFollowup.contacted_at <= cutoff,
            StudentFollowup.automation_enabled == True,
        )
        .options(joinedload(StudentFollowup.student))
        .order_by(StudentFollowup.contacted_at.asc(), StudentFollowup.id.desc())
        .limit(100)
    ).all()

    return {
        "rows": rows,
        "candidates_no_response": candidates_no_response,
    }


def _inbox_base_stmt(
    *,
    q: str = "",
):
    stmt = (
        select(FollowupAction)
        .join(StudentFollowup, FollowupAction.followup_id == StudentFollowup.id)
        .join(User, StudentFollowup.student_id == User.id)
        .where(
            or_(
                FollowupAction.summary.ilike("%Respuesta recibida%"),
                FollowupAction.summary.ilike("%Respuesta positiva%"),
                FollowupAction.summary.ilike("%Respuesta negativa%"),
                FollowupAction.summary.ilike("%Regla automática:%"),
            )
        )
    )

    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.full_name.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
                User.phone.ilike(like),
                FollowupAction.payload_text.ilike(like),
                FollowupAction.summary.ilike(like),
                StudentFollowup.title.ilike(like),
                StudentFollowup.result_summary.ilike(like),
            )
        )

    return stmt


def list_inbox_actions(
    db: Session,
    *,
    q: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    base_stmt = _inbox_base_stmt(q=q)

    status_enum = safe_status(status)
    if status_enum:
        base_stmt = base_stmt.where(StudentFollowup.status == status_enum)

    total = db.scalar(
        select(func.count()).select_from(base_stmt.order_by(None).subquery())
    ) or 0

    pagination = page_meta(total=total, page=page, page_size=page_size)

    actions = db.scalars(
        base_stmt
        .options(
            joinedload(FollowupAction.created_by),
            joinedload(FollowupAction.followup),
        )
        .order_by(FollowupAction.created_at.desc(), FollowupAction.id.desc())
        .offset(pagination["offset"])
        .limit(pagination["page_size"])
    ).all()

    followup_ids = list({a.followup_id for a in actions}) or [-1]
    followups = db.scalars(
        select(StudentFollowup)
        .where(StudentFollowup.id.in_(followup_ids))
        .options(joinedload(StudentFollowup.student))
    ).all()
    followup_map = {f.id: f for f in followups}

    return {
        "actions": actions,
        "followup_map": followup_map,
        "statuses": [
            FollowupStatus.RESPONDIO.value,
            FollowupStatus.REACTIVADO.value,
            FollowupStatus.DESCARTADO.value,
        ],
        "pagination": pagination,
    }


def get_agenda_data(db: Session) -> dict[str, Any]:
    today = date.today()
    week_end = today + timedelta(days=7)

    common_options = (
        joinedload(StudentFollowup.student),
        joinedload(StudentFollowup.created_by),
    )

    vencidos = db.scalars(
        select(StudentFollowup)
        .where(
            StudentFollowup.next_contact_date.is_not(None),
            StudentFollowup.next_contact_date < today,
        )
        .options(*common_options)
        .order_by(StudentFollowup.next_contact_date.asc(), StudentFollowup.id.desc())
        .limit(200)
    ).all()

    hoy_rows = db.scalars(
        select(StudentFollowup)
        .where(StudentFollowup.next_contact_date == today)
        .options(*common_options)
        .order_by(StudentFollowup.id.desc())
        .limit(200)
    ).all()

    semana = db.scalars(
        select(StudentFollowup)
        .where(
            StudentFollowup.next_contact_date > today,
            StudentFollowup.next_contact_date <= week_end,
        )
        .options(*common_options)
        .order_by(StudentFollowup.next_contact_date.asc(), StudentFollowup.id.desc())
        .limit(300)
    ).all()

    sin_fecha = db.scalars(
        select(StudentFollowup)
        .where(StudentFollowup.next_contact_date.is_(None))
        .options(*common_options)
        .order_by(StudentFollowup.id.desc())
        .limit(200)
    ).all()

    rows_for_actions = []
    for group in (vencidos, hoy_rows, semana, sin_fecha):
        rows_for_actions.extend(group)

    unique_rows = list({row.id: row for row in rows_for_actions}.values())

    return {
        "today": today,
        "vencidos": vencidos,
        "hoy_rows": hoy_rows,
        "semana": semana,
        "sin_fecha": sin_fecha,
        "row_actions": build_row_actions_map(db, unique_rows),
    }


def get_kanban_data(db: Session) -> dict[str, Any]:
    counts = db.execute(
        select(
            StudentFollowup.status,
            func.count(StudentFollowup.id),
        )
        .group_by(StudentFollowup.status)
    ).all()

    totals_by_status = {s.value: 0 for s in FollowupStatus}
    for status, count in counts:
        totals_by_status[status.value] = int(count or 0)

    common_options = (
        joinedload(StudentFollowup.student),
        joinedload(StudentFollowup.created_by),
    )

    columns = {}
    rows_for_actions = []

    for status in FollowupStatus:
        rows = db.scalars(
            select(StudentFollowup)
            .where(StudentFollowup.status == status)
            .options(*common_options)
            .order_by(
                case(
                    (StudentFollowup.next_contact_date.is_(None), 1),
                    else_=0,
                ).asc(),
                StudentFollowup.next_contact_date.asc(),
                StudentFollowup.created_at.desc(),
                StudentFollowup.id.desc(),
            )
            .limit(100)
        ).all()
        columns[status.value] = rows
        rows_for_actions.extend(rows)

    unique_rows = list({row.id: row for row in rows_for_actions}.values())

    return {
        "columns": columns,
        "row_actions": build_row_actions_map(db, unique_rows),
        "status_titles": {s.value: status_group_title(s.value) for s in FollowupStatus},
        "status_totals": totals_by_status,
        "today": date.today(),
    }


def get_reminders_data(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    today = date.today()

    base_stmt = (
        select(StudentFollowup)
        .where(
            StudentFollowup.automation_enabled == True,
            StudentFollowup.next_contact_date.is_not(None),
            StudentFollowup.status.in_([
                FollowupStatus.PENDIENTE,
                FollowupStatus.CONTACTADO,
                FollowupStatus.RESPONDIO,
            ]),
        )
    )

    total = db.scalar(
        select(func.count()).select_from(base_stmt.order_by(None).subquery())
    ) or 0

    pagination = page_meta(total=total, page=page, page_size=page_size)

    rows = db.scalars(
        base_stmt
        .options(joinedload(StudentFollowup.student))
        .order_by(StudentFollowup.next_contact_date.asc(), StudentFollowup.id.desc())
        .offset(pagination["offset"])
        .limit(pagination["page_size"])
    ).all()

    return {
        "today": today,
        "rows": rows,
        "pagination": pagination,
    }


def mark_reminder_sent_service(db: Session, *, followup_id: int, me: User) -> bool:
    row = db.get(StudentFollowup, followup_id)
    if not row:
        return False

    try:
        row.reminder_sent_at = utcnow_naive()

        append_followup_action(
            db,
            row=row,
            me=me,
            action_type=FollowupActionType.RECORDATORIO,
            channel=row.channel,
            summary="Recordatorio marcado como enviado",
        )

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def get_new_followup_page_data(
    db: Session,
    *,
    student_id: int,
    kind: str,
) -> dict[str, Any] | None:
    student = db.get(User, student_id)
    if not student:
        return None

    subject, suggested_message = build_followup_message(
        db,
        student,
        row=None,
        kind_value=kind,
        channel_value="WHATSAPP",
    )

    return {
        "student": student,
        "kind_default": kind,
        "statuses": [s.value for s in FollowupStatus],
        "kinds": [k.value for k in FollowupKind],
        "channels": [c.value for c in FollowupChannel],
        "suggested_message": suggested_message,
        "suggested_whatsapp_url": whatsapp_url(student, suggested_message),
        "suggested_email_url": email_url(student, subject, suggested_message),
        "error": "",
    }


def create_followup(
    db: Session,
    *,
    student_id: int,
    kind: str,
    status: str,
    channel: str,
    title: str,
    notes: str,
    next_contact_date: str,
    me: User,
) -> StudentFollowup | None:
    student = db.get(User, student_id)
    if not student:
        return None

    kind_enum = FollowupKind(kind)
    status_enum = FollowupStatus(status)
    channel_enum = FollowupChannel(channel)

    next_date = None
    if next_contact_date.strip():
        try:
            next_date = date.fromisoformat(next_contact_date.strip())
        except Exception:
            next_date = None

    priority_enum = infer_priority(kind, status, next_date)

    try:
        row = StudentFollowup(
            student_id=student.id,
            created_by_id=me.id,
            kind=kind_enum,
            status=status_enum,
            priority=priority_enum,
            channel=channel_enum,
            title=(title or "").strip(),
            notes=(notes or "").strip(),
            next_contact_date=next_date,
            automation_enabled=True,
        )
        db.add(row)
        db.flush()

        append_followup_action(
            db,
            row=row,
            me=me,
            action_type=FollowupActionType.NOTA,
            channel=channel_enum,
            summary="Seguimiento creado",
            payload_text=row.notes,
        )

        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise


def get_followup_edit_page_data(db: Session, *, followup_id: int) -> dict[str, Any] | None:
    row = db.get(StudentFollowup, followup_id)
    if not row:
        return None

    student = db.get(User, row.student_id)
    if not student:
        return None

    subject, suggested_message = build_followup_message(
        db,
        student,
        row=row,
        channel_value=row.channel.value,
    )

    return {
        "row": row,
        "student": student,
        "statuses": [s.value for s in FollowupStatus],
        "kinds": [k.value for k in FollowupKind],
        "priorities": [p.value for p in FollowupPriority],
        "channels": [c.value for c in FollowupChannel],
        "suggested_message": suggested_message,
        "suggested_whatsapp_url": whatsapp_url(student, suggested_message),
        "suggested_email_url": email_url(student, subject, suggested_message),
    }


def update_followup(
    db: Session,
    *,
    followup_id: int,
    kind: str,
    status: str,
    priority: str,
    channel: str,
    title: str,
    notes: str,
    next_contact_date: str,
    result_summary: str,
    automation_enabled: str,
    me: User,
) -> bool:
    row = db.get(StudentFollowup, followup_id)
    if not row:
        return False

    prev_status = row.status.value

    try:
        row.kind = FollowupKind(kind)
        row.status = FollowupStatus(status)
        row.channel = FollowupChannel(channel)
        row.title = (title or "").strip()
        row.notes = (notes or "").strip()
        row.result_summary = (result_summary or "").strip()
        row.automation_enabled = automation_enabled == "1"

        if next_contact_date.strip():
            try:
                row.next_contact_date = date.fromisoformat(next_contact_date.strip())
            except Exception:
                row.next_contact_date = None
        else:
            row.next_contact_date = None

        if priority.strip():
            row.priority = FollowupPriority(priority)
        else:
            row.priority = infer_priority(kind, status, row.next_contact_date)

        if row.status == FollowupStatus.CONTACTADO and row.contacted_at is None:
            row.contacted_at = utcnow_naive()

        if row.status in [FollowupStatus.REACTIVADO, FollowupStatus.DESCARTADO]:
            if row.resolved_at is None:
                row.resolved_at = utcnow_naive()
        else:
            row.resolved_at = None

        if prev_status != row.status.value:
            append_followup_action(
                db,
                row=row,
                me=me,
                action_type=FollowupActionType.CAMBIO_ESTADO,
                channel=row.channel,
                summary=f"Estado cambiado de {prev_status} a {row.status.value}",
                payload_text=row.result_summary,
            )

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def mark_channel_sent_service(
    db: Session,
    *,
    followup_id: int,
    channel: str,
    me: User,
) -> bool:
    row = db.get(StudentFollowup, followup_id)
    if not row:
        return False

    student = db.get(User, row.student_id)

    try:
        row.status = FollowupStatus.CONTACTADO
        if row.contacted_at is None:
            row.contacted_at = utcnow_naive()

        subject = ""
        msg = ""

        if student:
            subject, msg = build_followup_message(
                db,
                student,
                row=row,
                channel_value=channel,
            )

        if channel == "WHATSAPP":
            append_followup_action(
                db,
                row=row,
                me=me,
                action_type=FollowupActionType.WHATSAPP_ENVIADO,
                channel=FollowupChannel.WHATSAPP,
                summary="WhatsApp marcado como enviado",
                payload_text=msg,
            )
        else:
            append_followup_action(
                db,
                row=row,
                me=me,
                action_type=FollowupActionType.EMAIL_ENVIADO,
                channel=FollowupChannel.EMAIL,
                summary=f"Email marcado como enviado: {subject}" if subject else "Email marcado como enviado",
                payload_text=msg,
            )

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def get_followups_by_student_data(db: Session, *, student_id: int) -> dict[str, Any] | None:
    student = db.get(User, student_id)
    if not student:
        return None

    rows = db.scalars(
        select(StudentFollowup)
        .where(StudentFollowup.student_id == student.id)
        .options(joinedload(StudentFollowup.created_by))
        .order_by(StudentFollowup.created_at.desc(), StudentFollowup.id.desc())
    ).all()

    row_actions = {}
    for row in rows:
        row.student = student
        row_actions[row.id] = serialize_followup_for_actions(db, row)

    return {
        "student": student,
        "rows": rows,
        "row_actions": row_actions,
    }


def get_actions_by_student_data(db: Session, *, student_id: int) -> dict[str, Any] | None:
    student = db.get(User, student_id)
    if not student:
        return None

    followups = db.scalars(
        select(StudentFollowup)
        .where(StudentFollowup.student_id == student.id)
        .order_by(StudentFollowup.created_at.desc())
    ).all()

    followup_ids = [f.id for f in followups] or [-1]

    actions = db.scalars(
        select(FollowupAction)
        .where(FollowupAction.followup_id.in_(followup_ids))
        .options(joinedload(FollowupAction.created_by))
        .order_by(FollowupAction.created_at.desc(), FollowupAction.id.desc())
    ).all()

    followup_map = {f.id: f for f in followups}

    return {
        "student": student,
        "followups": followups,
        "actions": actions,
        "followup_map": followup_map,
    }