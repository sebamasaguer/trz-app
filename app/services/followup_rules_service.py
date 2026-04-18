from __future__ import annotations

from datetime import date, timedelta
from app.utils.datetime_utils import utcnow_naive

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import (
    User,
    StudentFollowup,
    FollowupKind,
    FollowupStatus,
    FollowupPriority,
    FollowupChannel,
    FollowupActionType,
)
from .followup_helpers import infer_priority
from .followup_message_service import send_via_n8n
from .followup_ops import append_followup_action

logger = logging.getLogger(__name__)


def _already_processed_recently(
    row: StudentFollowup,
    *,
    seconds: int = 90,
) -> bool:
    if not row.last_action_at:
        return False
    return row.last_action_at >= utcnow_naive() - timedelta(seconds=seconds)


def _eligible_morosity_rows(db: Session) -> list[StudentFollowup]:
    return db.scalars(
        select(StudentFollowup)
        .where(
            StudentFollowup.kind == FollowupKind.MOROSIDAD,
            StudentFollowup.status.in_([
                FollowupStatus.PENDIENTE,
                FollowupStatus.CONTACTADO,
                FollowupStatus.RESPONDIO,
            ]),
            StudentFollowup.automation_enabled == True,
        )
        .options(joinedload(StudentFollowup.student))
        .order_by(
            StudentFollowup.priority.desc(),
            StudentFollowup.next_contact_date.asc().nulls_last(),
            StudentFollowup.id.desc(),
        )
        .limit(300)
    ).all()


def _eligible_inactivity_rows(db: Session) -> list[StudentFollowup]:
    return db.scalars(
        select(StudentFollowup)
        .where(
            StudentFollowup.kind == FollowupKind.INACTIVIDAD,
            StudentFollowup.status.in_([
                FollowupStatus.PENDIENTE,
                FollowupStatus.CONTACTADO,
                FollowupStatus.RESPONDIO,
            ]),
            StudentFollowup.automation_enabled == True,
        )
        .options(joinedload(StudentFollowup.student))
        .order_by(
            StudentFollowup.priority.desc(),
            StudentFollowup.next_contact_date.asc().nulls_last(),
            StudentFollowup.id.desc(),
        )
        .limit(300)
    ).all()


def _eligible_general_rows(db: Session) -> list[StudentFollowup]:
    today = date.today()
    return db.scalars(
        select(StudentFollowup)
        .where(
            StudentFollowup.kind == FollowupKind.GENERAL,
            StudentFollowup.status.in_([
                FollowupStatus.PENDIENTE,
                FollowupStatus.CONTACTADO,
                FollowupStatus.RESPONDIO,
            ]),
            StudentFollowup.automation_enabled == True,
            StudentFollowup.next_contact_date.is_not(None),
            StudentFollowup.next_contact_date <= today,
        )
        .options(joinedload(StudentFollowup.student))
        .order_by(
            StudentFollowup.priority.desc(),
            StudentFollowup.next_contact_date.asc(),
            StudentFollowup.id.desc(),
        )
        .limit(300)
    ).all()


def _mark_rule_evaluated(
    db: Session,
    *,
    row: StudentFollowup,
    me: User,
    summary: str,
):
    append_followup_action(
        db,
        row=row,
        me=me,
        action_type=FollowupActionType.NOTA,
        channel=row.channel,
        summary=summary,
        delivery_status="RULE_EVALUATED",
    )


def _process_single_row(
    db: Session,
    *,
    row: StudentFollowup,
    me: User,
) -> dict:
    if not row.student:
        return {
            "followup_id": row.id,
            "ok": False,
            "reason": "sin_alumno",
        }

    if row.outbound_in_progress:
        return {
            "followup_id": row.id,
            "ok": True,
            "skipped": True,
            "reason": "outbound_in_progress",
        }

    if _already_processed_recently(row, seconds=90):
        return {
            "followup_id": row.id,
            "ok": True,
            "skipped": True,
            "reason": "processed_recently",
        }

    if row.channel not in [FollowupChannel.WHATSAPP, FollowupChannel.EMAIL]:
        return {
            "followup_id": row.id,
            "ok": True,
            "skipped": True,
            "reason": "unsupported_channel",
        }

    try:
        row.priority = infer_priority(
            row.kind.value if hasattr(row.kind, "value") else str(row.kind),
            row.status.value if hasattr(row.status, "value") else str(row.status),
            row.next_contact_date,
        )

        _mark_rule_evaluated(
            db,
            row=row,
            me=me,
            summary="Regla automática: seguimiento evaluado para envío",
        )
        db.commit()

        result = send_via_n8n(
            db=db,
            row=row,
            me=me,
            channel=row.channel.value,
        )

        return {
            "followup_id": row.id,
            "ok": True,
            "sent": not result.get("duplicate_prevented", False),
            "duplicate_prevented": result.get("duplicate_prevented", False),
            "external_ref": result.get("external_ref", ""),
        }

    except Exception as exc:
        db.rollback()

        try:
            row = db.get(StudentFollowup, row.id)
            if row:
                append_followup_action(
                    db,
                    row=row,
                    me=me,
                    action_type=FollowupActionType.NOTA,
                    channel=row.channel,
                    summary="Regla automática: error en procesamiento",
                    payload_text=str(exc),
                    delivery_status="RULE_ERROR",
                )
                db.commit()
        except Exception:
            db.rollback()

        logger.exception("Error procesando followup en corrida automática", extra={"followup_id": row.id})
        return {
            "followup_id": row.id,
            "ok": False,
            "reason": "exception",
            "error": str(exc),
        }


def run_followup_rules_for_all(db: Session, *, me: User) -> dict:
    processed_ids: set[int] = set()

    morosity_rows = _eligible_morosity_rows(db)
    inactivity_rows = _eligible_inactivity_rows(db)
    general_rows = _eligible_general_rows(db)

    queue: list[StudentFollowup] = []
    for batch in (morosity_rows, inactivity_rows, general_rows):
        for row in batch:
            if row.id in processed_ids:
                continue
            processed_ids.add(row.id)
            queue.append(row)

    summary = {
        "ok": True,
        "evaluated": len(queue),
        "sent": 0,
        "duplicate_prevented": 0,
        "skipped": 0,
        "errors": 0,
        "items": [],
    }

    for row in queue:
        item_result = _process_single_row(db, row=row, me=me)
        summary["items"].append(item_result)

        if not item_result.get("ok"):
            summary["errors"] += 1
            continue

        if item_result.get("duplicate_prevented"):
            summary["duplicate_prevented"] += 1
        elif item_result.get("sent"):
            summary["sent"] += 1
        else:
            summary["skipped"] += 1

        if item_result.get("skipped"):
            summary["skipped"] += 1

    return summary