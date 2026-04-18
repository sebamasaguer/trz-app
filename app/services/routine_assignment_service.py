from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..models import RoutineAssignment


def assign_routine_to_student(
    db: Session,
    *,
    routine_id: int,
    student_id: int,
    assigned_by: int,
    start_date: date | None,
) -> RoutineAssignment:
    """
    Garantiza una sola rutina activa por alumno:
    - desactiva activas previas
    - crea la nueva activa
    - hace flush para que la unicidad falle acá si hubiera carrera/concurrencia
    """
    db.query(RoutineAssignment).filter(
        RoutineAssignment.student_id == student_id,
        RoutineAssignment.is_active == True,
    ).update({"is_active": False})

    row = RoutineAssignment(
        routine_id=routine_id,
        student_id=student_id,
        assigned_by=assigned_by,
        start_date=start_date,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row