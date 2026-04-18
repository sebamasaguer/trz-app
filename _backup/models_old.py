import enum
from datetime import datetime, date, time

from sqlalchemy import (
    String,
    DateTime,
    Boolean,
    Enum as SAEnum,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .db import Base


class RoutineType(str, enum.Enum):
    DIAS = "DIAS"
    SEMANAS = "SEMANAS"


class Role(str, enum.Enum):
    ADMINISTRADOR = "ADMINISTRADOR"
    ADMINISTRATIVO = "ADMINISTRATIVO"
    PROFESOR = "PROFESOR"
    ALUMNO = "ALUMNO"


class MembershipKind(str, enum.Enum):
    FUNCIONAL = "FUNCIONAL"
    MUSCULACION = "MUSCULACION"
    COMBINACION = "COMBINACION"
    CLASE_SUELTA = "CLASE_SUELTA"


class PaymentMethod(str, enum.Enum):
    LISTA = "LISTA"
    EFECTIVO = "EFECTIVO"
    TRANSFERENCIA = "TRANSFERENCIA"


class ServiceKind(str, enum.Enum):
    FUNCIONAL = "FUNCIONAL"
    MUSCULACION = "MUSCULACION"


class CashEntryType(str, enum.Enum):
    INGRESO = "INGRESO"
    EGRESO = "EGRESO"


class CashPaymentStatus(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    ACREDITADO = "ACREDITADO"
    ANULADO = "ANULADO"


class CashSessionStatus(str, enum.Enum):
    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"


class CashExpenseCategory(str, enum.Enum):
    MEMBRESIA = "MEMBRESIA"
    INSUMOS = "INSUMOS"
    LIMPIEZA = "LIMPIEZA"
    MANTENIMIENTO = "MANTENIMIENTO"
    SERVICIOS = "SERVICIOS"
    SUELDOS = "SUELDOS"
    VARIOS = "VARIOS"

class CommercialStage(str, enum.Enum):
    NUEVO = "NUEVO"
    INTERESADO = "INTERESADO"
    CALIFICADO = "CALIFICADO"
    NEGOCIANDO = "NEGOCIANDO"
    DERIVADO = "DERIVADO"
    REACTIVADO = "REACTIVADO"
    CERRADO = "CERRADO"
    PERDIDO = "PERDIDO"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    first_name: Mapped[str] = mapped_column(String(120), default="")
    last_name: Mapped[str] = mapped_column(String(120), default="")
    dni: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    emergency_contact_name: Mapped[str] = mapped_column(String(120), default="")
    emergency_contact_phone: Mapped[str] = mapped_column(String(30), default="")

    full_name: Mapped[str] = mapped_column(String(255), default="")

    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SAEnum(Role, name="role_enum"), default=Role.ALUMNO)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    cash_sessions_opened: Mapped[list["CashSession"]] = relationship(
        back_populates="opened_by",
        foreign_keys="CashSession.opened_by_user_id",
    )
    cash_sessions_closed: Mapped[list["CashSession"]] = relationship(
        back_populates="closed_by",
        foreign_keys="CashSession.closed_by_user_id",
    )
    cash_movements_created: Mapped[list["CashMovement"]] = relationship(
        back_populates="created_by",
        foreign_keys="CashMovement.created_by_id",
    )

    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        today = date.today()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(1000), default="")
    muscle_group: Mapped[str] = mapped_column(String(120), default="")
    equipment: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    professor = relationship("User", lazy="joined")


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(primary_key=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(180))
    notes: Mapped[str] = mapped_column(String(2000), default="")
    routine_type: Mapped[RoutineType] = mapped_column(
        SAEnum(RoutineType, name="routine_type"),
        default=RoutineType.DIAS,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    professor = relationship("User", lazy="joined")
    items = relationship("RoutineItem", cascade="all, delete-orphan", back_populates="routine")


class RoutineItem(Base):
    __tablename__ = "routine_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="RESTRICT"), index=True)

    day_label: Mapped[str] = mapped_column(String(30), default="")
    weekday: Mapped[str] = mapped_column(String(12), default="")

    sets: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[str] = mapped_column(String(50), default="")
    rest_seconds: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(String(500), default="")

    routine = relationship("Routine", back_populates="items")
    exercise = relationship("Exercise", lazy="joined")


class RoutineAssignment(Base):
    __tablename__ = "routine_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    routine = relationship("Routine", lazy="joined")
    student = relationship("User", foreign_keys=[student_id], lazy="joined")
    professor = relationship("User", foreign_keys=[assigned_by], lazy="joined")


class ProfesorAlumno(Base):
    __tablename__ = "profesor_alumnos"

    id: Mapped[int] = mapped_column(primary_key=True)
    profesor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profesor = relationship("User", foreign_keys=[profesor_id], lazy="joined")
    alumno = relationship("User", foreign_keys=[alumno_id], lazy="joined")


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(180))
    kind: Mapped[MembershipKind] = mapped_column(SAEnum(MembershipKind, name="membership_kind"))

    funcional_classes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    musculacion_classes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    funcional_unlimited: Mapped[bool] = mapped_column(Boolean, default=False)
    musculacion_unlimited: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    prices: Mapped[list["MembershipPrice"]] = relationship(
        back_populates="membership",
        cascade="all, delete-orphan",
    )


