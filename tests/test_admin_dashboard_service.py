from datetime import date, time
from types import SimpleNamespace

from app.services.dashboard_service import (
    build_alertas,
    build_inactivity_details,
    build_membership_status,
    build_presence_breakdowns,
    normalize_date_range,
)


def _alumno(user_id, first_name, last_name):
    return SimpleNamespace(
        id=user_id,
        first_name=first_name,
        last_name=last_name,
        email=f"{first_name.lower()}@test.com",
        full_name=f"{first_name} {last_name}",
        dni="",
    )


def test_normalize_date_range_swaps_when_inverted():
    result = normalize_date_range("2026-04-20", "2026-04-10", today=date(2026, 4, 16))

    assert result.date_from == date(2026, 4, 10)
    assert result.date_to == date(2026, 4, 20)


def test_build_inactivity_details_buckets_students():
    today = date(2026, 4, 16)
    a1 = _alumno(1, "Ana", "A")
    a2 = _alumno(2, "Beto", "B")
    a3 = _alumno(3, "Carla", "C")

    last_usage_map = {
        1: date(2026, 4, 1),   # bucket 0
        2: date(2025, 10, 1),  # bucket 6+
        # 3 nunca
    }

    buckets, details, activos_recientes, total_inactivos = build_inactivity_details(
        [a1, a2, a3],
        last_usage_map,
        today=today,
    )

    assert len(buckets["0"]) == 1
    assert len(buckets["6+"]) == 1
    assert len(buckets["nunca"]) == 1
    assert activos_recientes == 1
    assert total_inactivos == 2
    assert len(details) == 3


def test_build_membership_status_marks_overdue_and_ok():
    today = date(2026, 4, 16)
    alumnos = [
        _alumno(1, "Ana", "A"),
        _alumno(2, "Beto", "B"),
        _alumno(3, "Carla", "C"),
    ]

    latest_assignment_by_student = {
        1: SimpleNamespace(
            id=10,
            period_yyyymm="2026-04",
            membership=SimpleNamespace(name="Plan día"),
        ),
        2: SimpleNamespace(
            id=11,
            period_yyyymm="2026-03",
            membership=SimpleNamespace(name="Plan mes"),
        ),
        3: SimpleNamespace(
            id=12,
            period_yyyymm=None,
            membership=SimpleNamespace(name="Plan sin período"),
        ),
    }

    vencidas, al_dia = build_membership_status(
        alumnos,
        latest_assignment_by_student,
        current_period="2026-04",
        today=today,
    )

    assert len(al_dia) == 1
    assert len(vencidas) == 2
    assert any(row["motivo"] == "Período vencido" for row in vencidas)
    assert any(row["motivo"] == "Asignación sin período" for row in vencidas)


def test_build_presence_breakdowns_builds_daily_series_and_hours():
    usages = [
        SimpleNamespace(
            used_at=date(2026, 4, 10),
            service=SimpleNamespace(value="FUNCIONAL"),
            used_at_time=time(9, 0),
        ),
        SimpleNamespace(
            used_at=date(2026, 4, 10),
            service=SimpleNamespace(value="FUNCIONAL"),
            used_at_time=time(9, 0),
        ),
        SimpleNamespace(
            used_at=date(2026, 4, 11),
            service=SimpleNamespace(value="MUSCULACION"),
            used_at_time=time(18, 30),
        ),
    ]

    por_dia, servicios, horarios_top = build_presence_breakdowns(
        usages,
        date(2026, 4, 10),
        date(2026, 4, 12),
    )

    assert len(por_dia) == 3
    assert por_dia[0]["count"] == 2
    assert por_dia[1]["count"] == 1
    assert por_dia[2]["count"] == 0

    servicios_map = {row["label"]: row["count"] for row in servicios}
    assert servicios_map["FUNCIONAL"] == 2
    assert servicios_map["MUSCULACION"] == 1

    assert horarios_top[0]["hour"] == "09:00"
    assert horarios_top[0]["count"] == 2


def test_build_alertas_returns_expected_flags():
    cuotas_vencidas = [
        {"severity": "alta"},
        {"severity": "media"},
    ]
    inactivos_bucket = {
        "0": [],
        "1": [],
        "2": [],
        "3": [],
        "4": [],
        "5": [],
        "6+": [object()],
        "nunca": [object()],
    }
    alumnos_nuevos_mes = [object(), object()]

    seguimiento, alertas = build_alertas(
        cuotas_vencidas=cuotas_vencidas,
        inactivos_bucket=inactivos_bucket,
        alumnos_nuevos_mes=alumnos_nuevos_mes,
    )

    assert seguimiento["morosos_alta"] == 1
    assert seguimiento["inactivos_criticos"] == 2
    assert seguimiento["alumnos_nuevos_mes"] == 2
    assert len(alertas) == 3