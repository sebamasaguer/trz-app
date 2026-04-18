from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers import admin_payments as router_mod


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
        self.flushed = 0
        self.commits = 0
        self.objects = {}

    def scalar(self, stmt):
        return self.scalar_value

    def scalars(self, stmt):
        if self.scalars_queue:
            return DummyScalarResult(self.scalars_queue.pop(0))
        return DummyScalarResult([])

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushed += 1

    def commit(self):
        self.commits += 1

    def get(self, model, obj_id):
        return self.objects.get((model, obj_id))


def _fake_me():
    return SimpleNamespace(id=1, role="ADMINISTRADOR", full_name="Admin Payments")


def _override_admin_payments_auth():
    for route in app.routes:
        path = getattr(route, "path", "")
        if not (path.startswith("/admin/caja") or path.startswith("/admin/payments") or path.startswith("/admin/alumnos/")):
            continue

        dependant = getattr(route, "dependant", None)
        if not dependant:
            continue

        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if call and call is not router_mod.get_db:
                app.dependency_overrides[call] = lambda: _fake_me()


def _make_student(student_id=10):
    return SimpleNamespace(
        id=student_id,
        role=SimpleNamespace(value="ALUMNO"),
        full_name="Alumno Test",
        email="alumno@test.com",
    )


def _make_assignment(assignment_id=30, student_id=10, membership_id=50):
    return SimpleNamespace(
        id=assignment_id,
        student_id=student_id,
        membership_id=membership_id,
        membership=SimpleNamespace(id=membership_id, name="Plan Test"),
    )


def _make_price(method, amount):
    return SimpleNamespace(
        payment_method=SimpleNamespace(value=method),
        amount=amount,
    )


def _make_cash_row(row_id=1, student_id=10, status=None):
    return SimpleNamespace(
        id=row_id,
        session_id=99,
        student_id=student_id,
        entry_type=router_mod.CashEntryType.INGRESO,
        status=status or router_mod.CashPaymentStatus.PENDIENTE,
        amount=1500,
        concept="Cuota abril",
        description="Pago",
        category="MEMBRESIA",
        payment_method=router_mod.PaymentMethod.TRANSFERENCIA,
        paid_at=None,
        movement_date=None,
        period_yyyymm="2026-04",
        receipt_image_path=None,
        created_by=SimpleNamespace(full_name="Admin"),
        student=SimpleNamespace(id=student_id, full_name="Alumno Test", email="alumno@test.com"),
        membership_assignment=SimpleNamespace(membership=SimpleNamespace(name="Plan Test")),
    )


