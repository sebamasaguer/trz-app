from __future__ import annotations

from datetime import timedelta
from app.utils.datetime_utils import utcnow_naive
import json
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..core.config import settings
from ..models import (
    StudentFollowup,
    FollowupAction,
    FollowupActionType,
    FollowupChannel,
    FollowupStatus,
    User,
)
from .followup_helpers import build_followup_message
from .followup_ops import append_followup_action

logger = logging.getLogger(__name__)


def _build_external_ref(row: StudentFollowup, channel: str) -> str:
    return f"fup-{row.id}-{channel.lower()}-{uuid.uuid4().hex[:12]}"


def _get_recent_pending_send(
    db: Session,
    *,
    followup_id: int,
    channel: FollowupChannel,
    seconds_window: int = 45,
) -> FollowupAction | None:
    cutoff = utcnow_naive() - timedelta(seconds=seconds_window)

    return db.scalar(
        select(FollowupAction)
        .where(
            FollowupAction.followup_id == followup_id,
            FollowupAction.channel == channel,
            FollowupAction.action_type == FollowupActionType.MENSAJE_ENVIADO,
            FollowupAction.delivery_status == "PENDING",
            FollowupAction.created_at >= cutoff,
        )
        .order_by(FollowupAction.created_at.desc(), FollowupAction.id.desc())
        .limit(1)
    )


def _mark_action_result(
    db: Session,
    *,
    external_ref: str,
    delivery_status: str,
    response_payload: str = "",
):
    if not external_ref:
        return

    action = db.scalar(
        select(FollowupAction)
        .where(FollowupAction.external_ref == external_ref)
        .order_by(FollowupAction.id.desc())
        .limit(1)
    )
    if not action:
        return

    action.delivery_status = delivery_status
    if response_payload:
        action.response_payload = response_payload


def send_via_n8n(
    db: Session,
    *,
    row: StudentFollowup,
    me: User,
    channel: str,
) -> dict:
    if channel not in {"WHATSAPP", "EMAIL"}:
        raise ValueError("Canal inválido")

    row = db.scalar(
        select(StudentFollowup)
        .where(StudentFollowup.id == row.id)
        .options(joinedload(StudentFollowup.student))
    )
    if not row:
        raise ValueError("Seguimiento no encontrado")

    if not row.student:
        raise ValueError("El seguimiento no tiene alumno asociado")

    channel_enum = FollowupChannel(channel)

    recent_pending = _get_recent_pending_send(
        db,
        followup_id=row.id,
        channel=channel_enum,
        seconds_window=45,
    )
    if recent_pending:
        return {
            "ok": True,
            "duplicate_prevented": True,
            "external_ref": recent_pending.external_ref,
            "message": "Ya existe un envío reciente en proceso.",
        }

    if row.outbound_in_progress and row.last_outbound_at:
        if row.last_outbound_at >= utcnow_naive() - timedelta(seconds=45):
            return {
                "ok": True,
                "duplicate_prevented": True,
                "external_ref": row.last_outbound_ref,
                "message": "El seguimiento ya tiene un envío en curso.",
            }

    subject, body = build_followup_message(
        db=db,
        student=row.student,
        row=row,
        channel_value=channel,
    )

    external_ref = _build_external_ref(row, channel)

    payload = {
        "followup_id": row.id,
        "student_id": row.student.id,
        "student_name": row.student.full_name or "",
        "student_email": row.student.email or "",
        "student_phone": row.student.phone or "",
        "channel": channel,
        "subject": subject or "",
        "message": body or "",
        "external_ref": external_ref,
    }

    try:
        row.outbound_in_progress = True
        row.last_outbound_ref = external_ref
        row.last_outbound_at = utcnow_naive()

        append_followup_action(
            db,
            row=row,
            me=me,
            action_type=FollowupActionType.MENSAJE_ENVIADO,
            channel=channel_enum,
            summary=f"Envío {channel} iniciado",
            payload_text=body or "",
            external_ref=external_ref,
            delivery_status="PENDING",
            response_payload=json.dumps(payload, ensure_ascii=False),
        )

        db.commit()

        webhook_url = (
            settings.N8N_FOLLOWUP_WHATSAPP_WEBHOOK
            if channel == "WHATSAPP"
            else settings.N8N_FOLLOWUP_EMAIL_WEBHOOK
        )

        if not webhook_url:
            raise RuntimeError(f"No está configurado el webhook n8n para {channel}")

        headers = {"Content-Type": "application/json"}
        if getattr(settings, "N8N_FOLLOWUP_TOKEN", ""):
            headers["X-Followup-Token"] = settings.N8N_FOLLOWUP_TOKEN

        with httpx.Client(timeout=20) as client:
            response = client.post(webhook_url, json=payload, headers=headers)

        response_text = response.text[:4000] if response.text else ""

        row = db.get(StudentFollowup, row.id)
        if not row:
            raise RuntimeError("Seguimiento no encontrado luego del envío")

        if response.status_code >= 400:
            row.outbound_in_progress = False
            _mark_action_result(
                db,
                external_ref=external_ref,
                delivery_status="ERROR",
                response_payload=response_text,
            )
            db.commit()
            raise RuntimeError(f"n8n respondió con status {response.status_code}")

        row.status = FollowupStatus.CONTACTADO
        if row.contacted_at is None:
            row.contacted_at = utcnow_naive()

        if channel == "WHATSAPP":
            append_followup_action(
                db,
                row=row,
                me=me,
                action_type=FollowupActionType.WHATSAPP_ENVIADO,
                channel=FollowupChannel.WHATSAPP,
                summary="WhatsApp enviado a n8n",
                payload_text=body or "",
                external_ref=external_ref,
                delivery_status="SENT",
                response_payload=response_text,
            )
        else:
            append_followup_action(
                db,
                row=row,
                me=me,
                action_type=FollowupActionType.EMAIL_ENVIADO,
                channel=FollowupChannel.EMAIL,
                summary=f"Email enviado a n8n: {subject}" if subject else "Email enviado a n8n",
                payload_text=body or "",
                external_ref=external_ref,
                delivery_status="SENT",
                response_payload=response_text,
            )

        _mark_action_result(
            db,
            external_ref=external_ref,
            delivery_status="SENT",
            response_payload=response_text,
        )

        row.outbound_in_progress = False
        db.commit()

        return {
            "ok": True,
            "duplicate_prevented": False,
            "external_ref": external_ref,
            "status_code": response.status_code,
        }

    except Exception as exc:
        logger.exception("Error enviando followup a n8n")
        db.rollback()

        row = db.get(StudentFollowup, row.id)
        if row:
            row.outbound_in_progress = False
            try:
                _mark_action_result(
                    db,
                    external_ref=external_ref if "external_ref" in locals() else "",
                    delivery_status="ERROR",
                    response_payload=str(exc),
                )
                db.commit()
            except Exception:
                db.rollback()

        raise