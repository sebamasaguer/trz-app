import pytest

from app.models import ServiceKind
from app.services.class_service import (
    build_extra_enrollment_note,
    build_final_enrollment_notes,
    parse_time_safe,
)


def test_parse_time_safe_ok():
    value = parse_time_safe("07:30")
    assert value.hour == 7
    assert value.minute == 30


def test_parse_time_safe_invalid():
    with pytest.raises(ValueError):
        parse_time_safe("abc")


def test_build_extra_enrollment_note_for_admin_without_slots():
    note = build_extra_enrollment_note(
        has_slots=False,
        gym_class_service_kind=ServiceKind.FUNCIONAL,
        actor_role_value="ADMINISTRATIVO",
    )
    assert "INSCRIPTO SIN CLASES DISPONIBLES" in note
    assert "FUNCIONAL" in note


def test_build_extra_enrollment_note_for_student_is_empty():
    note = build_extra_enrollment_note(
        has_slots=False,
        gym_class_service_kind=ServiceKind.FUNCIONAL,
        actor_role_value="ALUMNO",
    )
    assert note == ""


def test_build_final_enrollment_notes_joins_notes():
    final_notes = build_final_enrollment_notes(
        notes="Alumno pidió turno",
        extra_note="DEBE PAGAR EL MES.",
    )
    assert final_notes == "Alumno pidió turno | DEBE PAGAR EL MES."


def test_build_final_enrollment_notes_without_extra():
    final_notes = build_final_enrollment_notes(
        notes="Solo nota",
        extra_note="",
    )
    assert final_notes == "Solo nota"