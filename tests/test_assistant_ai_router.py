from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers import assistant_ai as router_mod


class DummyScalarResult:
    def __init__(self, value):
        self._value = value

    def all(self):
        return self._value

    def first(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value


class DummyDB:
    def __init__(self, *, rows=None, detail_row=None, messages=None, total=0):
        self.rows = rows
        self.detail_row = detail_row
        self.messages = messages or []
        self.total = total
        self.scalar_calls = 0
        self.scalars_calls = 0

    def scalar(self, stmt):
        self.scalar_calls += 1
        return self.total

    def scalars(self, stmt):
        self.scalars_calls += 1

        if self.rows is not None:
            return DummyScalarResult(self.rows)

        return DummyScalarResult(self.detail_row)


def _fake_me():
    return SimpleNamespace(id=1, role="ADMINISTRADOR", full_name="Admin Test")


def _make_row(
    *,
    row_id=1,
    status="EN_AUTOMATICO",
    paused=False,
    conv_type="NUEVO_PROSPECTO",
    lead_temperature="warm",
):
    return SimpleNamespace(
        id=row_id,
        student_id=None,
        prospect_id=20,
        followup_id=30,
        phone="5493870000000",
        student=None,
        prospect=SimpleNamespace(full_name="Prospecto Test", email="prospecto@test.com"),
        followup=SimpleNamespace(id=30),
        conversation_type=SimpleNamespace(value=conv_type),
        status=SimpleNamespace(value=status),
        assistant_paused=paused,
        intent_last="price_request",
        handoff_reason="",
        lead_temperature=lead_temperature,
        commercial_stage=SimpleNamespace(value="CALIFICADO"),
        last_message_at=None,
        updated_at=None,
    )


def _make_message(*, msg_id=1, inbound=True, sender="PROSPECTO", text="hola"):
    return SimpleNamespace(
        id=msg_id,
        is_inbound=inbound,
        sender_type=SimpleNamespace(value=sender),
        message_text=text,
        intent_detected="general_query",
        delivery_status="OK",
        external_ref="",
        created_at=None,
    )


def _override_admin_conversation_auth():
    """
    Overridea la dependencia real de auth ya enlazada en las rutas
    /admin/conversations* para evitar redirección a /login.
    """
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/admin/conversations"):
            continue

        dependant = getattr(route, "dependant", None)
        if not dependant:
            continue

        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if call and call is not router_mod.get_db:
                app.dependency_overrides[call] = lambda: _fake_me()


def test_conversations_list_renders():
    row = _make_row(row_id=10)
    db = DummyDB(rows=[row], total=1)

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_conversation_auth()

    client = TestClient(app)
    response = client.get("/admin/conversations", follow_redirects=False)
    assert response.status_code == 200
    assert "Conversaciones" in response.text
    assert "Prospecto Test" in response.text or "5493870000000" in response.text

    app.dependency_overrides.clear()


def test_conversations_list_accepts_filters():
    row = _make_row(row_id=11, status="DERIVADA_A_HUMANO", paused=True, lead_temperature="hot")
    db = DummyDB(rows=[row], total=1)

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_conversation_auth()

    client = TestClient(app)
    response = client.get(
        "/admin/conversations?status=DERIVADA_A_HUMANO&paused=1&q=549387&page=2&page_size=20",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "DERIVADA_A_HUMANO" in response.text
    assert "Conversaciones" in response.text

    app.dependency_overrides.clear()


def test_conversation_detail_renders(monkeypatch):
    row = _make_row(row_id=21)
    db = DummyDB(detail_row=row)

    detail_ctx = {
        "messages": [_make_message()],
        "contact_name": "Prospecto Test",
        "contact_email": "prospecto@test.com",
        "contact_phone": "5493870000000",
        "suggestions": ["Enviar precios"],
        "commercial_summary": {
            "commercial_stage": "CALIFICADO",
            "lead_temperature": "warm",
            "intent_last": "price_request",
            "handoff_reason": "",
            "total_messages": 1,
            "inbound_messages": 1,
            "outbound_messages": 0,
        },
    }

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_conversation_auth()
    monkeypatch.setattr(router_mod, "build_conversation_detail_context", lambda db, row: detail_ctx)

    client = TestClient(app)
    response = client.get("/admin/conversations/21", follow_redirects=False)

    assert response.status_code == 200
    assert "Conversación #21" in response.text
    assert "Prospecto Test" in response.text
    assert "Enviar precios" in response.text

    app.dependency_overrides.clear()


def test_conversation_detail_404():
    db = DummyDB(detail_row=None)

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_conversation_auth()

    client = TestClient(app)
    response = client.get("/admin/conversations/999", follow_redirects=False)

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversación no encontrada"

    app.dependency_overrides.clear()


def test_conversation_messages_partial_renders(monkeypatch):
    row = _make_row(row_id=31)
    messages = [
        _make_message(msg_id=1, inbound=True, sender="PROSPECTO", text="Hola"),
        _make_message(msg_id=2, inbound=False, sender="BOT", text="Te ayudo con eso"),
    ]

    app.dependency_overrides[router_mod.get_db] = lambda: object()
    _override_admin_conversation_auth()

    monkeypatch.setattr(router_mod, "get_conversation_or_404", lambda db, conversation_id: row)
    monkeypatch.setattr(router_mod, "get_conversation_messages", lambda db, row_id: messages)

    client = TestClient(app)
    response = client.get("/admin/conversations/31/messages", follow_redirects=False)

    assert response.status_code == 200
    assert "Hola" in response.text
    assert "Te ayudo con eso" in response.text

    app.dependency_overrides.clear()