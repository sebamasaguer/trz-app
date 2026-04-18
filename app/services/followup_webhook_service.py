from __future__ import annotations

from app.utils.datetime_utils import utcnow_naive
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import (
    StudentFollowup,
    FollowupAction,
    FollowupActionType,
    FollowupStatus,
    FollowupChannel,
)
from .followup_ops import append_followup_action

logger = logging.getLogger(__name__)


def _normalize_status(value: str) -> str:
    raw = (value or "").strip().upper()
    mapping = {
        "OK": "DELIVERED",
        "SUCCESS": "DELIVERED",
        "SENT": "DELIVERED",
        "DELIVERED": "DELIVERED",
        "FAILED": "FAILED",
        "ERROR": "FAILED",
        "BOUNCED": "FAILED",
        "READ": "READ",
        "REPLIED": "REPLIED",
    }
    return mapping.get(raw, raw or "UNKNOWN")


def process_followup_webhook(
    db: Session,
    *,
    payload: dict,
    header_token: str | None,
) -> dict:
    expected = getattr(settings, "N8N_FOLLOWUP_TOKEN", "") or ""
    if expected and header_token != expected:
        return {"ok": False, "error": "unauthorized"}

    external_ref = (payload.get("external_ref") or "").strip()
    followup_id = payload.get("followup_id")
    channel_value = (payload.get("channel") or "").strip().upper()
    provider_status = _normalize_status(payload.get("status") or payload.get("delivery_status") or "")
    provider_message = payload.get("message") or payload.get("detail") or ""
    raw_payload = json.dumps(payload, ensure_ascii=False)

    if not external_ref and not followup_id:
        return {"ok": False, "error": "missing identifiers"}

    channel = None
    if channel_value in {"WHATSAPP", "EMAIL"}:
        channel = FollowupChannel(channel_value)

    existing_same_ref = None
    if external_ref:
        existing_same_ref = db.scalar(
            select(FollowupAction)
            .where(
                FollowupAction.external_ref == external_ref,
                FollowupAction.action_type == FollowupActionType.NOTA,
                FollowupAction.summary == f"Webhook procesado: {provider_status}",
            )
            .limit(1)
        )
        if existing_same_ref:
            return {
                "ok": True,
                "duplicate_ignored": True,
                "external_ref": external_ref,
            }

    row = None
    if followup_id:
        row = db.get(StudentFollowup, int(followup_id))

    if row is None and external_ref:
        action = db.scalar(
            select(FollowupAction)
            .where(FollowupAction.external_ref == external_ref)
            .order_by(FollowupAction.id.desc())
            .limit(1)
        )
        if action:
            row = db.get(StudentFollowup, action.followup_id)

    if row is None:
        return {"ok": False, "error": "followup not found"}

    try:
        row.outbound_in_progress = False

        related_actions = db.scalars(
            select(FollowupAction)
            .where(FollowupAction.external_ref == external_ref)
        ).all()

        for action in related_actions:
            action.delivery_status = provider_status
            action.response_payload = raw_payload

        if provider_status in {"DELIVERED", "READ"}:
            if row.status == FollowupStatus.PENDIENTE:
                row.status = FollowupStatus.CONTACTADO
            if row.contacted_at is None:
                row.contacted_at = utcnow_naive()

        elif provider_status == "REPLIED":
            row.status = FollowupStatus.RESPONDIO

        append_followup_action(
            db,
            row=row,
            me=None,
            action_type=FollowupActionType.NOTA,
            channel=channel,
            summary=f"Webhook procesado: {provider_status}",
            payload_text=provider_message,
            external_ref=external_ref,
            delivery_status=provider_status,
            response_payload=raw_payload,
        )

        db.commit()

        return {
            "ok": True,
            "duplicate_ignored": False,
            "external_ref": external_ref,
            "status": provider_status,
        }
    except Exception:
        db.rollback()
        logger.exception("Error procesando webhook de followup")
        raise