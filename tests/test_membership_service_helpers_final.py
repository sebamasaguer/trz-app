from app.services.membership_service import (
    load_prices_for_membership_ids,
    membership_kind_values,
    normalize_qr_service,
    prices_by_membership_map,
)


class DummyScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class DummyDB:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self, stmt):
        return DummyScalarResult(self.rows)


class PriceRow:
    def __init__(self, membership_id, method, amount):
        self.membership_id = membership_id
        self.payment_method = type("PM", (), {"value": method})()
        self.amount = amount


def test_membership_kind_values_contains_expected():
    values = membership_kind_values()
    assert "FUNCIONAL" in values
    assert "MUSCULACION" in values


def test_prices_by_membership_map_groups_prices():
    rows = [
        PriceRow(1, "LISTA", 100),
        PriceRow(1, "EFECTIVO", 90),
        PriceRow(2, "LISTA", 200),
    ]
    grouped = prices_by_membership_map(rows)

    assert grouped[1]["LISTA"] == 100.0
    assert grouped[1]["EFECTIVO"] == 90.0
    assert grouped[2]["LISTA"] == 200.0


def test_load_prices_for_membership_ids_returns_empty_for_empty_ids():
    db = DummyDB([])
    grouped = load_prices_for_membership_ids(db, membership_ids=[])
    assert grouped == {}


def test_load_prices_for_membership_ids_groups_rows():
    db = DummyDB(
        [
            PriceRow(10, "LISTA", 70000),
            PriceRow(10, "EFECTIVO", 65000),
        ]
    )
    grouped = load_prices_for_membership_ids(db, membership_ids=[10])
    assert grouped[10]["LISTA"] == 70000.0
    assert grouped[10]["EFECTIVO"] == 65000.0


def test_normalize_qr_service_still_falls_back():
    assert normalize_qr_service("otro") == "FUNCIONAL"