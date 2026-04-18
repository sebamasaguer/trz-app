import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Role, User, Routine, RoutineAssignment, ProfesorAlumno
from app.services.routine_assignment_service import assign_routine_to_student


def _make_user(db_session, *, email, role, first_name):
    row = User(
        email=email,
        first_name=first_name,
        last_name="Test",
        full_name=f"{first_name} Test",
        password_hash="hash",
        role=role,
        is_active=True,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _make_routine(db_session, professor_id, title="Rutina base"):
    row = Routine(
        professor_id=professor_id,
        title=title,
        notes="",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_profesor_alumno_pair_must_be_unique(db_session):
    profesor = _make_user(
        db_session,
        email="profe@test.com",
        role=Role.PROFESOR,
        first_name="Profe",
    )
    alumno = _make_user(
        db_session,
        email="alumno1@test.com",
        role=Role.ALUMNO,
        first_name="Alumno",
    )

    db_session.add(
        ProfesorAlumno(
            profesor_id=profesor.id,
            alumno_id=alumno.id,
        )
    )
    db_session.commit()

    db_session.add(
        ProfesorAlumno(
            profesor_id=profesor.id,
            alumno_id=alumno.id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_unique_active_routine_assignment_per_student(db_session):
    profesor = _make_user(
        db_session,
        email="profe2@test.com",
        role=Role.PROFESOR,
        first_name="Profe2",
    )
    alumno = _make_user(
        db_session,
        email="alumno2@test.com",
        role=Role.ALUMNO,
        first_name="Alumno2",
    )

    rutina_1 = _make_routine(db_session, profesor.id, title="Rutina 1")
    rutina_2 = _make_routine(db_session, profesor.id, title="Rutina 2")

    db_session.add(
        RoutineAssignment(
            routine_id=rutina_1.id,
            student_id=alumno.id,
            assigned_by=profesor.id,
            is_active=True,
        )
    )
    db_session.commit()

    db_session.add(
        RoutineAssignment(
            routine_id=rutina_2.id,
            student_id=alumno.id,
            assigned_by=profesor.id,
            is_active=True,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_assign_routine_to_student_deactivates_previous_active(db_session):
    profesor = _make_user(
        db_session,
        email="profe3@test.com",
        role=Role.PROFESOR,
        first_name="Profe3",
    )
    alumno = _make_user(
        db_session,
        email="alumno3@test.com",
        role=Role.ALUMNO,
        first_name="Alumno3",
    )

    rutina_1 = _make_routine(db_session, profesor.id, title="Rutina 1")
    rutina_2 = _make_routine(db_session, profesor.id, title="Rutina 2")

    first = assign_routine_to_student(
        db_session,
        routine_id=rutina_1.id,
        student_id=alumno.id,
        assigned_by=profesor.id,
        start_date=None,
    )
    db_session.commit()
    db_session.refresh(first)

    second = assign_routine_to_student(
        db_session,
        routine_id=rutina_2.id,
        student_id=alumno.id,
        assigned_by=profesor.id,
        start_date=None,
    )
    db_session.commit()
    db_session.refresh(second)

    rows = (
        db_session.query(RoutineAssignment)
        .filter(RoutineAssignment.student_id == alumno.id)
        .order_by(RoutineAssignment.id.asc())
        .all()
    )

    assert len(rows) == 2
    assert rows[0].is_active is False
    assert rows[1].is_active is True
    assert rows[1].routine_id == rutina_2.id