class MembershipPrice(Base):
    __tablename__ = "membership_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id", ondelete="CASCADE"), index=True)

    payment_method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, name="payment_method"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))

    membership: Mapped["Membership"] = relationship(back_populates="prices")


class MembershipAssignment(Base):
    __tablename__ = "membership_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)

    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method"),
        nullable=True,
    )
    amount_snapshot: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    period_yyyymm: Mapped[str | None] = mapped_column(String(7), nullable=True)

    membership: Mapped["Membership"] = relationship()
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    assigned_by_user: Mapped["User"] = relationship(foreign_keys=[assigned_by])


class MembershipUsage(Base):
    __tablename__ = "membership_usages"

    id: Mapped[int] = mapped_column(primary_key=True)

    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("membership_assignments.id", ondelete="CASCADE"),
        index=True,
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    service: Mapped[ServiceKind] = mapped_column(SAEnum(ServiceKind, name="service_kind"))

    used_at: Mapped[date] = mapped_column(Date, nullable=False)
    used_at_time: Mapped[time | None] = mapped_column(nullable=True)
    period_yyyymm: Mapped[str] = mapped_column(String(7), index=True)

    notes: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assignment: Mapped["MembershipAssignment"] = relationship()
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    created_by_user: Mapped["User"] = relationship(foreign_keys=[created_by])


