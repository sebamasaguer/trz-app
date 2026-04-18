import json
from types import SimpleNamespace

import pytest

from app.services import assistant_inbound_service as svc


class DummyDB:
    def commit(self):
        return None

    def rollback(self):
        return None

    def add(self, obj):
        return None

    def flush(self):
        return None

    def refresh(self, obj):
        return None


def _body(response):
    return json.loads(response.body.decode("utf-8"))


def test_process_inbound_requires_phone():
    db = DummyDB()

    with pytest.raises(ValueError, match="incoming_phone es obligatorio"):
        svc.process_inbound_message(
            db,
            payload={
                "incoming_text": "hola",
                "incoming_name": "Prueba",
            },
        )


def test_process_inbound_requires_text():
    db = DummyDB()

    with pytest.raises(ValueError, match="incoming_text es obligatorio"):
        svc.process_inbound_message(
            db,
            payload={
                "incoming_phone": "5493870000000",
                "incoming_name": "Prueba",
            },
        )


def test_process_inbound_paused_returns_empty_reply(monkeypatch):
    db = DummyDB()

    conversation = SimpleNamespace(
        id=25,
        assistant_paused=True,
        lead_temperature="warm",
        external_chat_id="",
    )

    prospect = SimpleNamespace(
        id=10,
        full_name="Prueba",
        email="",
        phone="5493870000000",
        status=SimpleNamespace(value="NUEVO"),
    )

    calls = {"save_count": 0}

    monkeypatch.setattr(svc, "normalize_phone", lambda phone: "5493870000000")
    monkeypatch.setattr(svc, "find_student_by_phone", lambda db, phone: None)
    monkeypatch.setattr(
        svc,
        "find_or_create_prospect",
        lambda db, name, phone, email, **kwargs: prospect,
    )
    monkeypatch.setattr(svc, "find_or_create_conversation", lambda **kwargs: conversation)

    def fake_save_conversation_message(**kwargs):
        calls["save_count"] += 1

    monkeypatch.setattr(svc, "save_conversation_message", fake_save_conversation_message)

    response = svc.process_inbound_message(
        db,
        payload={
            "incoming_phone": "5493870000000",
            "incoming_text": "hola",
            "incoming_name": "Prueba",
        },
    )

    body = _body(response)
    assert response.status_code == 200
    assert body["assistant_paused"] is True
    assert body["reply_text"] == ""
    assert body["intent"] == "assistant_paused"
    assert body["conversation_id"] == 25
    assert body["prospect_id"] == 10
    assert calls["save_count"] == 2


def test_process_inbound_uses_ai_and_returns_contract(monkeypatch):
    db = DummyDB()

    conversation = SimpleNamespace(
        id=26,
        assistant_paused=False,
        lead_temperature="cold",
        external_chat_id="",
        conversation_type=SimpleNamespace(value="NUEVO_PROSPECTO"),
        commercial_stage=None,
        status=None,
        updated_at=None,
    )

    prospect = SimpleNamespace(
        id=11,
        full_name="Prueba",
        email="",
        phone="5493870000000",
        status=SimpleNamespace(value="NUEVO"),
        interest_summary="",
    )

    monkeypatch.setattr(svc, "normalize_phone", lambda phone: "5493870000000")
    monkeypatch.setattr(svc, "find_student_by_phone", lambda db, phone: None)
    monkeypatch.setattr(
        svc,
        "find_or_create_prospect",
        lambda db, name, phone, email, **kwargs: prospect,
    )
    monkeypatch.setattr(svc, "find_or_create_conversation", lambda **kwargs: conversation)
    monkeypatch.setattr(svc, "save_conversation_message", lambda **kwargs: None)
    monkeypatch.setattr(svc, "build_recent_messages", lambda db, conversation_id, limit=10: [])
    monkeypatch.setattr(svc, "get_trz_knowledge", lambda db: {"ok": True})
    monkeypatch.setattr(svc, "infer_commercial_stage", lambda **kwargs: "CALIFICADO")
    monkeypatch.setattr(svc, "create_handoff_action", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        svc,
        "call_openai_agent",
        lambda payload, fallback_fn: {
            "reply_text": "Te paso opciones de membresía.",
            "intent": "price_request",
            "confidence": 0.86,
            "should_create_task": False,
            "should_handoff_human": False,
            "lead_temperature": "warm",
            "handoff_reason": "",
        },
    )

    response = svc.process_inbound_message(
        db,
        payload={
            "incoming_phone": "5493870000000",
            "incoming_text": "quiero saber precios",
            "incoming_name": "Prueba",
        },
    )

    body = _body(response)
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["conversation_id"] == 26
    assert body["intent"] == "price_request"
    assert body["reply_text"] == "Te paso opciones de membresía."
    assert body["should_handoff_human"] is False
    assert body["prospect_id"] == 11
    assert body["followup_id"] is None


