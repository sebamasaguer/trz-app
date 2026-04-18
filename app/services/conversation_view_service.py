from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ContactConversation, ConversationMessage

from .assistant_view_support_service import (
    get_conversation_suggestions,
    build_commercial_summary,
)


def get_conversation_messages(db: Session, conversation_id: int) -> list[ConversationMessage]:
    return db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.id.asc())
    ).all()


def build_conversation_detail_context(db: Session, row: ContactConversation) -> dict:
    messages = get_conversation_messages(db, row.id)

    contact_name = ""
    contact_email = ""
    contact_phone = row.phone or ""

    if row.student:
        contact_name = row.student.full_name or ""
        contact_email = row.student.email or ""
    elif row.prospect:
        contact_name = row.prospect.full_name or ""
        contact_email = row.prospect.email or ""

    suggestions = get_conversation_suggestions(row)
    commercial_summary = build_commercial_summary(row, messages)

    return {
        "messages": messages,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "suggestions": suggestions,
        "commercial_summary": commercial_summary,
    }