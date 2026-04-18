from datetime import date, datetime, time as dtime
from types import SimpleNamespace

from app.models import ServiceKind
from app.services.membership_service import (
    current_membership_period,
    parse_usage_date,
    parse_usage_time,
    resolve_membership_service_limits,
    validate_membership_usage_capacity,
    validate_usage_date_for_current_period,
    validate_usage_time_window,
)


class DummyDB:
    def __init__(self, scalar_values=None):
        self.scalar_values = list(scalar_values or [])

    def scalar(self, stmt):
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return 0


def test_parse_usage_date_and_period():
    used_date = parse_usage_date("2026-04-16")
    assert used_date == date(2026, 4, 16)
    assert current_membership_period(date(2026, 4, 16)) == "2026-04"


def test_parse_usage_time_defaults_and_manual():
    manual = parse_usage_time("07:30")
    assert manual == dtime(7, 30)

    auto = parse_usage_time("", now=datetime(2026, 4, 16, 21, 45, 10))
    assert auto == dtime(21, 45)


def test_validate_usage_date_for_current_period():
    assert (
        validate_usage_date_for_current_period(
            date(2026, 4, 19),
            current_period="2026-04",
        )
        == "No se puede registrar consumo en domingo (gimnasio cerrado)."
    )

    assert (
        validate_usage_date_for_current_period(
            date(2026, 3, 31),
            current_period="2026-04",
        )
        == "Solo se permite registrar consumos del mes actual (2026-04)."
    )

    assert (
        validate_usage_date_for_current_period(
            date(2026, 4, 16),
            current_period="2026-04",
        )
        is None
    )


def test_validate_usage_time_window():
    assert validate_usage_time_window(dtime(6, 59)) == "Fuera de horario. Solo 07:00 a 22:00."
    assert validate_usage_time_window(dtime(7, 0)) is None
    assert validate_usage_time_window(dtime(22, 0)) is None
    assert validate_usage_time_window(dtime(22, 1)) == "Fuera de horario. Solo 07:00 a 22:00."


def test_resolve_membership_service_limits():
    membership = SimpleNamespace(
        funcional_unlimited=False,
        funcional_classes=12,
        musculacion_unlimited=True,
        musculacion_classes=None,
    )

    unlimited_f, allowed_f = resolve_membership_service_limits(
        membership,
        service=ServiceKind.FUNCIONAL,
    )
    assert unlimited_f is False
    assert allowed_f == 12

    unlimited_m, allowed_m = resolve_membership_service_limits(
        membership,
        service=ServiceKind.MUSCULACION,
    )
    assert unlimited_m is True
    assert allowed_m is None


def test_validate_membership_usage_capacity_blocks_when_quota_exhausted():
    db = DummyDB(scalar_values=[12])
    membership = SimpleNamespace(
        funcional_unlimited=False,
        funcional_classes=12,
        musculacion_unlimited=False,
        musculacion_classes=8,
    )

    error, used_count = validate_membership_usage_capacity(
        db,
        student_id=10,
        membership=membership,
        period="2026-04",
        service=ServiceKind.FUNCIONAL,
    )

    assert error == "Cupo agotado para FUNCIONAL. Usadas 12/12."
    assert used_count == 12


def test_validate_membership_usage_capacity_allows_unlimited():
    db = DummyDB(scalar_values=[99])
    membership = SimpleNamespace(
        funcional_unlimited=True,
        funcional_classes=None,
        musculacion_unlimited=False,
        musculacion_classes=8,
    )

    error, used_count = validate_membership_usage_capacity(
        db,
        student_id=10,
        membership=membership,
        period="2026-04",
        service=ServiceKind.FUNCIONAL,
    )

    assert error is None
    assert used_count == 99