class CashSession(Base):
    __tablename__ = "cash_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    status: Mapped[CashSessionStatus] = mapped_column(
        SAEnum(CashSessionStatus, name="cash_session_status"),
        default=CashSessionStatus.ABIERTA,
        index=True,
    )

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opened_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    closed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    opening_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_income: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_expense: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    expected_closing_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    real_closing_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    difference_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    notes: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    opened_by: Mapped["User"] = relationship(
        back_populates="cash_sessions_opened",
        foreign_keys=[opened_by_user_id],
    )
    closed_by: Mapped["User | None"] = relationship(
        back_populates="cash_sessions_closed",
        foreign_keys=[closed_by_user_id],
    )

    movements: Mapped[list["CashMovement"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class CashMovement(Base):
    __tablename__ = "cash_movements"

    id: Mapped[int] = mapped_column(primary_key=True)

    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("cash_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    entry_type: Mapped[CashEntryType] = mapped_column(
        SAEnum(CashEntryType, name="cash_entry_type"),
        default=CashEntryType.INGRESO,
        index=True,
    )

    category: Mapped[str] = mapped_column(String(60), default=CashExpenseCategory.MEMBRESIA.value, index=True)

    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    membership_assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("membership_assignments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    concept: Mapped[str] = mapped_column(String(150), default="Pago membresía")
    notes: Mapped[str] = mapped_column(String(500), default="")

    period_yyyymm: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)

    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method"),
        nullable=True,
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    status: Mapped[CashPaymentStatus] = mapped_column(
        SAEnum(CashPaymentStatus, name="cash_payment_status"),
        default=CashPaymentStatus.ACREDITADO,
        index=True,
    )

    receipt_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt_note: Mapped[str] = mapped_column(String(255), default="")
    movement_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["CashSession | None"] = relationship(back_populates="movements")
    student: Mapped["User | None"] = relationship(foreign_keys=[student_id])
    created_by: Mapped["User | None"] = relationship(
        back_populates="cash_movements_created",
        foreign_keys=[created_by_id],
    )
    membership_assignment: Mapped["MembershipAssignment | None"] = relationship()

class FollowupKind(str, enum.Enum):
    MOROSIDAD = "MOROSIDAD"
    INACTIVIDAD = "INACTIVIDAD"
    GENERAL = "GENERAL"


class FollowupStatus(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    CONTACTADO = "CONTACTADO"
    RESPONDIO = "RESPONDIO"
    REACTIVADO = "REACTIVADO"
    DESCARTADO = "DESCARTADO"

class FollowupPriority(str, enum.Enum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    CRITICA = "CRITICA"


class FollowupChannel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    LLAMADA = "LLAMADA"
    PRESENCIAL = "PRESENCIAL"
    OTRO = "OTRO"


class StudentFollowup(Base):
    __tablename__ = "student_followups"

    id: Mapped[int] = mapped_column(primary_key=True)

    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    kind: Mapped[FollowupKind] = mapped_column(
        SAEnum(FollowupKind, name="followup_kind"),
        default=FollowupKind.GENERAL,
        index=True,
    )

    status: Mapped[FollowupStatus] = mapped_column(
        SAEnum(FollowupStatus, name="followup_status"),
        default=FollowupStatus.PENDIENTE,
        index=True,
    )

    priority: Mapped[FollowupPriority] = mapped_column(
        SAEnum(FollowupPriority, name="followup_priority"),
        default=FollowupPriority.MEDIA,
        index=True,
    )

    channel: Mapped[FollowupChannel] = mapped_column(
        SAEnum(FollowupChannel, name="followup_channel"),
        default=FollowupChannel.WHATSAPP,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(180), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    next_contact_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    external_ref: Mapped[str] = mapped_column(String(180), default="")  # id de whatsapp/email futuro
    result_summary: Mapped[str] = mapped_column(String(255), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])

    last_action_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_action_type: Mapped[str] = mapped_column(String(60), default="")
    last_message_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class MessageTemplateChannel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    GENERAL = "GENERAL"


class FollowupActionType(str, enum.Enum):
    MENSAJE_ENVIADO = "MENSAJE_ENVIADO"
    LLAMADA = "LLAMADA"
    EMAIL_ENVIADO = "EMAIL_ENVIADO"
    WHATSAPP_ENVIADO = "WHATSAPP_ENVIADO"
    RECORDATORIO = "RECORDATORIO"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"
    NOTA = "NOTA"

class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    kind: Mapped[FollowupKind] = mapped_column(
        SAEnum(FollowupKind, name="template_followup_kind"),
        default=FollowupKind.GENERAL,
        index=True,
    )
    channel: Mapped[MessageTemplateChannel] = mapped_column(
        SAEnum(MessageTemplateChannel, name="message_template_channel"),
        default=MessageTemplateChannel.GENERAL,
        index=True,
    )

    subject: Mapped[str] = mapped_column(String(180), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FollowupAction(Base):
    __tablename__ = "followup_actions"

    id: Mapped[int] = mapped_column(primary_key=True)

    followup_id: Mapped[int] = mapped_column(ForeignKey("student_followups.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    action_type: Mapped[FollowupActionType] = mapped_column(
        SAEnum(FollowupActionType, name="followup_action_type"),
        default=FollowupActionType.NOTA,
        index=True,
    )

    channel: Mapped[FollowupChannel | None] = mapped_column(
        SAEnum(FollowupChannel, name="followup_channel"),
        nullable=True,
    )

    summary: Mapped[str] = mapped_column(String(255), default="")
    payload_text: Mapped[str] = mapped_column(Text, default="")
    external_ref: Mapped[str] = mapped_column(String(180), default="")
    delivery_status: Mapped[str] = mapped_column(String(40), default="")
    response_payload: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    followup: Mapped["StudentFollowup"] = relationship(foreign_keys=[followup_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])

class ProspectStatus(str, enum.Enum):
    NUEVO = "NUEVO"
    CALIFICANDO = "CALIFICANDO"
    INTERESADO = "INTERESADO"
    DERIVADO = "DERIVADO"
    CERRADO = "CERRADO"
    DESCARTADO = "DESCARTADO"


class ConversationType(str, enum.Enum):
    REACTIVACION = "REACTIVACION"
    NUEVO_PROSPECTO = "NUEVO_PROSPECTO"
    SOPORTE = "SOPORTE"
    GENERAL = "GENERAL"


class ConversationStatus(str, enum.Enum):
    ABIERTA = "ABIERTA"
    EN_AUTOMATICO = "EN_AUTOMATICO"
    DERIVADA_A_HUMANO = "DERIVADA_A_HUMANO"
    CERRADA = "CERRADA"


class SenderType(str, enum.Enum):
    BOT = "BOT"
    HUMANO = "HUMANO"
    ALUMNO = "ALUMNO"
    PROSPECTO = "PROSPECTO"
    SISTEMA = "SISTEMA"


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(primary_key=True)

    full_name: Mapped[str] = mapped_column(String(180), default="", index=True)
    phone: Mapped[str] = mapped_column(String(30), default="", index=True)
    email: Mapped[str] = mapped_column(String(255), default="", index=True)

    source: Mapped[str] = mapped_column(String(60), default="WHATSAPP")
    status: Mapped[ProspectStatus] = mapped_column(
        SAEnum(ProspectStatus, name="prospect_status"),
        default=ProspectStatus.NUEVO,
        index=True,
    )

    interest_summary: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_user_id])


class ContactConversation(Base):
    __tablename__ = "contact_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)

    channel: Mapped[FollowupChannel] = mapped_column(
        SAEnum(FollowupChannel, name="conversation_channel"),
        default=FollowupChannel.WHATSAPP,
        index=True,
    )

    phone: Mapped[str] = mapped_column(String(30), default="", index=True)
    external_chat_id: Mapped[str] = mapped_column(String(180), default="", index=True)

    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prospect_id: Mapped[int | None] = mapped_column(
        ForeignKey("prospects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    followup_id: Mapped[int | None] = mapped_column(
        ForeignKey("student_followups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    conversation_type: Mapped[ConversationType] = mapped_column(
        SAEnum(ConversationType, name="conversation_type"),
        default=ConversationType.GENERAL,
        index=True,
    )

    status: Mapped[ConversationStatus] = mapped_column(
        SAEnum(ConversationStatus, name="conversation_status"),
        default=ConversationStatus.ABIERTA,
        index=True,
    )

    intent_last: Mapped[str] = mapped_column(String(80), default="")
    lead_temperature: Mapped[str] = mapped_column(String(20), default="cold")
    handoff_reason: Mapped[str] = mapped_column(String(255), default="")

    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student: Mapped["User | None"] = relationship(foreign_keys=[student_id])
    prospect: Mapped["Prospect | None"] = relationship(foreign_keys=[prospect_id])
    followup: Mapped["StudentFollowup | None"] = relationship(foreign_keys=[followup_id])
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_user_id])
    assistant_paused: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    assistant_paused_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assistant_paused_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    assistant_paused_by: Mapped["User | None"] = relationship(foreign_keys=[assistant_paused_by_user_id])
    commercial_stage: Mapped[CommercialStage] = mapped_column(
    SAEnum(CommercialStage, name="commercial_stage"),
    default=CommercialStage.NUEVO,
    index=True,
)
    
    commercial_stage_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    commercial_stage_note: Mapped[str] = mapped_column(String(255), default="")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("contact_conversations.id", ondelete="CASCADE"),
        index=True,
    )

    sender_type: Mapped[SenderType] = mapped_column(
        SAEnum(SenderType, name="sender_type"),
        default=SenderType.SISTEMA,
        index=True,
    )

    is_inbound: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    message_text: Mapped[str] = mapped_column(Text, default="")
    external_ref: Mapped[str] = mapped_column(String(180), default="", index=True)

    intent_detected: Mapped[str] = mapped_column(String(80), default="")
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    generated_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)

    delivery_status: Mapped[str] = mapped_column(String(40), default="")
    raw_payload: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    conversation: Mapped["ContactConversation"] = relationship(foreign_keys=[conversation_id])

class ClassStatus(str, enum.Enum):
    ACTIVA = "ACTIVA"
    INACTIVA = "INACTIVA"


class Weekday(str, enum.Enum):
    LUNES = "LUNES"
    MARTES = "MARTES"
    MIERCOLES = "MIERCOLES"
    JUEVES = "JUEVES"
    VIERNES = "VIERNES"
    SABADO = "SABADO"
    DOMINGO = "DOMINGO"


class GymClass(Base):
    __tablename__ = "gym_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    service_kind: Mapped[ServiceKind] = mapped_column(
        SAEnum(ServiceKind, name="service_kind"),
        default=ServiceKind.FUNCIONAL,
        index=True,
    )
    status: Mapped[ClassStatus] = mapped_column(
        SAEnum(ClassStatus, name="class_status"),
        default=ClassStatus.ACTIVA,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    groups: Mapped[list["ClassGroup"]] = relationship(
        back_populates="gym_class",
        cascade="all, delete-orphan",
    )

class ClassGroup(Base):
    __tablename__ = "class_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("gym_classes.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(120), default="")
    weekday: Mapped[Weekday] = mapped_column(
        SAEnum(Weekday, name="weekday_enum"),
        index=True,
    )
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    capacity: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    gym_class: Mapped["GymClass"] = relationship(back_populates="groups")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])

    enrollments: Mapped[list["ClassEnrollment"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class EnrollmentStatus(str, enum.Enum):
    ACTIVA = "ACTIVA"
    CANCELADA = "CANCELADA"


class ClassEnrollment(Base):
    __tablename__ = "class_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("class_groups.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    status: Mapped[EnrollmentStatus] = mapped_column(
        SAEnum(EnrollmentStatus, name="enrollment_status"),
        default=EnrollmentStatus.ACTIVA,
        index=True,
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    group: Mapped["ClassGroup"] = relationship(back_populates="enrollments", foreign_keys=[group_id])
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])