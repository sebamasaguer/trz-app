"""baseline manual

Revision ID: e47e89f2d574
Revises: 
Create Date: 2026-03-18 00:23:05.623791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e47e89f2d574'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- CREATE ENUMS ---
    # We use a helper to create enums only if they don't exist
    def create_enum_if_not_exists(name, values):
        bind = op.get_bind()
        if bind.dialect.name == 'postgresql':
            res = bind.execute(sa.text(f"SELECT 1 FROM pg_type WHERE typname = '{name}'"))
            if not res.fetchone():
                values_str = ", ".join(f"'{v}'" for v in values)
                op.execute(f"CREATE TYPE {name} AS ENUM ({values_str})")

    create_enum_if_not_exists('service_kind', ['FUNCIONAL', 'MUSCULACION', 'AMBOS', 'OTRO'])
    create_enum_if_not_exists('class_status', ['ACTIVA', 'INACTIVA', 'CANCELADA'])
    create_enum_if_not_exists('membership_kind', ['MENSUAL', 'QUINCENAL', 'CLASES', 'OTRO'])
    create_enum_if_not_exists('template_followup_kind', ['GENERAL', 'RECORDATORIO_PAGO', 'BIENVENIDA', 'REACTIVACION', 'PROSPECTO'])
    create_enum_if_not_exists('message_template_channel', ['WHATSAPP', 'EMAIL', 'SMS', 'GENERAL'])
    create_enum_if_not_exists('role_enum', ['ADMIN', 'PROFESOR', 'ALUMNO', 'RECEPCION'])
    create_enum_if_not_exists('cash_session_status', ['ABIERTA', 'CERRADA'])
    create_enum_if_not_exists('weekday_enum', ['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO'])
    create_enum_if_not_exists('prospect_status', ['NUEVO', 'CONTACTADO', 'INTERESADO', 'INSCRIPTO', 'DESCARTADO'])
    create_enum_if_not_exists('routine_type', ['FUNCIONAL', 'MUSCULACION', 'PERSONALIZADA'])
    create_enum_if_not_exists('followup_kind', ['GENERAL', 'COBRO', 'ASISTENCIA', 'TECNICO', 'COMERCIAL'])
    create_enum_if_not_exists('followup_status', ['PENDIENTE', 'EN_PROCESO', 'COMPLETADO', 'CANCELADO'])
    create_enum_if_not_exists('followup_priority', ['BAJA', 'MEDIA', 'ALTA', 'URGENTE'])
    create_enum_if_not_exists('followup_channel', ['WHATSAPP', 'TELEFONO', 'EMAIL', 'PRESENCIAL'])
    create_enum_if_not_exists('cash_entry_type', ['INGRESO', 'EGRESO'])
    create_enum_if_not_exists('payment_method', ['EFECTIVO', 'TRANSFERENCIA', 'TARJETA', 'OTRO'])
    create_enum_if_not_exists('cash_payment_status', ['PENDIENTE', 'PAGADO', 'CANCELADO'])
    create_enum_if_not_exists('enrollment_status', ['ACTIVO', 'INACTIVO', 'LISTA_ESPERA', 'CANCELADO'])
    create_enum_if_not_exists('conversation_channel', ['WHATSAPP', 'INSTAGRAM', 'FACEBOOK', 'WEB'])
    create_enum_if_not_exists('conversation_type', ['GENERAL', 'PROSPECTO', 'SOPORTE', 'COMERCIAL'])
    create_enum_if_not_exists('conversation_status', ['NUEVA', 'BOT', 'HUMANO', 'CERRADA'])
    create_enum_if_not_exists('commercial_stage', ['NUEVO', 'CONTACTADO', 'CALIFICADO', 'PRESENTACION', 'NEGOCIACION', 'CIERRE_GANADO', 'CIERRE_PERDIDO', 'SEGUIMIENTO'])
    create_enum_if_not_exists('followup_action_type', ['LLAMADA', 'WHATSAPP', 'EMAIL', 'NOTA', 'TAREA', 'OTRO'])
    create_enum_if_not_exists('sender_type', ['USER', 'CONTACT', 'SYSTEM', 'BOT'])

    # --- CREATE TABLES ---

    op.create_table(
        'gym_classes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('service_kind', sa.Enum('FUNCIONAL', 'MUSCULACION', 'AMBOS', 'OTRO', name='service_kind', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('ACTIVA', 'INACTIVA', 'CANCELADA', name='class_status', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_gym_classes_name', 'gym_classes', ['name'], unique=False)
    op.create_index('ix_gym_classes_service_kind', 'gym_classes', ['service_kind'], unique=False)
    op.create_index('ix_gym_classes_status', 'gym_classes', ['status'], unique=False)

    op.create_table(
        'memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=False),
        sa.Column('kind', sa.Enum('MENSUAL', 'QUINCENAL', 'CLASES', 'OTRO', name='membership_kind', create_type=False), nullable=False),
        sa.Column('funcional_classes', sa.Integer(), nullable=True),
        sa.Column('musculacion_classes', sa.Integer(), nullable=True),
        sa.Column('funcional_unlimited', sa.Boolean(), nullable=False),
        sa.Column('musculacion_unlimited', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'message_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('kind', sa.Enum('GENERAL', 'RECORDATORIO_PAGO', 'BIENVENIDA', 'REACTIVACION', 'PROSPECTO', name='template_followup_kind', create_type=False), nullable=False),
        sa.Column('channel', sa.Enum('WHATSAPP', 'EMAIL', 'SMS', 'GENERAL', name='message_template_channel', create_type=False), nullable=False),
        sa.Column('subject', sa.String(length=180), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_message_templates_active_kind_channel_id', 'message_templates', ['is_active', 'kind', 'channel', 'id'], unique=False)
    op.create_index('ix_message_templates_channel', 'message_templates', ['channel'], unique=False)
    op.create_index('ix_message_templates_kind', 'message_templates', ['kind'], unique=False)
    op.create_index('ix_message_templates_name', 'message_templates', ['name'], unique=True)

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=120), nullable=False),
        sa.Column('last_name', sa.String(length=120), nullable=False),
        sa.Column('dni', sa.String(length=20), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('emergency_contact_name', sa.String(length=120), nullable=False),
        sa.Column('emergency_contact_phone', sa.String(length=30), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'PROFESOR', 'ALUMNO', 'RECEPCION', name='role_enum', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('must_change_password', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dni')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_role_is_active_last_name_first_name_id', 'users', ['role', 'is_active', 'last_name', 'first_name', 'id'], unique=False)

    op.create_table(
        'cash_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('ABIERTA', 'CERRADA', name='cash_session_status', create_type=False), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('opened_by_user_id', sa.Integer(), nullable=False),
        sa.Column('closed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('opening_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_income', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_expense', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('expected_closing_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('real_closing_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('difference_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('notes', sa.String(length=1000), nullable=False),
        sa.ForeignKeyConstraint(['closed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['opened_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cash_sessions_closed_by_user_id', 'cash_sessions', ['closed_by_user_id'], unique=False)
    op.create_index('ix_cash_sessions_opened_at', 'cash_sessions', ['opened_at'], unique=False)
    op.create_index('ix_cash_sessions_opened_by_user_id', 'cash_sessions', ['opened_by_user_id'], unique=False)
    op.create_index('ix_cash_sessions_status', 'cash_sessions', ['status'], unique=False)

    op.create_table(
        'class_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('weekday', sa.Enum('LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO', name='weekday_enum', create_type=False), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['class_id'], ['gym_classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_class_groups_class_id', 'class_groups', ['class_id'], unique=False)
    op.create_index('ix_class_groups_created_by_id', 'class_groups', ['created_by_id'], unique=False)
    op.create_index('ix_class_groups_is_active', 'class_groups', ['is_active'], unique=False)
    op.create_index('ix_class_groups_weekday', 'class_groups', ['weekday'], unique=False)

    op.create_table(
        'exercises',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('professor_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=False),
        sa.Column('muscle_group', sa.String(length=120), nullable=False),
        sa.Column('equipment', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['professor_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_exercises_professor_id', 'exercises', ['professor_id'], unique=False)
    op.create_index('ix_exercises_professor_name_id', 'exercises', ['professor_id', 'name', 'id'], unique=False)

    op.create_table(
        'membership_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('membership_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('payment_method', sa.Enum('EFECTIVO', 'TRANSFERENCIA', 'TARJETA', 'OTRO', name='payment_method', create_type=False), nullable=True),
        sa.Column('amount_snapshot', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('period_yyyymm', sa.String(length=7), nullable=True),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['membership_id'], ['memberships.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_membership_assignments_membership_id', 'membership_assignments', ['membership_id'], unique=False)
    op.create_index('ix_membership_assignments_student_id', 'membership_assignments', ['student_id'], unique=False)

    op.create_table(
        'membership_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('membership_id', sa.Integer(), nullable=False),
        sa.Column('payment_method', sa.Enum('EFECTIVO', 'TRANSFERENCIA', 'TARJETA', 'OTRO', name='payment_method', create_type=False), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['membership_id'], ['memberships.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_membership_prices_membership_id', 'membership_prices', ['membership_id'], unique=False)

    op.create_table(
        'profesor_alumnos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profesor_id', sa.Integer(), nullable=False),
        sa.Column('alumno_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['alumno_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['profesor_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profesor_id', 'alumno_id', name='uq_profesor_alumnos_profesor_alumno')
    )
    op.create_index('ix_profesor_alumnos_alumno_id', 'profesor_alumnos', ['alumno_id'], unique=False)
    op.create_index('ix_profesor_alumnos_profesor_id', 'profesor_alumnos', ['profesor_id'], unique=False)
    op.create_index('ix_profesor_alumnos_profesor_id_id', 'profesor_alumnos', ['profesor_id', 'id'], unique=False)

    op.create_table(
        'prospects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=180), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('source', sa.String(length=60), nullable=False),
        sa.Column('status', sa.Enum('NUEVO', 'CONTACTADO', 'INTERESADO', 'INSCRIPTO', 'DESCARTADO', name='prospect_status', create_type=False), nullable=False),
        sa.Column('interest_summary', sa.String(length=255), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_prospects_assigned_to_user_id', 'prospects', ['assigned_to_user_id'], unique=False)
    op.create_index('ix_prospects_created_at', 'prospects', ['created_at'], unique=False)
    op.create_index('ix_prospects_email', 'prospects', ['email'], unique=False)
    op.create_index('ix_prospects_full_name', 'prospects', ['full_name'], unique=False)
    op.create_index('ix_prospects_phone', 'prospects', ['phone'], unique=False)
    op.create_index('ix_prospects_status', 'prospects', ['status'], unique=False)

    op.create_table(
        'routines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('professor_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('notes', sa.String(length=2000), nullable=False),
        sa.Column('routine_type', sa.Enum('FUNCIONAL', 'MUSCULACION', 'PERSONALIZADA', name='routine_type', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['professor_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_routines_professor_id', 'routines', ['professor_id'], unique=False)
    op.create_index('ix_routines_professor_id_id', 'routines', ['professor_id', 'id'], unique=False)

    op.create_table(
        'student_followups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.Enum('GENERAL', 'COBRO', 'ASISTENCIA', 'TECNICO', 'COMERCIAL', name='followup_kind', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('PENDIENTE', 'EN_PROCESO', 'COMPLETADO', 'CANCELADO', name='followup_status', create_type=False), nullable=False),
        sa.Column('priority', sa.Enum('BAJA', 'MEDIA', 'ALTA', 'URGENTE', name='followup_priority', create_type=False), nullable=False),
        sa.Column('channel', sa.Enum('WHATSAPP', 'TELEFONO', 'EMAIL', 'PRESENCIAL', name='followup_channel', create_type=False), nullable=False),
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('next_contact_date', sa.Date(), nullable=True),
        sa.Column('contacted_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('external_ref', sa.String(length=180), nullable=False),
        sa.Column('result_summary', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_action_at', sa.DateTime(), nullable=True),
        sa.Column('last_action_type', sa.String(length=60), nullable=False),
        sa.Column('last_message_sent_at', sa.DateTime(), nullable=True),
        sa.Column('automation_enabled', sa.Boolean(), nullable=False),
        sa.Column('reminder_sent_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE')
    )
    op.create_index('ix_student_followups_channel', 'student_followups', ['channel'], unique=False)
    op.create_index('ix_student_followups_created_at', 'student_followups', ['created_at'], unique=False)
    op.create_index('ix_student_followups_created_by_id', 'student_followups', ['created_by_id'], unique=False)
    op.create_index('ix_student_followups_kind', 'student_followups', ['kind'], unique=False)
    op.create_index('ix_student_followups_priority', 'student_followups', ['priority'], unique=False)
    op.create_index('ix_student_followups_status', 'student_followups', ['status'], unique=False)
    op.create_index('ix_student_followups_student_id', 'student_followups', ['student_id'], unique=False)

    op.create_table(
        'cash_movements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('entry_type', sa.Enum('INGRESO', 'EGRESO', name='cash_entry_type', create_type=False), nullable=False),
        sa.Column('category', sa.String(length=60), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('membership_assignment_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('concept', sa.String(length=150), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=False),
        sa.Column('period_yyyymm', sa.String(length=7), nullable=True),
        sa.Column('payment_method', sa.Enum('EFECTIVO', 'TRANSFERENCIA', 'TARJETA', 'OTRO', name='payment_method', create_type=False), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', sa.Enum('PENDIENTE', 'PAGADO', 'CANCELADO', name='cash_payment_status', create_type=False), nullable=False),
        sa.Column('receipt_image_path', sa.String(length=255), nullable=True),
        sa.Column('receipt_note', sa.String(length=255), nullable=False),
        sa.Column('movement_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['membership_assignment_id'], ['membership_assignments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['cash_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cash_movements_category', 'cash_movements', ['category'], unique=False)
    op.create_index('ix_cash_movements_created_by_id', 'cash_movements', ['created_by_id'], unique=False)
    op.create_index('ix_cash_movements_entry_type', 'cash_movements', ['entry_type'], unique=False)
    op.create_index('ix_cash_movements_membership_assignment_id', 'cash_movements', ['membership_assignment_id'], unique=False)
    op.create_index('ix_cash_movements_movement_date', 'cash_movements', ['movement_date'], unique=False)
    op.create_index('ix_cash_movements_period_yyyymm', 'cash_movements', ['period_yyyymm'], unique=False)
    op.create_index('ix_cash_movements_session_id', 'cash_movements', ['session_id'], unique=False)
    op.create_index('ix_cash_movements_status', 'cash_movements', ['status'], unique=False)
    op.create_index('ix_cash_movements_student_id', 'cash_movements', ['student_id'], unique=False)

    op.create_table(
        'class_enrollments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVO', 'INACTIVO', 'LISTA_ESPERA', 'CANCELADO', name='enrollment_status', create_type=False), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['group_id'], ['class_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_class_enrollments_created_by_id', 'class_enrollments', ['created_by_id'], unique=False)
    op.create_index('ix_class_enrollments_group_id', 'class_enrollments', ['group_id'], unique=False)
    op.create_index('ix_class_enrollments_status', 'class_enrollments', ['status'], unique=False)
    op.create_index('ix_class_enrollments_student_id', 'class_enrollments', ['student_id'], unique=False)

    op.create_table(
        'contact_conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.Enum('WHATSAPP', 'INSTAGRAM', 'FACEBOOK', 'WEB', name='conversation_channel', create_type=False), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('external_chat_id', sa.String(length=180), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('prospect_id', sa.Integer(), nullable=True),
        sa.Column('followup_id', sa.Integer(), nullable=True),
        sa.Column('conversation_type', sa.Enum('GENERAL', 'PROSPECTO', 'SOPORTE', 'COMERCIAL', name='conversation_type', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('NUEVA', 'BOT', 'HUMANO', 'CERRADA', name='conversation_status', create_type=False), nullable=False),
        sa.Column('intent_last', sa.String(length=80), nullable=False),
        sa.Column('lead_temperature', sa.String(length=20), nullable=False),
        sa.Column('handoff_reason', sa.String(length=255), nullable=False),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('assistant_paused', sa.Boolean(), nullable=False),
        sa.Column('assistant_paused_at', sa.DateTime(), nullable=True),
        sa.Column('assistant_paused_by_user_id', sa.Integer(), nullable=True),
        sa.Column('commercial_stage', sa.Enum('NUEVO', 'CONTACTADO', 'CALIFICADO', 'PRESENTACION', 'NEGOCIACION', 'CIERRE_GANADO', 'CIERRE_PERDIDO', 'SEGUIMIENTO', name='commercial_stage', create_type=False), nullable=False),
        sa.Column('commercial_stage_updated_at', sa.DateTime(), nullable=True),
        sa.Column('commercial_stage_note', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assistant_paused_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['followup_id'], ['student_followups.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_contact_conversations_assigned_to_user_id', 'contact_conversations', ['assigned_to_user_id'], unique=False)
    op.create_index('ix_contact_conversations_assistant_paused', 'contact_conversations', ['assistant_paused'], unique=False)
    op.create_index('ix_contact_conversations_assistant_paused_by_user_id', 'contact_conversations', ['assistant_paused_by_user_id'], unique=False)
    op.create_index('ix_contact_conversations_channel', 'contact_conversations', ['channel'], unique=False)
    op.create_index('ix_contact_conversations_commercial_stage', 'contact_conversations', ['commercial_stage'], unique=False)
    op.create_index('ix_contact_conversations_conversation_type', 'contact_conversations', ['conversation_type'], unique=False)
    op.create_index('ix_contact_conversations_created_at', 'contact_conversations', ['created_at'], unique=False)
    op.create_index('ix_contact_conversations_external_chat_id', 'contact_conversations', ['external_chat_id'], unique=False)
    op.create_index('ix_contact_conversations_followup_id', 'contact_conversations', ['followup_id'], unique=False)
    op.create_index('ix_contact_conversations_phone', 'contact_conversations', ['phone'], unique=False)
    op.create_index('ix_contact_conversations_prospect_id', 'contact_conversations', ['prospect_id'], unique=False)
    op.create_index('ix_contact_conversations_status', 'contact_conversations', ['status'], unique=False)
    op.create_index('ix_contact_conversations_student_id', 'contact_conversations', ['student_id'], unique=False)

    op.create_table(
        'followup_actions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('followup_id', sa.Integer(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('action_type', sa.Enum('LLAMADA', 'WHATSAPP', 'EMAIL', 'NOTA', 'TAREA', 'OTRO', name='followup_action_type', create_type=False), nullable=False),
        sa.Column('channel', sa.Enum('WHATSAPP', 'TELEFONO', 'EMAIL', 'PRESENCIAL', name='followup_channel', create_type=False), nullable=True),
        sa.Column('summary', sa.String(length=255), nullable=False),
        sa.Column('payload_text', sa.Text(), nullable=False),
        sa.Column('external_ref', sa.String(length=180), nullable=False),
        sa.Column('delivery_status', sa.String(length=40), nullable=False),
        sa.Column('response_payload', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['followup_id'], ['student_followups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_followup_actions_action_type', 'followup_actions', ['action_type'], unique=False)
    op.create_index('ix_followup_actions_created_at', 'followup_actions', ['created_at'], unique=False)
    op.create_index('ix_followup_actions_created_by_id', 'followup_actions', ['created_by_id'], unique=False)
    op.create_index('ix_followup_actions_external_ref', 'followup_actions', ['external_ref'], unique=False)
    op.create_index('ix_followup_actions_followup_id', 'followup_actions', ['followup_id'], unique=False)

    op.create_table(
        'membership_usages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('service', sa.Enum('FUNCIONAL', 'MUSCULACION', 'AMBOS', 'OTRO', name='service_kind', create_type=False), nullable=False),
        sa.Column('used_at', sa.Date(), nullable=False),
        sa.Column('used_at_time', sa.Time(), nullable=True),
        sa.Column('period_yyyymm', sa.String(length=7), nullable=False),
        sa.Column('notes', sa.String(length=255), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['membership_assignments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_membership_usages_assignment_id', 'membership_usages', ['assignment_id'], unique=False)
    op.create_index('ix_membership_usages_period_yyyymm', 'membership_usages', ['period_yyyymm'], unique=False)
    op.create_index('ix_membership_usages_student_id', 'membership_usages', ['student_id'], unique=False)

    op.create_table(
        'routine_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('routine_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['routine_id'], ['routines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_routine_assignments_routine_active_id', 'routine_assignments', ['routine_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_routine_assignments_routine_id', 'routine_assignments', ['routine_id'], unique=False)
    op.create_index('ix_routine_assignments_student_active_created_at', 'routine_assignments', ['student_id', 'is_active', 'created_at'], unique=False)
    op.create_index('ix_routine_assignments_student_id', 'routine_assignments', ['student_id'], unique=False)
    op.create_index('ix_routine_assignments_student_id_id', 'routine_assignments', ['student_id', 'id'], unique=False)
    op.create_index('ux_routine_assignments_student_active', 'routine_assignments', ['student_id'], unique=True, postgresql_where=sa.text('is_active = true'))

    op.create_table(
        'routine_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('routine_id', sa.Integer(), nullable=False),
        sa.Column('exercise_id', sa.Integer(), nullable=False),
        sa.Column('day_label', sa.String(length=30), nullable=False),
        sa.Column('weekday', sa.String(length=12), nullable=False),
        sa.Column('sets', sa.Integer(), nullable=False),
        sa.Column('reps', sa.String(length=50), nullable=False),
        sa.Column('rest_seconds', sa.Integer(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['routine_id'], ['routines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_routine_items_exercise_id', 'routine_items', ['exercise_id'], unique=False)
    op.create_index('ix_routine_items_routine_day_weekday_order', 'routine_items', ['routine_id', 'day_label', 'weekday', 'order_index'], unique=False)
    op.create_index('ix_routine_items_routine_id', 'routine_items', ['routine_id'], unique=False)

    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('sender_type', sa.Enum('USER', 'CONTACT', 'SYSTEM', 'BOT', name='sender_type', create_type=False), nullable=False),
        sa.Column('is_inbound', sa.Boolean(), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('external_ref', sa.String(length=180), nullable=False),
        sa.Column('intent_detected', sa.String(length=80), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('generated_by_ai', sa.Boolean(), nullable=False),
        sa.Column('delivery_status', sa.String(length=40), nullable=False),
        sa.Column('raw_payload', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['contact_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversation_messages_conversation_id', 'conversation_messages', ['conversation_id'], unique=False)
    op.create_index('ix_conversation_messages_created_at', 'conversation_messages', ['created_at'], unique=False)
    op.create_index('ix_conversation_messages_external_ref', 'conversation_messages', ['external_ref'], unique=False)
    op.create_index('ix_conversation_messages_is_inbound', 'conversation_messages', ['is_inbound'], unique=False)
    op.create_index('ix_conversation_messages_sender_type', 'conversation_messages', ['sender_type'], unique=False)


def downgrade() -> None:
    op.drop_table('conversation_messages')
    op.drop_table('routine_items')
    op.drop_table('routine_assignments')
    op.drop_table('membership_usages')
    op.drop_table('followup_actions')
    op.drop_table('contact_conversations')
    op.drop_table('class_enrollments')
    op.drop_table('cash_movements')
    op.drop_table('student_followups')
    op.drop_table('routines')
    op.drop_table('prospects')
    op.drop_table('profesor_alumnos')
    op.drop_table('membership_prices')
    op.drop_table('membership_assignments')
    op.drop_table('exercises')
    op.drop_table('class_groups')
    op.drop_table('cash_sessions')
    op.drop_table('users')
    op.drop_table('message_templates')
    op.drop_table('memberships')
    op.drop_table('gym_classes')

    op.execute("DROP TYPE IF EXISTS sender_type")
    op.execute("DROP TYPE IF EXISTS followup_action_type")
    op.execute("DROP TYPE IF EXISTS commercial_stage")
    op.execute("DROP TYPE IF EXISTS conversation_status")
    op.execute("DROP TYPE IF EXISTS conversation_type")
    op.execute("DROP TYPE IF EXISTS conversation_channel")
    op.execute("DROP TYPE IF EXISTS enrollment_status")
    op.execute("DROP TYPE IF EXISTS cash_payment_status")
    op.execute("DROP TYPE IF EXISTS payment_method")
    op.execute("DROP TYPE IF EXISTS cash_entry_type")
    op.execute("DROP TYPE IF EXISTS followup_channel")
    op.execute("DROP TYPE IF EXISTS followup_priority")
    op.execute("DROP TYPE IF EXISTS followup_status")
    op.execute("DROP TYPE IF EXISTS followup_kind")
    op.execute("DROP TYPE IF EXISTS routine_type")
    op.execute("DROP TYPE IF EXISTS prospect_status")
    op.execute("DROP TYPE IF EXISTS weekday_enum")
    op.execute("DROP TYPE IF EXISTS cash_session_status")
    op.execute("DROP TYPE IF EXISTS role_enum")
    op.execute("DROP TYPE IF EXISTS message_template_channel")
    op.execute("DROP TYPE IF EXISTS template_followup_kind")
    op.execute("DROP TYPE IF EXISTS membership_kind")
    op.execute("DROP TYPE IF EXISTS class_status")
    op.execute("DROP TYPE IF EXISTS service_kind")
