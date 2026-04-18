from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.models import Role
from app.routers import admin_users as router_mod


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


def _fake_me_admin():
    return SimpleNamespace(
        id=1,
        email="admin@test.com",
        role=Role.ADMINISTRADOR,
        full_name="Admin Root",
        is_active=True,
    )


def _fake_me_administrativo():
    return SimpleNamespace(
        id=2,
        email="administrativo@test.com",
        role=Role.ADMINISTRATIVO,
        full_name="Admin Operativo",
        is_active=True,
    )


def _override_users_auth(fake_user):
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/admin/users"):
            continue

        dependant = getattr(route, "dependant", None)
        if not dependant:
            continue

        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if call and call is not router_mod.get_db:
                app.dependency_overrides[call] = lambda fake_user=fake_user: fake_user


def _make_user(
    user_id=10,
    *,
    email="user@test.com",
    role=Role.ALUMNO,
    is_active=True,
    first_name="Nombre",
    last_name="Apellido",
    dni="12345678",
):
    return SimpleNamespace(
        id=user_id,
        email=email,
        role=role,
        is_active=is_active,
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name} {last_name}".strip(),
        dni=dni,
        birth_date=None,
        age=None,
        address="",
        phone="",
        emergency_contact_name="",
        emergency_contact_phone="",
        password_hash="hashed",
        must_change_password=False,
    )


def test_users_list_renders_with_filters_and_pagination():
    db = DummyDB()
    db.scalar_queue = [1]
    db.scalars_queue = [[_make_user(user_id=50, email="alumno@test.com")]]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_users_auth(_fake_me_admin())

    client = TestClient(app)
    response = client.get(
        "/admin/users?q=alumno&role=ALUMNO&is_active=true&page=1&page_size=20",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "Usuarios" in response.text
    assert "alumno@test.com" in response.text
    assert "Página 1 de 1" in response.text

    app.dependency_overrides.clear()


def test_create_user_success():
    db = DummyDB()
    db.scalar_queue = [None, None]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_users_auth(_fake_me_admin())

    client = TestClient(app)
    response = client.post(
        "/admin/users/new",
        data={
            "email": "nuevo@test.com",
            "password": "123456",
            "role": "ALUMNO",
            "first_name": "Nuevo",
            "last_name": "Usuario",
            "dni": "30111222",
            "birth_date": "1990-01-10",
            "address": "Salta",
            "phone": "387000000",
            "emergency_contact_name": "Madre",
            "emergency_contact_phone": "387111111",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/users"
    assert len(db.added) == 1
    created = db.added[0]
    assert created.email == "nuevo@test.com"
    assert created.full_name == "Nuevo Usuario"
    assert created.role == Role.ALUMNO
    assert db.commits == 1

    app.dependency_overrides.clear()


def test_create_user_duplicate_email_returns_400():
    db = DummyDB()
    db.scalar_queue = [_make_user(user_id=99), None]

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_users_auth(_fake_me_admin())

    client = TestClient(app)
    response = client.post(
        "/admin/users/new",
        data={
            "email": "duplicado@test.com",
            "password": "123456",
            "role": "ALUMNO",
            "first_name": "Dup",
            "last_name": "Licado",
            "dni": "30111222",
            "birth_date": "",
            "address": "",
            "phone": "",
            "emergency_contact_name": "",
            "emergency_contact_phone": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Ese email ya existe." in response.text

    app.dependency_overrides.clear()


def test_administrativo_cannot_assign_admin_role():
    db = DummyDB()

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_users_auth(_fake_me_administrativo())

    client = TestClient(app)
    response = client.post(
        "/admin/users/new",
        data={
            "email": "admin2@test.com",
            "password": "123456",
            "role": "ADMINISTRADOR",
            "first_name": "Admin",
            "last_name": "Dos",
            "dni": "30111222",
            "birth_date": "",
            "address": "",
            "phone": "",
            "emergency_contact_name": "",
            "emergency_contact_phone": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "No tenés permisos para asignar ese rol." in response.text

    app.dependency_overrides.clear()


def test_administrativo_cannot_reset_admin_password():
    db = DummyDB()
    admin_target = _make_user(user_id=20, email="root@test.com", role=Role.ADMINISTRADOR)
    db.objects[(router_mod.User, 20)] = admin_target

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_users_auth(_fake_me_administrativo())

    client = TestClient(app)
    response = client.get("/admin/users/20/reset-password", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/users"

    app.dependency_overrides.clear()


def test_admin_reset_password_marks_must_change_password():
    db = DummyDB()
    target = _make_user(user_id=30, email="profe@test.com", role=Role.PROFESOR)
    db.objects[(router_mod.User, 30)] = target

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_users_auth(_fake_me_admin())

    client = TestClient(app)
    response = client.post("/admin/users/30/reset-password", follow_redirects=False)

    assert response.status_code == 200
    assert "Contraseña temporal generada" in response.text
    assert target.must_change_password is True
    assert target.is_active is True
    assert db.commits == 1

    app.dependency_overrides.clear()


def test_toggle_self_is_blocked():
    db = DummyDB()
    me = _fake_me_admin()
    myself = _make_user(user_id=1, email=me.email, role=Role.ADMINISTRADOR, is_active=True)
    db.objects[(router_mod.User, 1)] = myself

    app.dependency_overrides[router_mod.get_db] = lambda: db
    _override_users_auth(me)

    client = TestClient(app)
    response = client.post("/admin/users/1/toggle", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/users"
    assert myself.is_active is True
    assert db.commits == 0

    app.dependency_overrides.clear()