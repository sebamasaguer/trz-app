from datetime import datetime, UTC
import json

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import (
    ContactConversation,
    ConversationMessage,
    ConversationStatus,
    SenderType,
    User,
    StudentFollowup,
    FollowupAction,
    FollowupActionType,
    FollowupChannel,
    FollowupPriority,
)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def send_manual_whatsapp_message(phone: str, text: str) -> dict:
    phone = (phone or "").strip()
    text = (text or "").strip()

    if not phone:
        return {"ok": False, "status": "ERROR", "detail": "phone vacío"}
    if not text:
        return {"ok": False, "status": "ERROR", "detail": "text vacío"}

    webhook_url = getattr(settings, "N8N_WA_SEND_WEBHOOK", "") or getattr(settings, "N8N_WHATSAPP_WEBHOOK_URL", "") or ""
    auth_token = getattr(settings, "N8N_WA_SEND_TOKEN", "") or getattr(settings, "N8N_WHATSAPP_TOKEN", "") or ""

    if not webhook_url:
        return {
            "ok": False,
            "status": "NOT_CONFIGURED",
            "detail": "Webhook de WhatsApp no configurado",
            "phone": phone,
            "text": text,
        }

    payload = {
        "phone": phone,
        "text": text,
    }

    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(webhook_url, json=payload, headers=headers)

        body_text = response.text
        try:
            body_json = response.json()
        except Exception:
            body_json = None

        return {
            "ok": response.is_success,
            "status": "OK" if response.is_success else "ERROR",
            "http_status": response.status_code,
            "response_json": body_json,
            "response_text": body_text,
            "phone": phone,
            "text": text,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "ERROR",
            "detail": str(exc),
            "phone": phone,
            "text": text,
        }


def build_quick_message(db: Session, kind: str) -> str:
    kind = (kind or "").strip().lower()

    presets = {
        "saludo": "Hola, ¿cómo estás? Te escribimos desde TRZ para seguir tu consulta.",
        "precios": "¡Hola! Te paso la información de membresías y opciones disponibles. Si querés, te ayudamos a elegir la mejor para vos.",
        "seguimiento": "Hola, ¿cómo estás? Quedamos atentos si querés continuar con tu consulta o avanzar con tu inscripción.",
        "reactivacion": "¡Hola! Vimos tu consulta previa. Si querés retomar, te ayudamos a continuar por acá.",
        "cierre": "¡Hola! Si querés, avanzamos ahora mismo con tu inscripción o te derivamos con una persona para cerrar todo.",
    }

    return presets.get(
        kind,
        "Hola, ¿cómo estás? Te escribimos desde TRZ para continuar la conversación por acá.",
    )


def register_outbound_human_message(
    db: Session,
    *,
    row: ContactConversation,
    me: User,
    text: str,
    result,
    pause_assistant: bool,
) -> None:
    text = (text or "").strip()
    result = result or {}

    message = ConversationMessage(
        conversation_id=row.id,
        sender_type=SenderType.HUMANO,
        is_inbound=False,
        message_text=text,
        external_ref="",
        intent_detected="manual_human_message",
        confidence=None,
        generated_by_ai=False,
        delivery_status="OK" if result.get("ok") else (result.get("status") or "ERROR"),
        raw_payload=json.dumps(result, ensure_ascii=False),
    )
    db.add(message)

    row.last_message_at = _utcnow_naive()
    row.updated_at = _utcnow_naive()

    if pause_assistant:
        row.assistant_paused = True
        row.assistant_paused_at = _utcnow_naive()
        row.assistant_paused_by_user_id = me.id
        row.status = ConversationStatus.DERIVADA_A_HUMANO
    elif row.status != ConversationStatus.DERIVADA_A_HUMANO:
        row.status = ConversationStatus.EN_AUTOMATICO

    if row.followup_id:
        followup = db.get(StudentFollowup, row.followup_id)
        if followup:
            followup.priority = FollowupPriority.ALTA
            followup.last_action_at = _utcnow_naive()
            followup.last_action_type = FollowupActionType.NOTA.value
            followup.result_summary = text

            action = FollowupAction(
                followup_id=followup.id,
                created_by_id=me.id,
                action_type=FollowupActionType.NOTA,
                channel=FollowupChannel.WHATSAPP,
                summary="Mensaje manual enviado desde conversación",
                payload_text=text,
                external_ref="",
                delivery_status="OK" if result.get("ok") else (result.get("status") or "ERROR"),
                response_payload=json.dumps(result, ensure_ascii=False),
            )
            db.add(action)

    db.commit()