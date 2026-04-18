from datetime import date, time as dtime

from app.services.membership_service import (
    build_assignment_duplicate_message,
    build_assignment_success_message,
    build_consume_success_message,
    build_duplicate_usage_message,
    build_missing_assignment_message,
    normalize_period_input,
)


def test_normalize_period_input_valid():
    assert normalize_period_input("2026-04") == "2026-04"


def test_normalize_period_input_invalid_falls_back_to_current():
    assert normalize_period_input("abril-2026", today=date(2026, 4, 16)) == "2026-04"
    assert normalize_period_input("", today=date(2026, 4, 16)) == "2026-04"


def test_build_assignment_success_message():
    assert (
        build_assignment_success_message(
            student_full_name="Juan Pérez",
            period="2026-04",
        )
        == "Membresía asignada correctamente para Juan Pérez en 2026-04."
    )


def test_build_assignment_duplicate_message():
    assert (
        build_assignment_duplicate_message(
            student_full_name="Juan Pérez",
            period="2026-04",
        )
        == "Ya existe una membresía activa para Juan Pérez en 2026-04."
    )


def test_build_duplicate_usage_message():
    assert (
        build_duplicate_usage_message(
            service_value="FUNCIONAL",
            student_full_name="Juan Pérez",
            used_date=date(2026, 4, 16),
        )
        == "Ya existe un consumo de FUNCIONAL para Juan Pérez en 2026-04-16."
    )


def test_build_missing_assignment_message():
    assert (
        build_missing_assignment_message(period="2026-04")
        == "El alumno no tiene membresía activa para 2026-04."
    )


def test_build_consume_success_message():
    assert (
        build_consume_success_message(
            service_value="FUNCIONAL",
            student_full_name="Juan Pérez",
            used_date=date(2026, 4, 16),
            used_clock=dtime(7, 30),
        )
        == "OK: registrado FUNCIONAL para Juan Pérez (2026-04-16 07:30)."
    )