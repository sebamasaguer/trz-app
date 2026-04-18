from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers import admin_cash as router_mod

from datetime import datetime

def _fake_me():
    return SimpleNamespace(id=1, role="ADMINISTRADOR", full_name="Admin Caja")


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
        self.scalar_value = 0
        self.scalars_queue = []
        self.added = []
        self.commits = 0
        self.flushed = 0

    def scalar(self, stmt):
        return self.scalar_value

    def scalars(self, stmt):
        if self.scalars_queue:
            return DummyScalarResult(self.scalars_queue.pop(0))
        return DummyScalarResult([])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def flush(self):
        self.flushed += 1


def _override_admin_cash_auth():
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/admin/caja"):
            continue

        dependant = getattr(route, "dependant", None)
        if not dependant:
            continue

        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if call and call is not router_mod.get_db:
                app.dependency_overrides[call] = lambda: _fake_me()


def test_cash_dashboard_renders(monkeypatch):
    db = DummyDB()
    db.scalar_value = 1
    db.scalars_queue = [
        [
            SimpleNamespace(
                movement_date=None,
                entry_type=SimpleNamespace(value="INGRESO"),
                concept="Cuota",
                notes="",
                amount=1000,
                status=router_mod.CashPaymentStatus.ACREDITADO,
                payment_method=None,
                student=None,
                created_by=None,
                category="MEMBRESIA",
            )
        ],
        [],
    ]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_cash_auth()

    monkeypatch.setattr(router_mod, "get_open_cash_session", lambda db: None)

    client = TestClient(app)
    response = client.get("/admin/caja", follow_redirects=False)

    assert response.status_code == 200
    assert "Caja" in response.text
    assert "Cuota" in response.text

    app.dependency_overrides.clear()


def test_cash_open_form_renders(monkeypatch):
    db = DummyDB()

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_cash_auth()
    monkeypatch.setattr(router_mod, "get_open_cash_session", lambda db: None)

    client = TestClient(app)
    response = client.get("/admin/caja/open", follow_redirects=False)

    assert response.status_code == 200
    assert "Caja" in response.text or "Abrir" in response.text

    app.dependency_overrides.clear()


def test_cash_open_post_redirects_if_session_exists(monkeypatch):
    db = DummyDB()

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_cash_auth()
    monkeypatch.setattr(router_mod, "get_open_cash_session", lambda db: SimpleNamespace(id=99))

    client = TestClient(app)
    response = client.post(
        "/admin/caja/open",
        data={"opening_amount": "1000", "description": "Apertura"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "/admin/caja?error=" in response.headers["location"]

    app.dependency_overrides.clear()


def test_cash_expense_post_redirects_if_no_open_session(monkeypatch):
    db = DummyDB()

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_cash_auth()
    monkeypatch.setattr(router_mod, "get_open_cash_session", lambda db: None)

    client = TestClient(app)
    response = client.post(
        "/admin/caja/expense/new",
        data={
            "concept": "Compra insumos",
            "amount": "500",
            "category": "OTROS",
            "payment_method": "",
            "movement_date": "",
            "movement_time": "",
            "description": "Test",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "/admin/caja?error=No+hay+una+caja+abierta" == response.headers["location"]

    app.dependency_overrides.clear()


def test_cash_close_post_redirects_if_no_open_session(monkeypatch):
    db = DummyDB()

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_cash_auth()
    monkeypatch.setattr(router_mod, "get_open_cash_session", lambda db: None)

    client = TestClient(app)
    response = client.post(
        "/admin/caja/close",
        data={"real_closing_amount": "1000", "notes": "Cierre"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "/admin/caja?error=No+hay+una+caja+abierta" == response.headers["location"]

    app.dependency_overrides.clear()


def test_cash_report_renders(monkeypatch):
    db = DummyDB()
    db.scalars_queue = [
        [
            SimpleNamespace(
                movement_date=datetime(2026, 4, 15, 10, 30),
                entry_type=router_mod.CashEntryType.INGRESO,
                status=router_mod.CashPaymentStatus.ACREDITADO,
                amount=1200,
                student=None,
                created_by=None,
                session=None,
                payment_method=None,
                category="MEMBRESIA",
                concept="Cuota",
                notes="",
            )
        ],
        [],
    ]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_cash_auth()

    client = TestClient(app)
    response = client.get("/admin/caja/report", follow_redirects=False)

    assert response.status_code == 200
    assert "Cuota" in response.text or "Reporte" in response.text

    app.dependency_overrides.clear()