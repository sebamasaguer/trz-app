"""membership assignment unique constraint

Revision ID: 20260416_08e
Revises: 20260416_08c
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260416_08e"
down_revision = "20260416_08c"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "uq_membership_assignment_student_period_active"
TABLE_NAME = "membership_assignments"


def upgrade():
    op.create_unique_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        ["student_id", "period_yyyymm", "is_active"],
    )


def downgrade():
    op.drop_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        type_="unique",
    )