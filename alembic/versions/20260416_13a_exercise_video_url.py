"""add video url to exercises

Revision ID: 20260416_13a
Revises: 20260416_11b
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260416_13a"
down_revision = "20260416_11b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "exercises",
        sa.Column("video_url", sa.String(length=500), nullable=True),
    )


def downgrade():
    op.drop_column("exercises", "video_url")