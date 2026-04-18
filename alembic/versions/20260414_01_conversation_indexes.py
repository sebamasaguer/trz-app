"""add indexes for contact_conversations admin listing

Revision ID: 20260414_01
Revises: 20260406_02
Create Date: 2026-04-14 00:00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260414_01"
down_revision = "20260406_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_contact_conversations_status
        ON contact_conversations (status)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_contact_conversations_assistant_paused
        ON contact_conversations (assistant_paused)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_contact_conversations_phone
        ON contact_conversations (phone)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_contact_conversations_status_assistant_paused_id
        ON contact_conversations (status, assistant_paused, id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_contact_conversations_status_assistant_paused_id")
    op.execute("DROP INDEX IF EXISTS ix_contact_conversations_phone")
    op.execute("DROP INDEX IF EXISTS ix_contact_conversations_assistant_paused")
    op.execute("DROP INDEX IF EXISTS ix_contact_conversations_status")