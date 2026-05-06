from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from ..models import Exercise, ProfesorAlumno, Role, Routine, RoutineAssignment, User


def load_professor_exercises(
    db: Session,
    *,
    professor_id: int | None,
    q: str = "",
) -> list[Exercise]:
    stmt = select(Exercise).order_by(
        Exercise.name.asc(),
        Exercise.id.desc(),
    )

    if professor_id is not None:
        stmt = stmt.where(Exercise.professor_id == professor_id)

    q_clean = (q or "").strip()
    if q_clean:
        stmt = stmt.where(Exercise.name.ilike(f"%{q_clean}%"))

    return db.scalars(stmt).all()


def load_professor_routines(
    db: Session,
    *,
    professor_id: int | None,
) -> list[Routine]:
    stmt = select(Routine).order_by(Routine.id.desc())

    if professor_id is not None:
        stmt = stmt.where(Routine.professor_id == professor_id)

    return db.scalars(stmt).all()


def load_professor_students(
    db: Session,
    *,
    professor_id: int | None,
    q: str = "",
) -> list[User]:
    if professor_id is None:
        stmt = (
            select(User)
            .where(
                User.role == Role.ALUMNO,
                User.is_active.is_(True),
            )
            .order_by(User.last_name.asc(), User.first_name.asc(), User.email.asc())
        )
    else:
        stmt = (
            select(User)
            .join(ProfesorAlumno, ProfesorAlumno.alumno_id == User.id)
            .where(
                ProfesorAlumno.profesor_id == professor_id,
                User.role == Role.ALUMNO,
                User.is_active.is_(True),
            )
            .order_by(User.last_name.asc(), User.first_name.asc(), User.email.asc())
        )

    q_clean = (q or "").strip()
    if q_clean:
        like = f"%{q_clean}%"
        stmt = stmt.where(
            or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
                User.dni.ilike(like),
                User.full_name.ilike(like),
            )
        )

    return db.scalars(stmt).all()


def load_professor_active_assignments(
    db: Session,
    *,
    professor_id: int | None,
) -> list[RoutineAssignment]:
    stmt = (
        select(RoutineAssignment)
        .join(Routine, Routine.id == RoutineAssignment.routine_id)
        .where(RoutineAssignment.is_active.is_(True))
        .options(
            joinedload(RoutineAssignment.student),
            joinedload(RoutineAssignment.routine),
            joinedload(RoutineAssignment.professor),
        )
        .order_by(RoutineAssignment.id.desc())
    )

    if professor_id is not None:
        stmt = stmt.where(Routine.professor_id == professor_id)

    return db.scalars(stmt).all()


def load_professor_assignment_history(
    db: Session,
    *,
    professor_id: int | None,
    student_id: int,
) -> list[RoutineAssignment]:
    stmt = (
        select(RoutineAssignment)
        .join(Routine, Routine.id == RoutineAssignment.routine_id)
        .where(RoutineAssignment.student_id == student_id)
        .options(
            joinedload(RoutineAssignment.student),
            joinedload(RoutineAssignment.routine),
            joinedload(RoutineAssignment.professor),
        )
        .order_by(RoutineAssignment.id.desc())
    )

    if professor_id is not None:
        stmt = stmt.where(Routine.professor_id == professor_id)

    return db.scalars(stmt).all()


def load_professor_active_assignments_map(
    db: Session,
    *,
    professor_id: int | None,
    student_ids: list[int],
) -> dict[int, RoutineAssignment]:
    if not student_ids:
        return {}

    stmt = (
        select(RoutineAssignment)
        .join(Routine, Routine.id == RoutineAssignment.routine_id)
        .where(
            RoutineAssignment.student_id.in_(student_ids),
            RoutineAssignment.is_active.is_(True),
        )
        .options(
            joinedload(RoutineAssignment.student),
            joinedload(RoutineAssignment.routine),
            joinedload(RoutineAssignment.professor),
        )
        .order_by(RoutineAssignment.id.desc())
    )

    if professor_id is not None:
        stmt = stmt.where(Routine.professor_id == professor_id)

    rows = db.scalars(stmt).all()

    result: dict[int, RoutineAssignment] = {}
    for row in rows:
        if row.student_id not in result:
            result[row.student_id] = row

    return result