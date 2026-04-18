from app.services.class_service import is_class_enrollment_duplicate_integrity_error


class FakeExc(Exception):
    pass


def test_detects_duplicate_class_enrollment_integrity_error_by_constraint_name():
    exc = FakeExc(
        'duplicate key value violates unique constraint "uq_class_enrollment_group_student"'
    )
    assert is_class_enrollment_duplicate_integrity_error(exc) is True


def test_detects_duplicate_class_enrollment_integrity_error_by_columns():
    exc = FakeExc(
        "UNIQUE constraint failed: class_enrollments.group_id, class_enrollments.student_id"
    )
    assert is_class_enrollment_duplicate_integrity_error(exc) is True


def test_non_duplicate_class_enrollment_integrity_error_returns_false():
    exc = FakeExc("foreign key violation on class_enrollments.group_id")
    assert is_class_enrollment_duplicate_integrity_error(exc) is False