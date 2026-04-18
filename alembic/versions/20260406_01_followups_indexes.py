"""followups indexes

Revision ID: 20260406_01
Revises: e47e89f2d574
Create Date: 2026-04-06 19:00:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260406_01"
down_revision = "e47e89f2d574"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_student_followups_status_created_at
    ON student_followups (status, created_at DESC);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_student_followups_kind_status_created_at
    ON student_followups (kind, status, created_at DESC);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_student_followups_priority_created_at
    ON student_followups (priority, created_at DESC);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_student_followups_next_contact_date_status
    ON student_followups (next_contact_date, status);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_student_followups_automation_next_contact_date
    ON student_followups (automation_enabled, next_contact_date);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_student_followups_student_created_at
    ON student_followups (student_id, created_at DESC);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_followup_actions_followup_created_at
    ON followup_actions (followup_id, created_at DESC);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_followup_actions_action_type_created_at
    ON followup_actions (action_type, created_at DESC);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_followup_actions_delivery_status_created_at
    ON followup_actions (delivery_status, created_at DESC);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_followup_actions_delivery_status_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_followup_actions_action_type_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_followup_actions_followup_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_student_followups_student_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_student_followups_automation_next_contact_date;")
    op.execute("DROP INDEX IF EXISTS ix_student_followups_next_contact_date_status;")
    op.execute("DROP INDEX IF EXISTS ix_student_followups_priority_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_student_followups_kind_status_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_student_followups_status_created_at;")