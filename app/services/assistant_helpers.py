"""
Compatibilidad temporal.

Este módulo reexporta funciones del asistente separadas por responsabilidad.
No agregar lógica nueva acá.
Migrar imports nuevos a:
- assistant_identity_service
- assistant_conversation_service
- assistant_lead_service
- assistant_fallback_service
- assistant_view_support_service
"""

from .assistant_identity_service import (
    normalize_phone,
    find_student_by_phone,
    find_or_create_prospect,
)
from .assistant_conversation_service import (
    find_or_create_conversation,
    save_conversation_message,
    build_recent_messages,
)
from .assistant_lead_service import (
    find_open_followup_for_student,
    ensure_followup_for_reactivation,
    create_handoff_action,
    infer_commercial_stage,
)
from .assistant_fallback_service import local_intent_fallback

__all__ = [
    "normalize_phone",
    "find_student_by_phone",
    "find_or_create_prospect",
    "find_or_create_conversation",
    "save_conversation_message",
    "build_recent_messages",
    "find_open_followup_for_student",
    "ensure_followup_for_reactivation",
    "create_handoff_action",
    "infer_commercial_stage",
    "local_intent_fallback",
]