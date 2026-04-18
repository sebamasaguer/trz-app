from types import SimpleNamespace
from datetime import datetime

import pytest

from app.services import cash_service as svc


class DummyDB:
    def __init__(self):
        self.added = []
        self.flushed = 0
        self.scalar_values = []

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushed += 1

    def scalar(self, stmt):
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return None


def test_money_returns_float():
    assert svc.money(None) == 0.0
    assert svc.money(10) == 10.0
    assert svc.money("12.5") == 12.5


def test_parse_cash_movement_datetime_without_date_returns_datetime():
    dt = svc.parse_cash_movement_datetime("", "")
    assert isinstance(dt, datetime)


def test_parse_cash_movement_datetime_with_date_only():
    dt = svc.parse_cash_movement_datetime("2026-04-15", "")
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 15
    assert dt.hour == 0
    assert dt.minute == 0


def test_parse_cash_movement_datetime_with_date_and_time():
    dt = svc.parse_cash_movement_datetime("2026-04-15", "13:45")
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 15
    assert dt.hour == 13
    assert dt.minute == 45


def test_sync_cash_session_totals_updates_expected_amount():
    db = DummyDB()
    db.scalar_values = [1500, 300]

    cash_session = SimpleNamespace(
        id=1,
        opening_amount=1000,
        total_income=0,
        total_expense=0,
        expected_closing_amount=0,
    )

    svc.sync_cash_session_totals(db, cash_session)

    assert cash_session.total_income == 1500
    assert cash_session.total_expense == 300
    assert cash_session.expected_closing_amount == 2200.0


def test_register_cash_income_requires_open_session(monkeypatch):
    db = DummyDB()

    monkeypatch.setattr(svc, "get_open_cash_session", lambda db: None)

    with pytest.raises(ValueError, match="No hay caja abierta"):
        svc.register_cash_income(
            db,
            concept="Cuota",
            amount=1000,
            payment_method=None,
            created_by_id=1,
        )


def test_register_cash_income_creates_movement_and_syncs(monkeypatch):
    db = DummyDB()
    cash_session = SimpleNamespace(id=9)

    sync_called = {"ok": False}

    monkeypatch.setattr(svc, "get_open_cash_session", lambda db: cash_session)

    def fake_sync(db, session):
        sync_called["ok"] = True

    monkeypatch.setattr(svc, "sync_cash_session_totals", fake_sync)

    movement = svc.register_cash_income(
        db,
        concept="Cuota abril",
        amount=2500,
        payment_method=None,
        created_by_id=7,
        description="Pago manual",
    )

    assert movement.session_id == 9
    assert movement.concept == "Cuota abril"
    assert movement.amount == 2500
    assert movement.created_by_id == 7
    assert movement.notes == "Pago manual"
    assert len(db.added) == 1
    assert db.flushed == 2
    assert sync_called["ok"] is True