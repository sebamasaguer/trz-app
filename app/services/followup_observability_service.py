from __future__ import annotations

from datetime import timedelta
from app.utils.datetime_utils import utcnow_naive

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import (
    StudentFollowup,
    FollowupAction,
    FollowupActionType,
    FollowupChannel,
)


def _count_actions(
    db: Session,
    *,
    action_type: FollowupActionType | None = None,
    delivery_status: str | None = None,
    hours: int | None = None,
    summary_prefix: str | None = None,
    channel: FollowupChannel | None = None,
) -> int:
    stmt = select(func.count(FollowupAction.id))

    if action_type is not None:
        stmt = stmt.where(FollowupAction.action_type == action_type)

    if delivery_status is not None:
        stmt = stmt.where(FollowupAction.delivery_status == delivery_status)

    if channel is not None:
        stmt = stmt.where(FollowupAction.channel == channel)

    if summary_prefix:
        stmt = stmt.where(FollowupAction.summary.ilike(f"{summary_prefix}%"))

    if hours is not None:
        cutoff = utcnow_naive() - timedelta(hours=hours)
        stmt = stmt.where(FollowupAction.created_at >= cutoff)

    return int(db.scalar(stmt) or 0)


def get_followup_observability_data(db: Session) -> dict:
    pending_total = _count_actions(
        db,
        action_type=FollowupActionType.MENSAJE_ENVIADO,
        delivery_status="PENDING",
    )
    sent_total = _count_actions(
        db,
        action_type=FollowupActionType.MENSAJE_ENVIADO,
        delivery_status="SENT",
    )
    error_total = _count_actions(
        db,
        action_type=FollowupActionType.MENSAJE_ENVIADO,
        delivery_status="ERROR",
    )

    pending_24h = _count_actions(
        db,
        action_type=FollowupActionType.MENSAJE_ENVIADO,
        delivery_status="PENDING",
        hours=24,
    )
    sent_24h = _count_actions(
        db,
        action_type=FollowupActionType.MENSAJE_ENVIADO,
        delivery_status="SENT",
        hours=24,
    )
    error_24h = _count_actions(
        db,
        action_type=FollowupActionType.MENSAJE_ENVIADO,
        delivery_status="ERROR",
        hours=24,
    )

    webhook_processed_24h = _count_actions(
        db,
        action_type=FollowupActionType.NOTA,
        summary_prefix="Webhook procesado:",
        hours=24,
    )

    rule_error_24h = _count_actions(
        db,
        action_type=FollowupActionType.NOTA,
        delivery_status="RULE_ERROR",
        hours=24,
    )

    rule_evaluated_24h = _count_actions(
        db,
        action_type=FollowupActionType.NOTA,
        delivery_status="RULE_EVALUATED",
        hours=24,
    )

    whatsapp_sent_24h = _count_actions(
        db,
        action_type=FollowupActionType.WHATSAPP_ENVIADO,
        hours=24,
    )
    email_sent_24h = _count_actions(
        db,
        action_type=FollowupActionType.EMAIL_ENVIADO,
        hours=24,
    )

    outbound_in_progress = int(
        db.scalar(
            select(func.count(StudentFollowup.id)).where(
                StudentFollowup.outbound_in_progress == True
            )
        ) or 0
    )

    recent_actions = db.scalars(
        select(FollowupAction)
        .options(
            joinedload(FollowupAction.followup).joinedload(StudentFollowup.student),
            joinedload(FollowupAction.created_by),
        )
        .order_by(FollowupAction.created_at.desc(), FollowupAction.id.desc())
        .limit(40)
    ).all()

    pending_old = db.scalars(
        select(FollowupAction)
        .options(
            joinedload(FollowupAction.followup).joinedload(StudentFollowup.student),
        )
        .where(
            FollowupAction.action_type == FollowupActionType.MENSAJE_ENVIADO,
            FollowupAction.delivery_status == "PENDING",
            FollowupAction.created_at <= utcnow_naive() - timedelta(minutes=10),
        )
        .order_by(FollowupAction.created_at.asc(), FollowupAction.id.asc())
        .limit(30)
    ).all()

    return {
        "summary": {
            "pending_total": pending_total,
            "sent_total": sent_total,
            "error_total": error_total,
            "pending_24h": pending_24h,
            "sent_24h": sent_24h,
            "error_24h": error_24h,
            "webhook_processed_24h": webhook_processed_24h,
            "rule_error_24h": rule_error_24h,
            "rule_evaluated_24h": rule_evaluated_24h,
            "whatsapp_sent_24h": whatsapp_sent_24h,
            "email_sent_24h": email_sent_24h,
            "outbound_in_progress": outbound_in_progress,
        },
        "recent_actions": recent_actions,
        "pending_old": pending_old,
    }