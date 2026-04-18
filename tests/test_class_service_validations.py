import pytest

from app.models import EnrollmentStatus, Role, Weekday
from app.services.class_service import (
    normalize_group_name,
    parse_capacity_safe,
    parse_time_safe,
    validate_enrollment_cancel_permission,
    validate_group_time_range,
)


def test_parse_capacity_safe_ok():
    assert parse_capacity_safe(10) == 10
    assert parse_capacity_safe("5") == 5


def test_parse_capacity_safe_invalid():
    with pytest.raises(ValueError):
        parse_capacity_safe(0)

    with pytest.raises(ValueError):
        parse_capacity_safe("abc")


def test_normalize_group_name():
    assert normalize_group_name("  Grupo Mañana  ") == "Grupo Mañana"
    assert normalize_group_name("") == ""


def test_validate_group_time_range_ok():
    start_time = parse_time_safe("08:00")
    end_time = parse_time_safe("09:00")
    assert validate_group_time_range(start_time=start_time, end_time=end_time) is None


def test_validate_group_time_range_invalid():
    start_time = parse_time_safe("09:00")
    end_time = parse_time_safe("08:00")
    assert (
        validate_group_time_range(start_time=start_time, end_time=end_time)
        == "El horario de fin debe ser mayor al horario de inicio."
    )


def test_validate_enrollment_cancel_permission_admin():
    actor = type("Actor", (), {"role": Role.ADMINISTRATIVO, "id": 10})()
    enrollment = type("Enrollment", (), {"student_id": 5, "status": EnrollmentStatus.ACTIVA})()
    assert validate_enrollment_cancel_permission(enrollment=enrollment, actor=actor) is True


def test_validate_enrollment_cancel_permission_student_same_owner():
    actor = type("Actor", (), {"role": Role.ALUMNO, "id": 5})()
    enrollment = type("Enrollment", (), {"student_id": 5, "status": EnrollmentStatus.ACTIVA})()
    assert validate_enrollment_cancel_permission(enrollment=enrollment, actor=actor) is True


def test_validate_enrollment_cancel_permission_student_other_owner():
    actor = type("Actor", (), {"role": Role.ALUMNO, "id": 6})()
    enrollment = type("Enrollment", (), {"student_id": 5, "status": EnrollmentStatus.ACTIVA})()
    assert validate_enrollment_cancel_permission(enrollment=enrollment, actor=actor) is False


def test_validate_enrollment_cancel_permission_missing_enrollment():
    actor = type("Actor", (), {"role": Role.ADMINISTRADOR, "id": 1})()
    assert validate_enrollment_cancel_permission(enrollment=None, actor=actor) is False