from datetime import date
from types import SimpleNamespace

from app.models import PaymentMethod, Role
from app.services.membership_service import (
    build_membership_assignment,
    parse_assignment_start_date,
    parse_optional_payment_method,
    resolve_assignment_period,
    validate_assignment_entities,
)


def test_parse_assignment_start_date_and_period():
    sd = parse_assignment_start_date("2026-04-16")
    assert sd == date(2026, 4, 16)
    assert resolve_assignment_period(sd) == "2026-04"


def test_parse_assignment_start_date_empty_returns_none():
    assert parse_assignment_start_date("") is None
    assert resolve_assignment_period(None, today=date(2026, 4, 16)) == "2026-04"


def test_parse_optional_payment_method():
    assert parse_optional_payment_method("") is None
    assert parse_optional_payment_method("EFECTIVO") == PaymentMethod.EFECTIVO


def test_validate_assignment_entities_ok():
    student = SimpleNamespace(role=Role.ALUMNO)
    membership = SimpleNamespace(is_active=True)

    assert (
        validate_assignment_entities(
            student=student,
            membership=membership,
            alumno_role=Role.ALUMNO,
        )
        is None
    )


def test_validate_assignment_entities_invalid_student():
    membership = SimpleNamespace(is_active=True)

    assert (
        validate_assignment_entities(
            student=None,
            membership=membership,
            alumno_role=Role.ALUMNO,
        )
        == "Alumno inválido."
    )


def test_validate_assignment_entities_invalid_membership():
    student = SimpleNamespace(role=Role.ALUMNO)

    assert (
        validate_assignment_entities(
            student=student,
            membership=None,
            alumno_role=Role.ALUMNO,
        )
        == "Membresía inválida."
    )


def test_validate_assignment_entities_inactive_membership():
    student = SimpleNamespace(role=Role.ALUMNO)
    membership = SimpleNamespace(is_active=False)

    assert (
        validate_assignment_entities(
            student=student,
            membership=membership,
            alumno_role=Role.ALUMNO,
        )
        == "La membresía seleccionada está inactiva."
    )


def test_build_membership_assignment():
    item = build_membership_assignment(
        membership_id=3,
        student_id=8,
        assigned_by=1,
        start_date=date(2026, 4, 16),
        period="2026-04",
        payment_method=PaymentMethod.LISTA,
        amount_snapshot=70000.0,
    )

    assert item.membership_id == 3
    assert item.student_id == 8
    assert item.assigned_by == 1
    assert item.start_date == date(2026, 4, 16)
    assert item.period_yyyymm == "2026-04"
    assert item.payment_method == PaymentMethod.LISTA
    assert item.amount_snapshot == 70000.0
    assert item.is_active is True