def test_cash_list_renders_with_filters():
    db = DummyDB()
    db.scalar_value = 1
    db.scalars_queue = [[_make_cash_row()]]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_payments_auth()

    client = TestClient(app)
    response = client.get(
        "/admin/caja?q=abril&period=2026-04&status=PENDIENTE&payment_method=TRANSFERENCIA&page=1&page_size=50",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "Caja" in response.text
    assert "Cuota abril" in response.text

    app.dependency_overrides.clear()


def test_payment_confirm_updates_status_and_redirects(monkeypatch):
    db = DummyDB()
    row = _make_cash_row(row_id=15, student_id=10, status=router_mod.CashPaymentStatus.PENDIENTE)
    db.objects[(router_mod.CashMovement, 15)] = row

    sync_called = {"ok": False}

    def fake_sync(db_obj, session_id):
        sync_called["ok"] = True

    monkeypatch.setattr(router_mod, "_sync_cash_session_totals", fake_sync)

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_payments_auth()

    client = TestClient(app)
    response = client.post("/admin/payments/15/confirm", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/alumnos/10/payments"
    assert row.status == router_mod.CashPaymentStatus.ACREDITADO
    assert sync_called["ok"] is True
    assert db.commits == 1

    app.dependency_overrides.clear()


def test_payment_cancel_updates_status_and_redirects(monkeypatch):
    db = DummyDB()
    row = _make_cash_row(row_id=16, student_id=10, status=router_mod.CashPaymentStatus.PENDIENTE)
    db.objects[(router_mod.CashMovement, 16)] = row

    sync_called = {"ok": False}

    def fake_sync(db_obj, session_id):
        sync_called["ok"] = True

    monkeypatch.setattr(router_mod, "_sync_cash_session_totals", fake_sync)

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_payments_auth()

    client = TestClient(app)
    response = client.post("/admin/payments/16/cancel", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/alumnos/10/payments"
    assert row.status == router_mod.CashPaymentStatus.ANULADO
    assert sync_called["ok"] is True
    assert db.commits == 1

    app.dependency_overrides.clear()


def test_payment_new_do_success(monkeypatch):
    db = DummyDB()

    student = _make_student(student_id=10)
    assignment = _make_assignment(assignment_id=30, student_id=10, membership_id=50)

    db.objects[(router_mod.User, 10)] = student
    db.objects[(router_mod.MembershipAssignment, 30)] = assignment

    db.scalars_queue = [
        [assignment],  # assignments list
        [_make_price("TRANSFERENCIA", 2500)],  # assignment_prices
        [_make_price("TRANSFERENCIA", 2500)],  # prices_map final
    ]

    monkeypatch.setattr(router_mod, "_get_open_cash_session", lambda db: SimpleNamespace(id=99))
    monkeypatch.setattr(router_mod, "_save_receipt", lambda receipt_file: None)

    sync_called = {"ok": False}

    def fake_sync(db_obj, session_id):
        sync_called["ok"] = True

    monkeypatch.setattr(router_mod, "_sync_cash_session_totals", fake_sync)

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_payments_auth()

    client = TestClient(app)
    response = client.post(
        "/admin/alumnos/10/payments/new",
        data={
            "concept": "Pago membresía",
            "description": "Pago test",
            "amount": "",
            "payment_method": "TRANSFERENCIA",
            "membership_assignment_id": "30",
            "period_yyyymm": "2026-04",
            "receipt_note": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/alumnos/10/payments"
    assert len(db.added) == 1
    assert db.flushed == 1
    assert db.commits == 1
    assert sync_called["ok"] is False  # transferencia entra pendiente

    app.dependency_overrides.clear()


def test_payment_new_do_invalid_payment_method():
    db = DummyDB()

    student = _make_student(student_id=10)
    assignment = _make_assignment(assignment_id=30, student_id=10, membership_id=50)

    db.objects[(router_mod.User, 10)] = student
    db.scalars_queue = [
        [assignment],
        [_make_price("EFECTIVO", 2000)],
    ]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_payments_auth()

    client = TestClient(app)
    response = client.post(
        "/admin/alumnos/10/payments/new",
        data={
            "concept": "Pago membresía",
            "description": "",
            "amount": "",
            "payment_method": "METODO_INVALIDO",
            "membership_assignment_id": "30",
            "period_yyyymm": "2026-04",
            "receipt_note": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Método de pago inválido" in response.text

    app.dependency_overrides.clear()


def test_payment_new_do_invalid_assignment():
    db = DummyDB()

    student = _make_student(student_id=10)
    db.objects[(router_mod.User, 10)] = student

    db.scalars_queue = [
        [],  # assignments list vacío
    ]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_payments_auth()

    client = TestClient(app)
    response = client.post(
        "/admin/alumnos/10/payments/new",
        data={
            "concept": "Pago membresía",
            "description": "",
            "amount": "",
            "payment_method": "TRANSFERENCIA",
            "membership_assignment_id": "",
            "period_yyyymm": "2026-04",
            "receipt_note": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Debés seleccionar una asignación de membresía válida." in response.text

    app.dependency_overrides.clear()

def test_payment_confirm_already_accredited(monkeypatch):
    db = DummyDB()
    row = _make_cash_row(row_id=25, student_id=10, status=router_mod.CashPaymentStatus.ACREDITADO)
    db.objects[(router_mod.CashMovement, 25)] = row

    sync_called = {"ok": False}

    def fake_sync(db_obj, session_id):
        sync_called["ok"] = True

    monkeypatch.setattr(router_mod, "_sync_cash_session_totals", fake_sync)

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_payments_auth()

    client = TestClient(app)
    response = client.post("/admin/payments/25/confirm", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/alumnos/10/payments"
    assert row.status == router_mod.CashPaymentStatus.ACREDITADO
    assert sync_called["ok"] is False
    assert db.commits == 0

    app.dependency_overrides.clear()


def test_payment_cancel_already_cancelled(monkeypatch):
    db = DummyDB()
    row = _make_cash_row(row_id=26, student_id=10, status=router_mod.CashPaymentStatus.ANULADO)
    db.objects[(router_mod.CashMovement, 26)] = row

    sync_called = {"ok": False}

    def fake_sync(db_obj, session_id):
        sync_called["ok"] = True

    monkeypatch.setattr(router_mod, "_sync_cash_session_totals", fake_sync)

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_admin_payments_auth()

    client = TestClient(app)
    response = client.post("/admin/payments/26/cancel", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/alumnos/10/payments"
    assert row.status == router_mod.CashPaymentStatus.ANULADO
    assert sync_called["ok"] is False
    assert db.commits == 0

    app.dependency_overrides.clear()