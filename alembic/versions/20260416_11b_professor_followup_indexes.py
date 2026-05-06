"""professor/followup support indexes

Revision ID: 20260416_11b
Revises: 20260416_11a
Create Date: 2026-04-16
"""

from alembic import op


revision = "20260416_11b"
down_revision = "20260416_11a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_users_role_is_active_last_name_first_name_id",
        "users",
        ["role", "is_active", "last_name", "first_name", "id"],
        unique=False,
    )

    op.create_index(
        "ix_message_templates_active_kind_channel_id",
        "message_templates",
        ["is_active", "kind", "channel", "id"],
        unique=False,
    )

    op.create_index(
        "ix_exercises_professor_name_id",
        "exercises",
        ["professor_id", "name", "id"],
        unique=False,
    )

    op.create_index(
        "ix_routines_professor_id_id",
        "routines",
        ["professor_id", "id"],
        unique=False,
    )

    op.create_index(
        "ix_routine_items_routine_day_weekday_order",
        "routine_items",
        ["routine_id", "day_label", "weekday", "order_index"],
        unique=False,
    )

    op.create_index(
        "ix_routine_assignments_student_id_id",
        "routine_assignments",
        ["student_id", "id"],
        unique=False,
    )

    op.create_index(
        "ix_routine_assignments_routine_active_id",
        "routine_assignments",
        ["routine_id", "is_active", "id"],
        unique=False,
    )

    op.create_index(
        "ix_profesor_alumnos_profesor_id_id",
        "profesor_alumnos",
        ["profesor_id", "id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_profesor_alumnos_profesor_id_id", table_name="profesor_alumnos")
    op.drop_index("ix_routine_assignments_routine_active_id", table_name="routine_assignments")
    op.drop_index("ix_routine_assignments_student_id_id", table_name="routine_assignments")
    op.drop_index("ix_routine_items_routine_day_weekday_order", table_name="routine_items")
    op.drop_index("ix_routines_professor_id_id", table_name="routines")
    op.drop_index("ix_exercises_professor_name_id", table_name="exercises")
    op.drop_index("ix_message_templates_active_kind_channel_id", table_name="message_templates")
    op.drop_index("ix_users_role_is_active_last_name_first_name_id", table_name="users")