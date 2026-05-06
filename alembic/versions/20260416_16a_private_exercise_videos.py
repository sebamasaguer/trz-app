"""add private video fields to exercises

Revision ID: 20260416_16a
Revises: 20260416_13a
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260416_16a"
down_revision = "20260416_13a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("exercises", sa.Column("video_path", sa.String(length=500), nullable=True))
    op.add_column("exercises", sa.Column("video_original_filename", sa.String(length=255), nullable=True))
    op.add_column("exercises", sa.Column("video_content_type", sa.String(length=100), nullable=True))
    op.add_column("exercises", sa.Column("video_size_bytes", sa.BigInteger(), nullable=True))


def downgrade():
    op.drop_column("exercises", "video_size_bytes")
    op.drop_column("exercises", "video_content_type")
    op.drop_column("exercises", "video_original_filename")
    op.drop_column("exercises", "video_path")