from datetime import date, datetime
from app.utils.datetime_utils import utcnow_naive

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Numeric

from ..db import Base
from .enums import (
    CommercialStage,
    ConversationStatus,
    ConversationType,
    FollowupChannel,
    ProspectStatus,
    SenderType,
)


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

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

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

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

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

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)

    conversation: Mapped["ContactConversation"] = relationship(foreign_keys=[conversation_id])