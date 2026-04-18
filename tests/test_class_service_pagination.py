from app.services.class_service import (
    active_enrollment_counts_for_group_ids,
    build_classes_list_query,
    build_enrollable_groups_query,
)


class DummyExecResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class DummyDB:
    def __init__(self, rows=None):
        self.rows = rows or []

    def execute(self, stmt):
        return DummyExecResult(self.rows)


def test_active_enrollment_counts_for_group_ids_empty():
    db = DummyDB([])
    result = active_enrollment_counts_for_group_ids(db, group_ids=[])
    assert result == {}


def test_active_enrollment_counts_for_group_ids_fills_missing_ids():
    db = DummyDB([(10, 3)])
    result = active_enrollment_counts_for_group_ids(db, group_ids=[10, 11])
    assert result[10] == 3
    assert result[11] == 0


def test_build_classes_list_query_returns_statement():
    stmt = build_classes_list_query(
        q="Funcional",
        status="ACTIVA",
        service_kind="FUNCIONAL",
    )
    assert stmt is not None


def test_build_enrollable_groups_query_returns_statement():
    stmt = build_enrollable_groups_query(weekday="LUNES")
    assert stmt is not None