def test_process_inbound_blocks_non_safe_handoff(monkeypatch):
    db = DummyDB()

    conversation = SimpleNamespace(
        id=27,
        assistant_paused=False,
        lead_temperature="cold",
        external_chat_id="",
        conversation_type=SimpleNamespace(value="NUEVO_PROSPECTO"),
        commercial_stage=None,
        status=None,
        updated_at=None,
    )

    prospect = SimpleNamespace(
        id=12,
        full_name="Prueba",
        email="",
        phone="5493870000000",
        status=SimpleNamespace(value="NUEVO"),
        interest_summary="",
    )

    handoff_called = {"ok": False}

    monkeypatch.setattr(svc, "normalize_phone", lambda phone: "5493870000000")
    monkeypatch.setattr(svc, "find_student_by_phone", lambda db, phone: None)
    monkeypatch.setattr(
        svc,
        "find_or_create_prospect",
        lambda db, name, phone, email, **kwargs: prospect,
    )
    monkeypatch.setattr(svc, "find_or_create_conversation", lambda **kwargs: conversation)
    monkeypatch.setattr(svc, "save_conversation_message", lambda **kwargs: None)
    monkeypatch.setattr(svc, "build_recent_messages", lambda db, conversation_id, limit=10: [])
    monkeypatch.setattr(svc, "get_trz_knowledge", lambda db: {"ok": True})
    monkeypatch.setattr(svc, "infer_commercial_stage", lambda **kwargs: "INTERESADO")

    def fake_create_handoff_action(*args, **kwargs):
        handoff_called["ok"] = True

    monkeypatch.setattr(svc, "create_handoff_action", fake_create_handoff_action)

    monkeypatch.setattr(
        svc,
        "call_openai_agent",
        lambda payload, fallback_fn: {
            "reply_text": "Respuesta cualquiera.",
            "intent": "general_query",
            "confidence": 0.70,
            "should_create_task": False,
            "should_handoff_human": True,
            "lead_temperature": "warm",
            "handoff_reason": "No debería derivar",
        },
    )

    response = svc.process_inbound_message(
        db,
        payload={
            "incoming_phone": "5493870000000",
            "incoming_text": "hola",
            "incoming_name": "Prueba",
        },
    )

    body = _body(response)
    assert response.status_code == 200
    assert body["intent"] == "general_query"
    assert body["should_handoff_human"] is False
    assert handoff_called["ok"] is False


def test_process_inbound_student_reactivation_path(monkeypatch):
    db = DummyDB()

    student = SimpleNamespace(
        id=7,
        full_name="Alumno Test",
        email="alumno@test.com",
        phone="5493870000000",
    )

    followup = SimpleNamespace(
        id=55,
        kind=SimpleNamespace(value="INACTIVIDAD"),
        status=svc.FollowupStatus.CONTACTADO,
        priority=SimpleNamespace(value="MEDIA"),
        title="Seguimiento",
        contacted_at=None,
        last_action_at=None,
        last_action_type="",
        result_summary="",
    )

    conversation = SimpleNamespace(
        id=28,
        assistant_paused=False,
        lead_temperature="cold",
        external_chat_id="",
        conversation_type=SimpleNamespace(value="REACTIVACION"),
        commercial_stage=None,
        status=None,
        updated_at=None,
    )

    monkeypatch.setattr(svc, "normalize_phone", lambda phone: "5493870000000")
    monkeypatch.setattr(svc, "find_student_by_phone", lambda db, phone: student)
    monkeypatch.setattr(svc, "find_open_followup_for_student", lambda db, student_id: followup)
    monkeypatch.setattr(svc, "find_or_create_conversation", lambda **kwargs: conversation)
    monkeypatch.setattr(svc, "save_conversation_message", lambda **kwargs: None)
    monkeypatch.setattr(svc, "build_recent_messages", lambda db, conversation_id, limit=10: [])
    monkeypatch.setattr(svc, "get_trz_knowledge", lambda db: {"ok": True})
    monkeypatch.setattr(svc, "infer_commercial_stage", lambda **kwargs: "CALIFICADO")
    monkeypatch.setattr(svc, "create_handoff_action", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        svc,
        "call_openai_agent",
        lambda payload, fallback_fn: {
            "reply_text": "Perfecto, te ayudo con eso.",
            "intent": "interes_alto",
            "confidence": 0.82,
            "should_create_task": False,
            "should_handoff_human": False,
            "lead_temperature": "warm",
            "handoff_reason": "",
        },
    )

    response = svc.process_inbound_message(
        db,
        payload={
            "incoming_phone": "5493870000000",
            "incoming_text": "quiero volver",
            "incoming_name": "Alumno Test",
        },
    )

    body = _body(response)
    assert response.status_code == 200
    assert body["student_id"] == 7
    assert body["followup_id"] == 55
    assert body["prospect_id"] is None
    assert followup.status == svc.FollowupStatus.RESPONDIO