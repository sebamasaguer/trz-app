"""dashboard support indexes

Revision ID: 20260416_10b
Revises: 20260416_10a
Create Date: 2026-04-16
"""

from alembic import op


revision = "20260416_10b"
down_revision = "20260416_10a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_membership_usages_used_at_id",
        "membership_usages",
        ["used_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_membership_usages_student_used_at",
        "membership_usages",
        ["student_id", "used_at"],
        unique=False,
    )
    op.create_index(
        "ix_membership_assignments_active_student_period_id",
        "membership_assignments",
        ["is_active", "student_id", "period_yyyymm", "id"],
        unique=False,
    )
    op.create_index(
        "ix_users_role_is_active_created_at",
        "users",
        ["role", "is_active", "created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_users_role_is_active_created_at", table_name="users")
    op.drop_index("ix_membership_assignments_active_student_period_id", table_name="membership_assignments")
    op.drop_index("ix_membership_usages_student_used_at", table_name="membership_usages")
    op.drop_index("ix_membership_usages_used_at_id", table_name="membership_usages")