from types import SimpleNamespace

import pytest

from app.models import FollowupAction, FollowupActionType, FollowupStatus
from app.services.followup_message_service import send_via_n8n


class DummyResponse:
    def __init__(self, status_code=200, text="OK"):
        self.status_code = status_code
        self.text = text


class DummyClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None, headers=None):
        return DummyResponse(status_code=200, text='{"ok": true}')


@pytest.fixture()
def patch_message_dependencies(monkeypatch):
    monkeypatch.setattr(
        "app.services.followup_message_service.build_followup_message",
        lambda db, student, row, channel_value: ("Asunto demo", "Mensaje demo"),
    )
    monkeypatch.setattr(
        "app.services.followup_message_service.httpx.Client",
        DummyClient,
    )
    monkeypatch.setattr(
        "app.services.followup_message_service.settings",
        SimpleNamespace(
            N8N_FOLLOWUP_WHATSAPP_WEBHOOK="http://fake-whatsapp",
            N8N_FOLLOWUP_EMAIL_WEBHOOK="http://fake-email",
            N8N_FOLLOWUP_TOKEN="token-demo",
        ),
    )


def test_send_via_n8n_whatsapp_marks_contacted_and_creates_actions(
    db_session,
    admin_user,
    basic_followup,
    patch_message_dependencies,
):
    result = send_via_n8n(
        db=db_session,
        row=basic_followup,
        me=admin_user,
        channel="WHATSAPP",
    )

    assert result["ok"] is True
    assert result["duplicate_prevented"] is False
    assert result["external_ref"]

    db_session.refresh(basic_followup)
    assert basic_followup.status == FollowupStatus.CONTACTADO
    assert basic_followup.contacted_at is not None
    assert basic_followup.outbound_in_progress is False

    actions = (
        db_session.query(FollowupAction)
        .filter(FollowupAction.followup_id == basic_followup.id)
        .all()
    )
    assert any(a.action_type == FollowupActionType.MENSAJE_ENVIADO for a in actions)
    assert any(a.action_type == FollowupActionType.WHATSAPP_ENVIADO for a in actions)


def test_send_via_n8n_creates_traceable_actions(
    db_session,
    admin_user,
    basic_followup,
    patch_message_dependencies,
):
    result = send_via_n8n(
        db=db_session,
        row=basic_followup,
        me=admin_user,
        channel="WHATSAPP",
    )

    assert result["ok"] is True
    assert result["external_ref"]

    actions = (
        db_session.query(FollowupAction)
        .filter(FollowupAction.followup_id == basic_followup.id)
        .order_by(FollowupAction.id.asc())
        .all()
    )

    assert len(actions) >= 2
    assert any(
        a.action_type == FollowupActionType.MENSAJE_ENVIADO and a.external_ref == result["external_ref"]
        for a in actions
    )
    assert any(
        a.action_type == FollowupActionType.WHATSAPP_ENVIADO and a.external_ref == result["external_ref"]
        for a in actions
    )