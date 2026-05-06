from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.models import Role
from app.routers import profesor as profesor_router
from app.routers import auth as auth_router
from app.deps import get_current_user


class DummyScalarResult:
    def __init__(self, value):
        self._value = value

    def all(self):
        return self._value

    def first(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value


class DummyQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *args, **kwargs):
        return self

    def update(self, values):
        self.db.updated = values
        return 1


class DummyDB:
    def __init__(self):
        self.objects = {}
        self.scalar_queue = []
        self.scalars_queue = []
        self.commits = 0
        self.rollbacks = 0
        self.updated = None

    def get(self, model, obj_id):
        return self.objects.get((model, obj_id))

    def scalar(self, stmt):
        if self.scalar_queue:
            return self.scalar_queue.pop(0)
        return None

    def scalars(self, stmt):
        if self.scalars_queue:
            return DummyScalarResult(self.scalars_queue.pop(0))
        return DummyScalarResult([])

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def query(self, model):
        return DummyQuery(self)


def _fake_prof():
    return SimpleNamespace(
        id=10,
        email="profe@test.com",
        role=Role.PROFESOR,
        is_active=True,
        full_name="Profe Test",
    )


def _fake_alumno():
    return SimpleNamespace(
        id=20,
        email="alumno@test.com",
        role=Role.ALUMNO,
        is_active=True,
        full_name="Alumno Test",
    )


def _fake_admin():
    return SimpleNamespace(
        id=1,
        email="admin@test.com",
        role=Role.ADMINISTRADOR,
        is_active=True,
        full_name="Admin Test",
    )


def _override_prof_auth(fake_user):
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/profesor"):
            continue

        dependant = getattr(route, "dependant", None)
        if not dependant:
            continue

        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if call and call is not profesor_router.get_db:
                app.dependency_overrides[call] = lambda fake_user=fake_user: fake_user


def test_admin_can_open_profesor_home():
    app.dependency_overrides[get_current_user] = lambda: _fake_admin()
    client = TestClient(app)

    response = client.get("/profesor", follow_redirects=False)

    assert response.status_code == 200


def test_professor_cannot_assign_routine_to_unlinked_student():
    db = DummyDB()
    prof = _fake_prof()

    routine = SimpleNamespace(id=100, professor_id=prof.id)
    foreign_student = _fake_alumno()

    db.objects[(profesor_router.Routine, 100)] = routine
    db.objects[(profesor_router.User, foreign_student.id)] = foreign_student
    db.scalar_queue = [None]  # no link in profesor_alumnos

    app.dependency_overrides[profesor_router.get_db] = lambda: db
    _override_prof_auth(prof)

    client = TestClient(app)
    response = client.post(
        "/profesor/routines/100/assign",
        data={"student_id": foreign_student.id, "start_date": ""},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/profesor/routines/100"
    assert db.commits == 0

    app.dependency_overrides.clear()


def test_professor_cannot_assign_global_endpoint_to_unlinked_student():
    db = DummyDB()
    prof = _fake_prof()

    routine = SimpleNamespace(id=200, professor_id=prof.id)
    foreign_student = _fake_alumno()

    db.objects[(profesor_router.Routine, 200)] = routine
    db.objects[(profesor_router.User, foreign_student.id)] = foreign_student
    db.scalar_queue = [None]

    app.dependency_overrides[profesor_router.get_db] = lambda: db
    _override_prof_auth(prof)

    client = TestClient(app)
    response = client.post(
        "/profesor/assignments",
        data={"student_id": foreign_student.id, "routine_id": 200, "start_date": ""},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/profesor/assignments"
    assert db.commits == 0

    app.dependency_overrides.clear()


def test_professor_cannot_deactivate_unlinked_student_assignment():
    db = DummyDB()
    prof = _fake_prof()
    foreign_student = _fake_alumno()

    db.objects[(profesor_router.User, foreign_student.id)] = foreign_student
    db.scalar_queue = [None]

    app.dependency_overrides[profesor_router.get_db] = lambda: db
    _override_prof_auth(prof)

    client = TestClient(app)
    response = client.post(
        f"/profesor/assignments/{foreign_student.id}/deactivate",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/profesor/assignments"
    assert db.commits == 0

    app.dependency_overrides.clear()