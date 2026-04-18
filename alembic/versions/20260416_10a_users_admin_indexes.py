"""users admin indexes

Revision ID: 20260416_10a
Revises: 20260416_09e
Create Date: 2026-04-16
"""

from alembic import op


revision = "20260416_10a"
down_revision = "20260416_09e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_users_role_is_active_id",
        "users",
        ["role", "is_active", "id"],
        unique=False,
    )
    op.create_index(
        "ix_users_is_active_id",
        "users",
        ["is_active", "id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_users_is_active_id", table_name="users")
    op.drop_index("ix_users_role_is_active_id", table_name="users")