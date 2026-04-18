"""membership usage unique constraint

Revision ID: 20260416_08c
Revises: 
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260416_08c"
down_revision = "20260414_01"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "uq_membership_usage_student_date_service"
TABLE_NAME = "membership_usages"


def upgrade():
    op.create_unique_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        ["student_id", "used_at", "service"],
    )


def downgrade():
    op.drop_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        type_="unique",
    )