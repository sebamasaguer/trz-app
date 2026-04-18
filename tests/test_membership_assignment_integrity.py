from app.services.membership_service import is_membership_assignment_duplicate_integrity_error


class FakeExc(Exception):
    pass


def test_detects_assignment_duplicate_integrity_error_by_constraint_name():
    exc = FakeExc(
        'duplicate key value violates unique constraint "uq_membership_assignment_student_period_active"'
    )
    assert is_membership_assignment_duplicate_integrity_error(exc) is True


def test_detects_assignment_duplicate_integrity_error_by_columns():
    exc = FakeExc(
        "UNIQUE constraint failed: membership_assignments.student_id, membership_assignments.period_yyyymm, membership_assignments.is_active"
    )
    assert is_membership_assignment_duplicate_integrity_error(exc) is True


def test_non_assignment_duplicate_integrity_error_returns_false():
    exc = FakeExc("foreign key violation on membership_assignments.membership_id")
    assert is_membership_assignment_duplicate_integrity_error(exc) is False