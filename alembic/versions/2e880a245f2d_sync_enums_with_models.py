"""sync_enums_with_models

Revision ID: 2e880a245f2d
Revises: 20260416_11b_professor_followup_indexes
Create Date: 2026-04-20 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2e880a245f2d'
down_revision: Union[str, Sequence[str], None] = '20260416_11b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # List of (enum_name, new_value)
        updates = [
            ('role_enum', 'ADMINISTRADOR'),
            ('role_enum', 'ADMINISTRATIVO'),
            ('membership_kind', 'FUNCIONAL'),
            ('membership_kind', 'MUSCULACION'),
            ('membership_kind', 'COMBINACION'),
            ('membership_kind', 'CLASE_SUELTA'),
            ('prospect_status', 'INTERESADO'),
            ('prospect_status', 'DERIVADO'),
            ('prospect_status', 'CERRADO'),
            ('routine_type', 'DIAS'),
            ('routine_type', 'SEMANAS'),
            ('followup_kind', 'MOROSIDAD'),
            ('followup_kind', 'INACTIVIDAD'),
            ('followup_status', 'RESPONDIO'),
            ('followup_status', 'REACTIVADO'),
            ('followup_status', 'DESCARTADO'),
            ('followup_priority', 'CRITICA'),
            ('followup_channel', 'OTRO'),
            ('payment_method', 'LISTA'),
            ('cash_payment_status', 'ACREDITADO'),
            ('cash_payment_status', 'ANULADO'),
            ('enrollment_status', 'ACTIVA'),
            ('conversation_type', 'REACTIVACION'),
            ('conversation_type', 'NUEVO_PROSPECTO'),
            ('conversation_status', 'ABIERTA'),
            ('conversation_status', 'EN_AUTOMATICO'),
            ('conversation_status', 'DERIVADA_A_HUMANO'),
            ('commercial_stage', 'NUEVO'),
            ('commercial_stage', 'INTERESADO'),
            ('commercial_stage', 'DERIVADO'),
            ('commercial_stage', 'REACTIVADO'),
            ('commercial_stage', 'CERRADO'),
            ('commercial_stage', 'PERDIDO'),
            ('followup_action_type', 'MENSAJE_ENVIADO'),
            ('followup_action_type', 'EMAIL_ENVIADO'),
            ('followup_action_type', 'WHATSAPP_ENVIADO'),
            ('followup_action_type', 'RECORDATORIO'),
            ('followup_action_type', 'CAMBIO_ESTADO'),
            ('sender_type', 'ALUMNO'),
            ('sender_type', 'PROSPECTO'),
            ('sender_type', 'SISTEMA'),
        ]

        for enum_name, value in updates:
            # Check if value exists to be idempotent
            check_sql = sa.text(f"SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = '{enum_name}' AND e.enumlabel = '{value}'")
            res = bind.execute(check_sql).fetchone()
            if not res:
                op.execute(f"ALTER TYPE {enum_name} ADD VALUE '{value}'")

def downgrade() -> None:
    # Removing values from ENUMs is not directly supported in PostgreSQL without recreating the type.
    # Given the nature of this fix, we leave it as a no-op or handle if absolutely necessary.
    pass
