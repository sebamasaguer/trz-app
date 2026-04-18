from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import Base, get_db
from app.deps import get_current_user
from app.models import (
    User,
    Role,
    ProfesorAlumno,
    Routine,
    StudentFollowup,
    FollowupKind,
    FollowupStatus,
    FollowupPriority,
    FollowupChannel,
)


@pytest.fixture
def smoke_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)

    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _clear_overrides():
    app.dependency_overrides.clear()


def _fake_auth_user(*, user_id: int, role: Role, email: str):
    return SimpleNamespace(
        id=user_id,
        email=email,
        role=role,
        is_active=True,
        full_name=email,
    )


def _set_auth(SessionLocal, auth_user):
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: auth_user


def _make_user(
    db_session,
    *,
    email: str,
    role: Role,
    first_name: str,
    last_name: str = "Smoke",
    is_active: bool = True,
):
    row = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name} {last_name}",
        password_hash="hash",
        role=role,
        is_active=is_active,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _make_professor_student_link(db_session, *, professor_id: int, student_id: int):
    row = ProfesorAlumno(
        profesor_id=professor_id,
        alumno_id=student_id,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _make_routine(db_session, *, professor_id: int, title: str = "Rutina Smoke"):
    row = Routine(
        professor_id=professor_id,
        title=title,
        notes="",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _make_followup(db_session, *, admin_id: int, student_id: int):
    row = StudentFollowup(
        student_id=student_id,
        created_by_id=admin_id,
        kind=FollowupKind.GENERAL,
        status=FollowupStatus.PENDIENTE,
        priority=FollowupPriority.MEDIA,
        channel=FollowupChannel.WHATSAPP,
        title="Seguimiento smoke",
        notes="Smoke integral",
        automation_enabled=True,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_public_routes_smoke():
    client = TestClient(app)

    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert response.json()["ok"] is True

    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 200

    response = client.get("/forgot-password", follow_redirects=False)
    assert response.status_code == 200


def test_admin_critical_pages_smoke(smoke_db):
    seed = smoke_db()
    try:
        admin = _make_user(
            seed,
            email="admin-smoke@test.com",
            role=Role.ADMINISTRADOR,
            first_name="AdminSmoke",
        )
        student = _make_user(
            seed,
            email="alumno-smoke@test.com",
            role=Role.ALUMNO,
            first_name="AlumnoSmoke",
        )
        _make_followup(seed, admin_id=admin.id, student_id=student.id)
    finally:
        seed.close()

    auth_user = _fake_auth_user(user_id=admin.id, role=admin.role, email=admin.email)
    _set_auth(smoke_db, auth_user)
    client = TestClient(app)

    endpoints = [
        "/admin/users",
        "/admin/users/new",
        f"/admin/users/{student.id}/edit",
        "/admin/home",
        "/admin/memberships",
        "/admin/memberships/assign",
        "/admin/memberships/consume",
        "/admin/memberships/report",
        "/admin/classes",
        "/admin/classes/enrollments",
        "/admin/caja",
        "/admin/followups",
        "/admin/followups/dashboard",
        "/admin/followups/automation",
        "/admin/followups/agenda",
        "/admin/followups/kanban",
        "/admin/followups/reminders",
        "/admin/templates",
        "/admin/templates/new",
        f"/admin/alumnos/{student.id}/payments",
        f"/admin/alumnos/{student.id}/followups",
        f"/admin/alumnos/{student.id}/actions",
        "/admin/conversations",
    ]

    try:
        for url in endpoints:
            response = client.get(url, follow_redirects=False)
            assert response.status_code == 200, f"Falló GET {url}: {response.status_code}"
    finally:
        _clear_overrides()


def test_admin_representative_posts_smoke(smoke_db):
    seed = smoke_db()
    try:
        admin = _make_user(
            seed,
            email="admin-post@test.com",
            role=Role.ADMINISTRADOR,
            first_name="AdminPost",
        )
    finally:
        seed.close()

    auth_user = _fake_auth_user(user_id=admin.id, role=admin.role, email=admin.email)
    _set_auth(smoke_db, auth_user)
    client = TestClient(app)

    try:
        response = client.post(
            "/admin/templates/new",
            data={
                "name": "Smoke Template",
                "kind": "GENERAL",
                "channel": "WHATSAPP",
                "subject": "Asunto smoke",
                "body": "Cuerpo smoke",
                "is_active": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/admin/templates"

        response = client.post(
            "/admin/templates/seed",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/admin/templates"
    finally:
        _clear_overrides()


def test_professor_pages_and_posts_smoke(smoke_db):
    seed = smoke_db()
    try:
        professor = _make_user(
            seed,
            email="profe-smoke@test.com",
            role=Role.PROFESOR,
            first_name="ProfeSmoke",
        )
        student = _make_user(
            seed,
            email="alumno-prof-smoke@test.com",
            role=Role.ALUMNO,
            first_name="AlumnoProfSmoke",
        )
        _make_professor_student_link(
            seed,
            professor_id=professor.id,
            student_id=student.id,
        )
        routine = _make_routine(
            seed,
            professor_id=professor.id,
            title="Rutina Inicial Smoke",
        )
    finally:
        seed.close()

    auth_user = _fake_auth_user(user_id=professor.id, role=professor.role, email=professor.email)
    _set_auth(smoke_db, auth_user)
    client = TestClient(app)

    endpoints = [
        "/profesor",
        "/profesor/exercises",
        "/profesor/exercises/new",
        "/profesor/routines",
        "/profesor/routines/new",
        f"/profesor/routines/{routine.id}",
        "/profesor/assignments",
        f"/profesor/assignments/history/{student.id}",
        "/profesor/alumnos",
    ]

    try:
        for url in endpoints:
            response = client.get(url, follow_redirects=False)
            assert response.status_code == 200, f"Falló GET {url}: {response.status_code}"

        response = client.post(
            "/profesor/exercises/new",
            data={
                "name": "Sentadilla Smoke",
                "description": "Ejercicio smoke",
                "muscle_group": "Piernas",
                "equipment": "Barra",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/profesor/exercises"

        response = client.post(
            "/profesor/routines/new",
            data={
                "title": "Rutina Nueva Smoke",
                "notes": "Notas smoke",
                "routine_type": "DIAS",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"].startswith("/profesor/routines/")
    finally:
        _clear_overrides()


def test_alumno_pages_smoke(smoke_db):
    seed = smoke_db()
    try:
        student = _make_user(
            seed,
            email="alumno-app-smoke@test.com",
            role=Role.ALUMNO,
            first_name="AlumnoAppSmoke",
        )
    finally:
        seed.close()

    auth_user = _fake_auth_user(user_id=student.id, role=student.role, email=student.email)
    _set_auth(smoke_db, auth_user)
    client = TestClient(app)

    endpoints = [
        "/alumno",
        "/alumno/app",
        "/alumno/rutina",
        "/alumno/membresia",
    ]

    try:
        expected_status = {
            "/alumno": 200,
            "/alumno/app": 200,
            "/alumno/rutina": 302,
            "/alumno/membresia": 200,
        }

        for url in endpoints:
            response = client.get(url, follow_redirects=False)
            assert response.status_code == expected_status[url], f"Falló GET {url}: {response.status_code}"
    finally:
        _clear_overrides()