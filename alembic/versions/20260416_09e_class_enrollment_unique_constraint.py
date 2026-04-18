"""class enrollment unique constraint

Revision ID: 20260416_09e
Revises: 20260416_08e
Create Date: 2026-04-16
"""

from alembic import op


revision = "20260416_09e"
down_revision = "20260416_08e"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "uq_class_enrollment_group_student"
TABLE_NAME = "class_enrollments"


def upgrade():
    op.create_unique_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        ["group_id", "student_id"],
    )


def downgrade():
    op.drop_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        type_="unique",
    )