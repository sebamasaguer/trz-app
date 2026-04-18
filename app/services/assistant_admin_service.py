from datetime import datetime, UTC
import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    User,
    Prospect,
    ProspectStatus,
    ContactConversation,
    ConversationStatus,
    StudentFollowup,
    FollowupPriority,
    FollowupChannel,
    FollowupAction,
    FollowupActionType,
    CommercialStage,
    FollowupStatus,
)
from .assistant_admin_ops_service import (
    send_manual_whatsapp_message,
    build_quick_message,
    register_outbound_human_message,
)

logger = logging.getLogger("app.assistant_admin")


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def get_conversation_or_404(db: Session, conversation_id: int) -> ContactConversation:
    row = db.get(ContactConversation, conversation_id)
    if not row:
        logger.warning("assistant_admin_conversation_not_found conversation_id=%s", conversation_id)
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return row


def pause_conversation(db: Session, row: ContactConversation, me: User) -> None:
    row.assistant_paused = True
    row.assistant_paused_at = _utcnow_naive()
    row.assistant_paused_by_user_id = me.id
    row.status = ConversationStatus.DERIVADA_A_HUMANO
    row.updated_at = _utcnow_naive()
    db.commit()

    logger.info(
        "assistant_admin_pause conversation_id=%s by_user_id=%s followup_id=%s prospect_id=%s",
        row.id,
        me.id,
        row.followup_id,
        row.prospect_id,
    )


def resume_conversation(db: Session, row: ContactConversation) -> None:
    row.assistant_paused = False
    row.assistant_paused_at = None
    row.assistant_paused_by_user_id = None
    row.status = ConversationStatus.EN_AUTOMATICO
    row.updated_at = _utcnow_naive()
    db.commit()

    logger.info(
        "assistant_admin_resume conversation_id=%s followup_id=%s prospect_id=%s",
        row.id,
        row.followup_id,
        row.prospect_id,
    )


def send_manual_conversation_message(
    db: Session,
    *,
    row: ContactConversation,
    me: User,
    text: str,
    pause_assistant: bool,
) -> None:
    text = (text or "").strip()
    if not text:
        logger.warning(
            "assistant_admin_send_manual_empty conversation_id=%s by_user_id=%s",
            row.id,
            me.id,
        )
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    result = send_manual_whatsapp_message(row.phone, text)

    register_outbound_human_message(
        db=db,
        row=row,
        me=me,
        text=text,
        result=result,
        pause_assistant=pause_assistant,
    )

    logger.info(
        "assistant_admin_send_manual conversation_id=%s by_user_id=%s paused=%s ok=%s",
        row.id,
        me.id,
        pause_assistant,
        bool(result.get("ok")) if isinstance(result, dict) else None,
    )


def send_quick_conversation_message(
    db: Session,
    *,
    row: ContactConversation,
    me: User,
    kind: str,
    pause_assistant: bool,
) -> None:
    text = build_quick_message(db, kind)
    result = send_manual_whatsapp_message(row.phone, text)

    register_outbound_human_message(
        db=db,
        row=row,
        me=me,
        text=text,
        result=result,
        pause_assistant=pause_assistant,
    )

    logger.info(
        "assistant_admin_send_quick conversation_id=%s by_user_id=%s kind=%s paused=%s ok=%s",
        row.id,
        me.id,
        kind,
        pause_assistant,
        bool(result.get("ok")) if isinstance(result, dict) else None,
    )


def mark_conversation_reactivated(
    db: Session,
    *,
    row: ContactConversation,
    me: User,
) -> None:
    followup_touched = False

    if row.followup_id:
        followup = db.get(StudentFollowup, row.followup_id)
        if followup:
            followup.status = FollowupStatus.REACTIVADO
            followup.priority = FollowupPriority.ALTA
            followup.last_action_at = _utcnow_naive()
            followup.last_action_type = FollowupActionType.NOTA.value

            action = FollowupAction(
                followup_id=followup.id,
                created_by_id=me.id,
                action_type=FollowupActionType.NOTA,
                channel=FollowupChannel.WHATSAPP,
                summary="Marcado manualmente como reactivado",
                payload_text="",
                external_ref="",
                delivery_status="OK",
                response_payload="",
            )
            db.add(action)
            followup_touched = True

    row.updated_at = _utcnow_naive()
    db.commit()

    logger.info(
        "assistant_admin_mark_reactivated conversation_id=%s by_user_id=%s followup_id=%s followup_touched=%s",
        row.id,
        me.id,
        row.followup_id,
        followup_touched,
    )


def mark_conversation_handoff(
    db: Session,
    *,
    row: ContactConversation,
    me: User,
) -> None:
    followup_touched = False
    prospect_touched = False

    row.status = ConversationStatus.DERIVADA_A_HUMANO
    row.assistant_paused = True
    row.assistant_paused_at = _utcnow_naive()
    row.assistant_paused_by_user_id = me.id
    row.handoff_reason = "Derivación manual desde panel"
    row.updated_at = _utcnow_naive()

    if row.followup_id:
        followup = db.get(StudentFollowup, row.followup_id)
        if followup:
            followup.priority = FollowupPriority.ALTA
            followup.last_action_at = _utcnow_naive()
            followup.last_action_type = FollowupActionType.NOTA.value

            action = FollowupAction(
                followup_id=followup.id,
                created_by_id=me.id,
                action_type=FollowupActionType.NOTA,
                channel=FollowupChannel.WHATSAPP,
                summary="Derivación manual a humano",
                payload_text="",
                external_ref="",
                delivery_status="DERIVADO",
                response_payload="",
            )
            db.add(action)
            followup_touched = True

    if row.prospect_id:
        prospect = db.get(Prospect, row.prospect_id)
        if prospect:
            prospect.status = ProspectStatus.DERIVADO
            prospect_touched = True

    db.commit()

    logger.info(
        "assistant_admin_mark_handoff conversation_id=%s by_user_id=%s followup_id=%s prospect_id=%s followup_touched=%s prospect_touched=%s",
        row.id,
        me.id,
        row.followup_id,
        row.prospect_id,
        followup_touched,
        prospect_touched,
    )


def change_conversation_stage(
    db: Session,
    *,
    row: ContactConversation,
    me: User,
    stage: str,
    note: str,
) -> None:
    try:
        new_stage = CommercialStage(stage)
    except Exception:
        logger.warning(
            "assistant_admin_invalid_stage conversation_id=%s by_user_id=%s stage=%s",
            row.id,
            me.id,
            stage,
        )
        raise HTTPException(status_code=400, detail="Etapa no válida")

    row.commercial_stage = new_stage
    row.commercial_stage_updated_at = _utcnow_naive()
    row.commercial_stage_note = (note or "").strip()

    if new_stage == CommercialStage.DERIVADO:
        row.assistant_paused = True
        row.assistant_paused_at = _utcnow_naive()
        row.assistant_paused_by_user_id = me.id
        row.status = ConversationStatus.DERIVADA_A_HUMANO

    row.updated_at = _utcnow_naive()
    db.commit()

    logger.info(
        "assistant_admin_change_stage conversation_id=%s by_user_id=%s stage=%s paused=%s",
        row.id,
        me.id,
        new_stage.value if hasattr(new_stage, "value") else str(new_stage),
        bool(row.assistant_paused),
    )