from datetime import date, datetime

from app.utils.datetime_utils import utcnow_naive

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .enums import (
    FollowupActionType,
    FollowupChannel,
    FollowupKind,
    FollowupPriority,
    FollowupStatus,
    MessageTemplateChannel,
)


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

    external_ref: Mapped[str] = mapped_column(String(180), default="")
    result_summary: Mapped[str] = mapped_column(String(255), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])

    last_action_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_action_type: Mapped[str] = mapped_column(String(60), default="")
    last_message_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outbound_in_progress: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_outbound_ref: Mapped[str] = mapped_column(String(180), default="", index=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MessageTemplate(Base):
    __tablename__ = "message_templates"
    __table_args__ = (
        Index(
            "ix_message_templates_active_kind_channel_id",
            "is_active",
            "kind",
            "channel",
            "id",
        ),
    )

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

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


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
    external_ref: Mapped[str] = mapped_column(String(180), default="", index=True)
    delivery_status: Mapped[str] = mapped_column(String(40), default="")
    response_payload: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)

    followup: Mapped["StudentFollowup"] = relationship(foreign_keys=[followup_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])