from app.models import ProfesorAlumno, Role, Routine, RoutineAssignment, User
from app.services.professor_query_service import (
    load_professor_active_assignments,
    load_professor_active_assignments_map,
    load_professor_assignment_history,
    load_professor_students,
)


def _make_user(db_session, *, email, role, first_name, last_name="Test", is_active=True, dni=None):
    row = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name} {last_name}",
        password_hash="hash",
        role=role,
        is_active=is_active,
        dni=dni,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _make_routine(db_session, professor_id, title):
    row = Routine(
        professor_id=professor_id,
        title=title,
        notes="",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_load_professor_students_filters_in_db(db_session):
    profe = _make_user(
        db_session,
        email="profe@test.com",
        role=Role.PROFESOR,
        first_name="Profe",
    )
    alumno_ok = _make_user(
        db_session,
        email="ana@test.com",
        role=Role.ALUMNO,
        first_name="Ana",
        last_name="Lopez",
        dni="111",
    )
    _make_user(
        db_session,
        email="otro@test.com",
        role=Role.ALUMNO,
        first_name="Bruno",
        last_name="Perez",
        dni="222",
    )

    db_session.add(
        ProfesorAlumno(
            profesor_id=profe.id,
            alumno_id=alumno_ok.id,
        )
    )
    db_session.commit()

    rows = load_professor_students(db_session, professor_id=profe.id, q="ana")

    assert len(rows) == 1
    assert rows[0].id == alumno_ok.id


def test_load_professor_active_assignments_only_returns_professor_rows(db_session):
    profe_1 = _make_user(
        db_session,
        email="profe1@test.com",
        role=Role.PROFESOR,
        first_name="Profe1",
    )
    profe_2 = _make_user(
        db_session,
        email="profe2@test.com",
        role=Role.PROFESOR,
        first_name="Profe2",
    )
    alumno_1 = _make_user(
        db_session,
        email="alumno1@test.com",
        role=Role.ALUMNO,
        first_name="Alumno1",
    )
    alumno_2 = _make_user(
        db_session,
        email="alumno2@test.com",
        role=Role.ALUMNO,
        first_name="Alumno2",
    )

    rutina_1 = _make_routine(db_session, profe_1.id, "Rutina 1")
    rutina_2 = _make_routine(db_session, profe_2.id, "Rutina 2")

    db_session.add_all(
        [
            RoutineAssignment(
                routine_id=rutina_1.id,
                student_id=alumno_1.id,
                assigned_by=profe_1.id,
                is_active=True,
            ),
            RoutineAssignment(
                routine_id=rutina_2.id,
                student_id=alumno_2.id,
                assigned_by=profe_2.id,
                is_active=True,
            ),
        ]
    )
    db_session.commit()

    rows = load_professor_active_assignments(db_session, professor_id=profe_1.id)

    assert len(rows) == 1
    assert rows[0].routine_id == rutina_1.id
    assert rows[0].student_id == alumno_1.id


def test_load_professor_assignment_history_only_for_that_professor(db_session):
    profe_1 = _make_user(
        db_session,
        email="profe3@test.com",
        role=Role.PROFESOR,
        first_name="Profe3",
    )
    profe_2 = _make_user(
        db_session,
        email="profe4@test.com",
        role=Role.PROFESOR,
        first_name="Profe4",
    )
    alumno = _make_user(
        db_session,
        email="alumno3@test.com",
        role=Role.ALUMNO,
        first_name="Alumno3",
    )

    rutina_1 = _make_routine(db_session, profe_1.id, "Rutina A")
    rutina_2 = _make_routine(db_session, profe_2.id, "Rutina B")

    db_session.add_all(
        [
            RoutineAssignment(
                routine_id=rutina_1.id,
                student_id=alumno.id,
                assigned_by=profe_1.id,
                is_active=False,
            ),
            RoutineAssignment(
                routine_id=rutina_2.id,
                student_id=alumno.id,
                assigned_by=profe_2.id,
                is_active=False,
            ),
        ]
    )
    db_session.commit()

    rows = load_professor_assignment_history(
        db_session,
        professor_id=profe_1.id,
        student_id=alumno.id,
    )

    assert len(rows) == 1
    assert rows[0].routine_id == rutina_1.id


def test_load_professor_active_assignments_map_returns_latest_by_student(db_session):
    profe = _make_user(
        db_session,
        email="profe5@test.com",
        role=Role.PROFESOR,
        first_name="Profe5",
    )
    alumno_1 = _make_user(
        db_session,
        email="alumno4@test.com",
        role=Role.ALUMNO,
        first_name="Alumno4",
    )
    alumno_2 = _make_user(
        db_session,
        email="alumno5@test.com",
        role=Role.ALUMNO,
        first_name="Alumno5",
    )

    rutina_1 = _make_routine(db_session, profe.id, "Rutina X")
    rutina_2 = _make_routine(db_session, profe.id, "Rutina Y")

    db_session.add_all(
        [
            RoutineAssignment(
                routine_id=rutina_1.id,
                student_id=alumno_1.id,
                assigned_by=profe.id,
                is_active=True,
            ),
            RoutineAssignment(
                routine_id=rutina_2.id,
                student_id=alumno_2.id,
                assigned_by=profe.id,
                is_active=True,
            ),
        ]
    )
    db_session.commit()

    result = load_professor_active_assignments_map(
        db_session,
        professor_id=profe.id,
        student_ids=[alumno_1.id, alumno_2.id],
    )

    assert alumno_1.id in result
    assert alumno_2.id in result
    assert result[alumno_1.id].routine_id == rutina_1.id
    assert result[alumno_2.id].routine_id == rutina_2.id