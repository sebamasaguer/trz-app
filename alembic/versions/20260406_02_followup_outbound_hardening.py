"""followup outbound hardening

Revision ID: 20260406_02
Revises: 20260406_01
Create Date: 2026-04-06 20:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260406_02"
down_revision = "20260406_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("student_followups", sa.Column("outbound_in_progress", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("student_followups", sa.Column("last_outbound_ref", sa.String(length=180), nullable=False, server_default=""))
    op.add_column("student_followups", sa.Column("last_outbound_at", sa.DateTime(), nullable=True))

    op.create_index("ix_student_followups_outbound_in_progress", "student_followups", ["outbound_in_progress"], unique=False)
    op.create_index("ix_student_followups_last_outbound_ref", "student_followups", ["last_outbound_ref"], unique=False)


def downgrade():
    op.drop_index("ix_student_followups_last_outbound_ref", table_name="student_followups")
    op.drop_index("ix_student_followups_outbound_in_progress", table_name="student_followups")

    op.drop_column("student_followups", "last_outbound_at")
    op.drop_column("student_followups", "last_outbound_ref")
    op.drop_column("student_followups", "outbound_in_progress")