from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ProfesorAlumno, Role, Routine, User


def is_professor_student_linked(db: Session, *, professor_id: int, student_id: int) -> bool:
    row = db.scalar(
        select(ProfesorAlumno.id).where(
            ProfesorAlumno.profesor_id == professor_id,
            ProfesorAlumno.alumno_id == student_id,
        ).limit(1)
    )
    return bool(row)


def load_professor_owned_student(
    db: Session,
    *,
    professor_id: int,
    student_id: int,
) -> User | None:
    student = db.get(User, student_id)
    if not student or student.role != Role.ALUMNO:
        return None

    if not is_professor_student_linked(db, professor_id=professor_id, student_id=student_id):
        return None

    return student


def load_professor_owned_routine(
    db: Session,
    *,
    professor_id: int,
    routine_id: int,
) -> Routine | None:
    routine = db.get(Routine, routine_id)
    if not routine or routine.professor_id != professor_id:
        return None
    return routine