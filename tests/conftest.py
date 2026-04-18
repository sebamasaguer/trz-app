from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db import Base  # noqa: E402
from app.models import (  # noqa: E402
    User,
    Role,
    StudentFollowup,
    FollowupKind,
    FollowupStatus,
    FollowupPriority,
    FollowupChannel,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def admin_user(db_session):
    user = User(
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        full_name="Admin User",
        password_hash="hash",
        role=Role.ADMINISTRADOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def student_user(db_session):
    user = User(
        email="alumno@test.com",
        first_name="Alumno",
        last_name="Demo",
        full_name="Alumno Demo",
        password_hash="hash",
        role=Role.ALUMNO,
        is_active=True,
        phone="5493870000000",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def basic_followup(db_session, admin_user, student_user):
    row = StudentFollowup(
        student_id=student_user.id,
        created_by_id=admin_user.id,
        kind=FollowupKind.GENERAL,
        status=FollowupStatus.PENDIENTE,
        priority=FollowupPriority.MEDIA,
        channel=FollowupChannel.WHATSAPP,
        title="Seguimiento inicial",
        notes="Notas iniciales",
        automation_enabled=True,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row