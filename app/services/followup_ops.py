from __future__ import annotations

from app.utils.datetime_utils import utcnow_naive
from typing import TypeVar

from sqlalchemy.orm import Session

from ..models import (
    StudentFollowup,
    FollowupAction,
    FollowupActionType,
    FollowupChannel,
    FollowupKind,
    FollowupPriority,
    FollowupStatus,
    User,
)

T = TypeVar("T")


def safe_enum(enum_cls: type[T], value: str | None) -> T | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return enum_cls(raw)
    except Exception:
        return None


def safe_kind(value: str | None) -> FollowupKind | None:
    return safe_enum(FollowupKind, value)


def safe_status(value: str | None) -> FollowupStatus | None:
    return safe_enum(FollowupStatus, value)


def safe_priority(value: str | None) -> FollowupPriority | None:
    return safe_enum(FollowupPriority, value)


def safe_channel(value: str | None) -> FollowupChannel | None:
    return safe_enum(FollowupChannel, value)


def append_followup_action(
    db: Session,
    *,
    row: StudentFollowup,
    me: User | None,
    action_type: FollowupActionType,
    channel: FollowupChannel | None,
    summary: str,
    payload_text: str = "",
    external_ref: str = "",
    delivery_status: str = "",
    response_payload: str = "",
):
    action = FollowupAction(
        followup_id=row.id,
        created_by_id=me.id if me else None,
        action_type=action_type,
        channel=channel,
        summary=(summary or "").strip(),
        payload_text=payload_text or "",
        external_ref=external_ref or "",
        delivery_status=delivery_status or "",
        response_payload=response_payload or "",
        created_at=utcnow_naive(),
    )
    db.add(action)

    row.last_action_at = utcnow_naive()
    row.last_action_type = action_type.value

    if action_type in [
        FollowupActionType.MENSAJE_ENVIADO,
        FollowupActionType.EMAIL_ENVIADO,
        FollowupActionType.WHATSAPP_ENVIADO,
    ]:
        row.last_message_sent_at = utcnow_naive()