from types import SimpleNamespace

import pytest

from app.models import FollowupAction, FollowupActionType, FollowupStatus
from app.services.followup_webhook_service import process_followup_webhook


@pytest.fixture()
def patch_webhook_settings(monkeypatch):
    monkeypatch.setattr(
        "app.services.followup_webhook_service.settings",
        SimpleNamespace(
            N8N_FOLLOWUP_TOKEN="token-demo",
        ),
    )


def test_process_followup_webhook_updates_status_and_logs_note(
    db_session,
    basic_followup,
    patch_webhook_settings,
):
    seed_action = FollowupAction(
        followup_id=basic_followup.id,
        created_by_id=None,
        action_type=FollowupActionType.MENSAJE_ENVIADO,
        channel=basic_followup.channel,
        summary="Envío WHATSAPP iniciado",
        external_ref="ext-123",
        delivery_status="PENDING",
    )
    db_session.add(seed_action)
    basic_followup.outbound_in_progress = True
    db_session.commit()

    result = process_followup_webhook(
        db_session,
        payload={
            "external_ref": "ext-123",
            "followup_id": basic_followup.id,
            "channel": "WHATSAPP",
            "status": "DELIVERED",
            "message": "Entregado",
        },
        header_token="token-demo",
    )

    assert result["ok"] is True
    assert result["duplicate_ignored"] is False

    db_session.refresh(basic_followup)
    assert basic_followup.outbound_in_progress is False
    assert basic_followup.status == FollowupStatus.CONTACTADO

    actions = (
        db_session.query(FollowupAction)
        .filter(FollowupAction.followup_id == basic_followup.id)
        .all()
    )
    assert any(
        a.action_type == FollowupActionType.NOTA and a.summary == "Webhook procesado: DELIVERED"
        for a in actions
    )


def test_process_followup_webhook_ignores_duplicate(
    db_session,
    basic_followup,
    patch_webhook_settings,
):
    note = FollowupAction(
        followup_id=basic_followup.id,
        created_by_id=None,
        action_type=FollowupActionType.NOTA,
        channel=basic_followup.channel,
        summary="Webhook procesado: DELIVERED",
        external_ref="dup-1",
        delivery_status="DELIVERED",
    )
    db_session.add(note)
    db_session.commit()

    result = process_followup_webhook(
        db_session,
        payload={
            "external_ref": "dup-1",
            "followup_id": basic_followup.id,
            "channel": "WHATSAPP",
            "status": "DELIVERED",
        },
        header_token="token-demo",
    )

    assert result["ok"] is True
    assert result["duplicate_ignored"] is True