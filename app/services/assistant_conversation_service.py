from datetime import datetime, UTC
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Prospect,
    ContactConversation,
    ConversationMessage,
    ConversationType,
    ConversationStatus,
    SenderType,
    StudentFollowup,
    User,
    FollowupChannel,
)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def find_or_create_conversation(
    db: Session,
    *,
    phone: str,
    student: User | None,
    prospect: Prospect | None,
    followup: StudentFollowup | None,
    auto_commit: bool = True,
) -> ContactConversation:
    row = db.scalars(
        select(ContactConversation)
        .where(
            ContactConversation.phone == phone,
            ContactConversation.status.in_(
                [
                    ConversationStatus.ABIERTA,
                    ConversationStatus.EN_AUTOMATICO,
                    ConversationStatus.DERIVADA_A_HUMANO,
                ]
            ),
        )
        .order_by(ContactConversation.id.desc())
    ).first()

    if row:
        if student and not row.student_id:
            row.student_id = student.id
        if prospect and not row.prospect_id:
            row.prospect_id = prospect.id
        if followup and not row.followup_id:
            row.followup_id = followup.id

        row.last_message_at = _utcnow_naive()

        if row.status != ConversationStatus.DERIVADA_A_HUMANO:
            row.status = ConversationStatus.EN_AUTOMATICO

        if auto_commit:
            db.commit()
        return row

    if student and followup:
        conversation_type = ConversationType.REACTIVACION
    elif prospect:
        conversation_type = ConversationType.NUEVO_PROSPECTO
    else:
        conversation_type = ConversationType.GENERAL

    row = ContactConversation(
        channel=FollowupChannel.WHATSAPP,
        phone=phone,
        student_id=student.id if student else None,
        prospect_id=prospect.id if prospect else None,
        followup_id=followup.id if followup else None,
        conversation_type=conversation_type,
        status=ConversationStatus.EN_AUTOMATICO,
        last_message_at=_utcnow_naive(),
    )
    db.add(row)

    if auto_commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()

    return row


def save_conversation_message(
    db: Session,
    *,
    conversation: ContactConversation,
    sender_type: SenderType,
    is_inbound: bool,
    message_text: str,
    external_ref: str = "",
    intent_detected: str = "",
    confidence: float | None = None,
    generated_by_ai: bool = False,
    delivery_status: str = "",
    raw_payload: dict | None = None,
    auto_commit: bool = True,
):
    row = ConversationMessage(
        conversation_id=conversation.id,
        sender_type=sender_type,
        is_inbound=is_inbound,
        message_text=(message_text or "").strip(),
        external_ref=(external_ref or "").strip(),
        intent_detected=(intent_detected or "").strip(),
        confidence=confidence,
        generated_by_ai=generated_by_ai,
        delivery_status=(delivery_status or "").strip(),
        raw_payload=json.dumps(raw_payload or {}, ensure_ascii=False),
    )
    db.add(row)

    conversation.last_message_at = _utcnow_naive()

    if auto_commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()

    return row


def build_recent_messages(db: Session, conversation_id: int, limit: int = 12) -> list[dict]:
    rows = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.id.desc())
        .limit(limit)
    ).all()

    rows = list(reversed(rows))
    out = []
    for row in rows:
        role = "user" if row.is_inbound else "assistant"
        out.append(
            {
                "role": role,
                "text": row.message_text,
                "sender_type": row.sender_type.value,
                "intent": row.intent_detected,
            }
        )
    return out