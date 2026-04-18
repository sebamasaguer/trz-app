from datetime import datetime, UTC
import json
import logging

from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..models import (
    User,
    Prospect,
    ContactConversation,
    SenderType,
    FollowupStatus,
    FollowupPriority,
    FollowupChannel,
    FollowupAction,
    FollowupActionType,
    ConversationStatus,
    ProspectStatus,
)
from .assistant_context_service import get_trz_knowledge
from .assistant_identity_service import (
    normalize_phone,
    find_student_by_phone,
    find_or_create_prospect,
)
from .assistant_conversation_service import (
    find_or_create_conversation,
    save_conversation_message,
    build_recent_messages,
)
from .assistant_lead_service import (
    find_open_followup_for_student,
    ensure_followup_for_reactivation,
    create_handoff_action,
    infer_commercial_stage,
)
from .assistant_fallback_service import local_intent_fallback
from .ai_client import call_openai_agent


logger = logging.getLogger("app.assistant_inbound")


SAFE_HANDOFF_INTENTS = {
    "handoff_requested",
    "ready_to_close",
    "payment_request",
    "complaint",
}


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _safe_rollback(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def process_inbound_message(
    db: Session,
    *,
    payload: dict,
) -> JSONResponse:
    incoming_text = (payload.get("incoming_text") or "").strip()
    incoming_phone_raw = (payload.get("incoming_phone") or "").strip()
    incoming_phone = normalize_phone(incoming_phone_raw)
    incoming_name = (payload.get("incoming_name") or "").strip()
    incoming_email = (payload.get("incoming_email") or "").strip()
    external_ref = (payload.get("external_ref") or "").strip()
    external_chat_id = (payload.get("external_chat_id") or "").strip()

    logger.info(
        "assistant_inbound_start phone_raw=%s phone=%s name=%s has_text=%s external_chat_id=%s",
        incoming_phone_raw,
        incoming_phone,
        incoming_name,
        bool(incoming_text),
        bool(external_chat_id),
    )

    if not incoming_phone:
        logger.warning("assistant_inbound_invalid missing_phone name=%s", incoming_name)
        raise ValueError("incoming_phone es obligatorio")

    if not incoming_text:
        logger.warning("assistant_inbound_invalid missing_text phone=%s", incoming_phone)
        raise ValueError("incoming_text es obligatorio")

    try:
        student: User | None = find_student_by_phone(db, incoming_phone)
        prospect: Prospect | None = None

        if student:
            followup = find_open_followup_for_student(db, student.id)
            if not followup:
                followup = ensure_followup_for_reactivation(
                    db,
                    student,
                    summary="Inbound automático",
                    auto_commit=False,
                )
            logger.info(
                "assistant_inbound_actor student_id=%s followup_id=%s phone=%s",
                student.id,
                followup.id if followup else None,
                incoming_phone,
            )
        else:
            followup = None
            prospect = find_or_create_prospect(
                db,
                incoming_name,
                incoming_phone,
                incoming_email,
                auto_commit=False,
            )
            logger.info(
                "assistant_inbound_actor prospect_id=%s phone=%s created_or_found_prospect=true",
                prospect.id if prospect else None,
                incoming_phone,
            )

        conversation: ContactConversation = find_or_create_conversation(
            db=db,
            phone=incoming_phone,
            student=student,
            prospect=prospect,
            followup=followup,
            auto_commit=False,
        )

        logger.info(
            "assistant_inbound_conversation conversation_id=%s student_id=%s prospect_id=%s followup_id=%s paused=%s",
            conversation.id,
            student.id if student else None,
            prospect.id if prospect else None,
            followup.id if followup else None,
            bool(getattr(conversation, "assistant_paused", False)),
        )

        if external_chat_id and not conversation.external_chat_id:
            conversation.external_chat_id = external_chat_id

        save_conversation_message(
            db=db,
            conversation=conversation,
            sender_type=SenderType.ALUMNO if student else SenderType.PROSPECTO,
            is_inbound=True,
            message_text=incoming_text,
            external_ref=external_ref,
            raw_payload=payload,
            auto_commit=False,
        )

        if getattr(conversation, "assistant_paused", False):
            save_conversation_message(
                db=db,
                conversation=conversation,
                sender_type=SenderType.SISTEMA,
                is_inbound=False,
                message_text="Asistente pausado por operador humano. No se responde automáticamente.",
                external_ref="",
                intent_detected="assistant_paused",
                confidence=None,
                generated_by_ai=False,
                delivery_status="PAUSADO",
                raw_payload={"reason": "assistant_paused"},
                auto_commit=False,
            )

            db.commit()

            logger.info(
                "assistant_inbound_paused conversation_id=%s student_id=%s prospect_id=%s",
                conversation.id,
                student.id if student else None,
                prospect.id if prospect else None,
            )

            return JSONResponse(
                {
                    "ok": True,
                    "conversation_id": conversation.id,
                    "reply_text": "",
                    "intent": "assistant_paused",
                    "confidence": 1.0,
                    "should_handoff_human": False,
                    "handoff_reason": "",
                    "lead_temperature": getattr(conversation, "lead_temperature", "") or "warm",
                    "student_id": student.id if student else None,
                    "prospect_id": prospect.id if prospect else None,
                    "followup_id": followup.id if followup else None,
                    "assistant_paused": True,
                }
            )

        if followup:
            if followup.status == FollowupStatus.CONTACTADO:
                followup.status = FollowupStatus.RESPONDIO
            if not followup.contacted_at:
                followup.contacted_at = _utcnow_naive()
            followup.last_action_at = _utcnow_naive()
            followup.last_action_type = FollowupActionType.NOTA.value
            followup.result_summary = incoming_text

        recent_messages = build_recent_messages(db, conversation.id, limit=10)
        knowledge = get_trz_knowledge(db)

        agent_payload = {
            "conversation_type": conversation.conversation_type.value,
            "contact_name": (
                student.full_name
                if student and student.full_name
                else prospect.full_name
                if prospect and prospect.full_name
                else incoming_name
            ),
            "incoming_text": incoming_text,
            "recent_messages": recent_messages,
            "student": {
                "id": student.id,
                "name": student.full_name,
                "email": student.email,
                "phone": student.phone,
            }
            if student
            else None,
            "prospect": {
                "id": prospect.id,
                "name": prospect.full_name,
                "email": prospect.email,
                "phone": prospect.phone,
                "status": prospect.status.value,
            }
            if prospect
            else None,
            "followup": {
                "id": followup.id,
                "kind": followup.kind.value,
                "status": followup.status.value,
                "priority": followup.priority.value,
                "title": followup.title,
            }
            if followup
            else None,
            "knowledge": knowledge,
        }

        ai_result = call_openai_agent(agent_payload, fallback_fn=local_intent_fallback)

        reply_text = (ai_result.get("reply_text") or "").strip()
        intent = (ai_result.get("intent") or "").strip()
        confidence = float(ai_result.get("confidence") or 0)
        should_create_task = bool(ai_result.get("should_create_task"))
        should_handoff_human = bool(ai_result.get("should_handoff_human"))
        lead_temperature = (ai_result.get("lead_temperature") or "cold").strip()
        handoff_reason = (ai_result.get("handoff_reason") or "").strip()

        if intent not in SAFE_HANDOFF_INTENTS:
            should_handoff_human = False

        logger.info(
            "assistant_inbound_ai conversation_id=%s intent=%s confidence=%s handoff=%s create_task=%s lead_temperature=%s",
            conversation.id,
            intent,
            confidence,
            should_handoff_human,
            should_create_task,
            lead_temperature,
        )

        conversation.intent_last = intent
        conversation.lead_temperature = lead_temperature

        new_stage = infer_commercial_stage(
            intent=intent,
            lead_temperature=lead_temperature,
            should_handoff_human=should_handoff_human,
            current_stage=getattr(conversation, "commercial_stage", None),
        )

        if getattr(conversation, "commercial_stage", None) != new_stage:
            conversation.commercial_stage = new_stage
            conversation.commercial_stage_updated_at = _utcnow_naive()
            conversation.commercial_stage_note = f"Actualizado automáticamente por intent '{intent}'"

        if conversation.status != ConversationStatus.DERIVADA_A_HUMANO:
            conversation.status = (
                ConversationStatus.DERIVADA_A_HUMANO
                if should_handoff_human
                else ConversationStatus.EN_AUTOMATICO
            )

        conversation.updated_at = _utcnow_naive()

        save_conversation_message(
            db=db,
            conversation=conversation,
            sender_type=SenderType.BOT,
            is_inbound=False,
            message_text=reply_text,
            external_ref="",
            intent_detected=intent,
            confidence=confidence,
            generated_by_ai=True,
            delivery_status="PENDIENTE",
            raw_payload=ai_result,
            auto_commit=False,
        )

        if followup:
            if lead_temperature == "hot":
                followup.priority = FollowupPriority.ALTA

            if intent in ["ready_to_close", "handoff_requested"]:
                followup.status = FollowupStatus.REACTIVADO
            elif followup.status == FollowupStatus.CONTACTADO:
                followup.status = FollowupStatus.RESPONDIO

            followup.last_action_at = _utcnow_naive()
            followup.last_action_type = FollowupActionType.NOTA.value
            followup.result_summary = intent or incoming_text

        if prospect:
            if should_handoff_human:
                prospect.status = ProspectStatus.DERIVADO
            elif lead_temperature == "hot":
                prospect.status = ProspectStatus.INTERESADO
            elif prospect.status == ProspectStatus.NUEVO:
                prospect.status = ProspectStatus.CALIFICANDO

            if intent:
                prospect.interest_summary = intent

        if should_create_task and followup:
            action = FollowupAction(
                followup_id=followup.id,
                created_by_id=None,
                action_type=FollowupActionType.NOTA,
                channel=FollowupChannel.WHATSAPP,
                summary=f"Asistente virtual detectó intención: {intent}",
                payload_text=reply_text,
                external_ref="",
                delivery_status="AI",
                response_payload=json.dumps(ai_result, ensure_ascii=False),
            )
            db.add(action)

        db.commit()

        if should_handoff_human:
            create_handoff_action(
                db,
                conversation,
                handoff_reason or "Derivación automática por intención alta",
                auto_commit=True,
            )
            logger.info(
                "assistant_inbound_handoff conversation_id=%s followup_id=%s prospect_id=%s reason=%s",
                conversation.id,
                followup.id if followup else None,
                prospect.id if prospect else None,
                handoff_reason or "Derivación automática por intención alta",
            )

        logger.info(
            "assistant_inbound_done conversation_id=%s student_id=%s prospect_id=%s followup_id=%s intent=%s",
            conversation.id,
            student.id if student else None,
            prospect.id if prospect else None,
            followup.id if followup else None,
            intent,
        )

        return JSONResponse(
            {
                "ok": True,
                "conversation_id": conversation.id,
                "reply_text": reply_text,
                "intent": intent,
                "confidence": confidence,
                "should_handoff_human": should_handoff_human,
                "handoff_reason": handoff_reason,
                "lead_temperature": lead_temperature,
                "student_id": student.id if student else None,
                "prospect_id": prospect.id if prospect else None,
                "followup_id": followup.id if followup else None,
            }
        )

    except Exception as exc:
        _safe_rollback(db)
        logger.exception(
            "assistant_inbound_error phone=%s name=%s external_chat_id=%s error=%s",
            incoming_phone,
            incoming_name,
            external_chat_id,
            exc,
        )
        raise