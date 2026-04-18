from app.models import ClassStatus, EnrollmentStatus, Role, ServiceKind
from app.services.class_service import (
    apply_enrollment_state,
    build_enrollment_payload,
    get_group_and_class_for_enrollment,
    resolve_target_student_id,
    validate_group_capacity_available,
)


class DummyScalarResult:
    def __init__(self, rows=None, first_value=None):
        self._rows = rows or []
        self._first_value = first_value

    def all(self):
        return self._rows

    def first(self):
        return self._first_value


class DummyDB:
    def __init__(self):
        self.objects = {}
        self.scalar_values = []

    def get(self, model, obj_id):
        return self.objects.get((model, obj_id))

    def scalar(self, stmt):
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return 0


def test_resolve_target_student_id_for_student():
    actor = type("Actor", (), {"role": Role.ALUMNO, "id": 44})()
    assert resolve_target_student_id(actor=actor, posted_student_id=99) == 44


def test_resolve_target_student_id_for_admin():
    actor = type("Actor", (), {"role": Role.ADMINISTRATIVO, "id": 1})()
    assert resolve_target_student_id(actor=actor, posted_student_id=99) == 99


def test_build_enrollment_payload():
    row = build_enrollment_payload(
        group_id=10,
        student_id=20,
        notes="nota",
        created_by_id=1,
    )
    assert row.group_id == 10
    assert row.student_id == 20
    assert row.notes == "nota"
    assert row.created_by_id == 1
    assert row.status == EnrollmentStatus.ACTIVA


def test_apply_enrollment_state():
    row = type(
        "Enrollment",
        (),
        {
            "status": EnrollmentStatus.CANCELADA,
            "notes": "",
            "created_by_id": None,
        },
    )()
    apply_enrollment_state(
        enrollment=row,
        notes="reactivado",
        created_by_id=5,
    )
    assert row.status == EnrollmentStatus.ACTIVA
    assert row.notes == "reactivado"
    assert row.created_by_id == 5


def test_validate_group_capacity_available_true():
    db = DummyDB()
    db.scalar_values = [2]
    assert validate_group_capacity_available(db, group_id=10, capacity=3) is True


def test_validate_group_capacity_available_false():
    db = DummyDB()
    db.scalar_values = [3]
    assert validate_group_capacity_available(db, group_id=10, capacity=3) is False