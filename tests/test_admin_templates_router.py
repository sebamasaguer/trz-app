from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.models import MessageTemplateChannel, FollowupKind, Role
from app.routers import admin_templates as router_mod


class DummyScalarResult:
    def __init__(self, value):
        self._value = value

    def all(self):
        return self._value


class DummyDB:
    def __init__(self):
        self.scalar_queue = []
        self.scalars_queue = []
        self.objects = {}
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def scalar(self, stmt):
        if self.scalar_queue:
            return self.scalar_queue.pop(0)
        return 0

    def scalars(self, stmt):
        if self.scalars_queue:
            return DummyScalarResult(self.scalars_queue.pop(0))
        return DummyScalarResult([])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def get(self, model, obj_id):
        return self.objects.get((model, obj_id))


def _fake_me():
    return SimpleNamespace(
        id=1,
        email="admin@test.com",
        role=Role.ADMINISTRADOR,
        full_name="Admin Root",
        is_active=True,
    )


def _override_templates_auth(fake_user):
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/admin/templates"):
            continue

        dependant = getattr(route, "dependant", None)
        if not dependant:
            continue

        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if call and call is not router_mod.get_db:
                app.dependency_overrides[call] = lambda fake_user=fake_user: fake_user


def _make_template(
    template_id=10,
    *,
    name="General WhatsApp",
    kind=FollowupKind.GENERAL,
    channel=MessageTemplateChannel.WHATSAPP,
    subject="Hola",
    body="Cuerpo base",
    is_active=True,
):
    return SimpleNamespace(
        id=template_id,
        name=name,
        kind=kind,
        channel=channel,
        subject=subject,
        body=body,
        is_active=is_active,
    )


def test_templates_list_renders_with_filters_and_pagination():
    db = DummyDB()
    db.scalar_queue = [1]
    db.scalars_queue = [[_make_template()]]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_templates_auth(_fake_me())

    client = TestClient(app)
    response = client.get(
        "/admin/templates?q=General&kind=GENERAL&channel=WHATSAPP&is_active=true&page=1&page_size=20",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "Plantillas de mensaje" in response.text
    assert "General WhatsApp" in response.text
    assert "Página 1 de 1" in response.text

    app.dependency_overrides.clear()


def test_create_template_success():
    db = DummyDB()
    db.scalar_queue = [None]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_templates_auth(_fake_me())

    client = TestClient(app)
    response = client.post(
        "/admin/templates/new",
        data={
            "name": "Nueva plantilla",
            "kind": "GENERAL",
            "channel": "EMAIL",
            "subject": "Asunto",
            "body": "Texto del cuerpo",
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/templates"
    assert len(db.added) == 1
    assert db.added[0].name == "Nueva plantilla"
    assert db.commits == 1

    app.dependency_overrides.clear()


def test_create_template_duplicate_name_returns_400():
    db = DummyDB()
    db.scalar_queue = [_make_template(template_id=99, name="Duplicada")]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_templates_auth(_fake_me())

    client = TestClient(app)
    response = client.post(
        "/admin/templates/new",
        data={
            "name": "Duplicada",
            "kind": "GENERAL",
            "channel": "EMAIL",
            "subject": "Asunto",
            "body": "Texto del cuerpo",
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Ya existe una plantilla con ese nombre." in response.text

    app.dependency_overrides.clear()


def test_edit_template_success():
    db = DummyDB()
    row = _make_template(template_id=12, name="Base")
    db.objects[(router_mod.MessageTemplate, 12)] = row
    db.scalar_queue = [None]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_templates_auth(_fake_me())

    client = TestClient(app)
    response = client.post(
        "/admin/templates/12/edit",
        data={
            "name": "Base actualizada",
            "kind": "MOROSIDAD",
            "channel": "WHATSAPP",
            "subject": "Nuevo asunto",
            "body": "Nuevo cuerpo",
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/templates"
    assert row.name == "Base actualizada"
    assert row.kind == FollowupKind.MOROSIDAD
    assert row.channel == MessageTemplateChannel.WHATSAPP
    assert db.commits == 1

    app.dependency_overrides.clear()