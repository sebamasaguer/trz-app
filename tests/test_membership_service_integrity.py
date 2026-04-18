from app.services.membership_service import is_membership_usage_duplicate_integrity_error


class FakeExc(Exception):
    pass


def test_detects_duplicate_integrity_error_by_constraint_name():
    exc = FakeExc(
        'duplicate key value violates unique constraint "uq_membership_usage_student_date_service"'
    )
    assert is_membership_usage_duplicate_integrity_error(exc) is True


def test_detects_duplicate_integrity_error_by_columns():
    exc = FakeExc(
        "UNIQUE constraint failed: membership_usages.student_id, membership_usages.used_at, membership_usages.service"
    )
    assert is_membership_usage_duplicate_integrity_error(exc) is True


def test_non_duplicate_integrity_error_returns_false():
    exc = FakeExc("foreign key violation on membership_usages.assignment_id")
    assert is_membership_usage_duplicate_integrity_error(exc) is False