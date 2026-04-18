from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers import admin_memberships as router_mod


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
    def __init__(self):
        self.scalar_values = []
        self.scalars_queue = []
        self.objects = {}
        self.added = []
        self.commits = 0
        self.deleted = []

    def scalar(self, stmt):
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return 0

    def scalars(self, stmt):
        if self.scalars_queue:
            return DummyScalarResult(self.scalars_queue.pop(0))
        return DummyScalarResult([])

    def get(self, model, obj_id):
        return self.objects.get((model, obj_id))

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commits += 1

    def execute(self, stmt):
        class DummyExecResult:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        if self.scalars_queue:
            return DummyExecResult(self.scalars_queue.pop(0))
        return DummyExecResult([])

    def query(self, model):
        class DummyQuery:
            def filter(self, *args, **kwargs):
                return self

            def update(self, *args, **kwargs):
                return 1

        return DummyQuery()


def _fake_me():
    return SimpleNamespace(id=1, role="ADMINISTRADOR", full_name="Admin Memberships")


def _override_admin_memberships_auth():
    for route in app.routes:
        path = getattr(route, "path", "")
        if not (
            path.startswith("/admin/memberships")
            or path.startswith("/admin/qr")
        ):
            continue

        dependant = getattr(route, "dependant", None)
        if not dependant:
            continue

        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if call and call is not router_mod.get_db:
                app.dependency_overrides[call] = lambda: _fake_me()


def _make_membership(mid=10, name="Plan Funcional", active=True):
    return SimpleNamespace(
        id=mid,
        name=name,
        kind=SimpleNamespace(value="FUNCIONAL"),
        funcional_classes=12,
        musculacion_classes=None,
        funcional_unlimited=False,
        musculacion_unlimited=False,
        is_active=active,
    )


def _make_price(membership_id, method, amount):
    return SimpleNamespace(
        membership_id=membership_id,
        payment_method=SimpleNamespace(value=method),
        amount=amount,
    )


def test_memberships_list_renders_with_pagination():
    db = DummyDB()
    db.scalar_values = [1]
    db.scalars_queue = [
        [_make_membership(mid=10, name="Plan Test")],
        [_make_price(10, "LISTA", 70000), _make_price(10, "EFECTIVO", 65000)],
    ]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_memberships_auth()

    client = TestClient(app)
    response = client.get(
        "/admin/memberships?q=Plan&page=1&page_size=20",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "Membresías (Mensual)" in response.text
    assert "Plan Test" in response.text
    assert "Total:" in response.text
    assert "Página <strong>1</strong> de <strong>1</strong>" in response.text

    app.dependency_overrides.clear()


def test_membership_new_redirects_and_commits_twice():
    db = DummyDB()

    def fake_add(obj):
        if getattr(obj, "id", None) is None:
            obj.id = 99
        db.added.append(obj)

    db.add = fake_add

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_memberships_auth()

    client = TestClient(app)
    response = client.post(
        "/admin/memberships/new",
        data={
            "name": "Plan Nuevo",
            "kind": "FUNCIONAL",
            "funcional_classes": "8",
            "musculacion_classes": "0",
            "funcional_unlimited": "",
            "musculacion_unlimited": "",
            "price_lista": "70000",
            "price_efectivo": "65000",
            "price_transferencia": "68000",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/memberships"
    assert db.commits == 2
    assert len(db.added) >= 2

    app.dependency_overrides.clear()


def test_membership_edit_removes_empty_price_and_redirects():
    db = DummyDB()
    item = _make_membership(mid=25, name="Plan Editar")
    db.objects[(router_mod.Membership, 25)] = item
    db.scalars_queue = [[
        SimpleNamespace(
            membership_id=25,
            payment_method=router_mod.PaymentMethod.LISTA,
            amount=70000,
        ),
        SimpleNamespace(
            membership_id=25,
            payment_method=router_mod.PaymentMethod.EFECTIVO,
            amount=65000,
        ),
    ]]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_memberships_auth()

    client = TestClient(app)
    response = client.post(
        "/admin/memberships/25/edit",
        data={
            "name": "Plan Editado",
            "kind": "FUNCIONAL",
            "funcional_classes": "10",
            "musculacion_classes": "0",
            "funcional_unlimited": "",
            "musculacion_unlimited": "",
            "price_lista": "",
            "price_efectivo": "60000",
            "price_transferencia": "",
            "is_active": "true",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/memberships"
    assert item.name == "Plan Editado"
    assert db.commits == 1
    assert len(db.deleted) == 1

    app.dependency_overrides.clear()