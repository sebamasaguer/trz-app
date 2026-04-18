from ..models import ContactConversation, ConversationMessage, CommercialStage, ConversationStatus


def get_conversation_suggestions(row: ContactConversation) -> list[str]:
    suggestions: list[str] = []

    if getattr(row, "assistant_paused", False):
        suggestions.append("Reanudar asistente")
    else:
        suggestions.append("Pausar asistente")

    if getattr(row, "status", None) != ConversationStatus.DERIVADA_A_HUMANO:
        suggestions.append("Derivar a humano")

    stage = getattr(row, "commercial_stage", None)

    if stage in [CommercialStage.NUEVO, CommercialStage.INTERESADO]:
        suggestions.append("Enviar precios")
        suggestions.append("Consultar horario preferido")

    if stage in [CommercialStage.CALIFICADO, CommercialStage.NEGOCIANDO]:
        suggestions.append("Ofrecer cierre con asesor")
        suggestions.append("Registrar como reactivado")

    if getattr(row, "followup_id", None):
        suggestions.append("Ver seguimiento")

    return suggestions


def build_commercial_summary(
    row: ContactConversation,
    messages: list[ConversationMessage],
) -> dict:
    inbound_count = 0
    outbound_count = 0
    last_inbound_text = ""
    last_outbound_text = ""

    for msg in messages:
        if getattr(msg, "is_inbound", False):
            inbound_count += 1
            last_inbound_text = msg.message_text or ""
        else:
            outbound_count += 1
            last_outbound_text = msg.message_text or ""

    return {
        "conversation_id": row.id,
        "status": row.status.value if getattr(row, "status", None) else "",
        "commercial_stage": row.commercial_stage.value if getattr(row, "commercial_stage", None) else "",
        "lead_temperature": getattr(row, "lead_temperature", "") or "",
        "assistant_paused": bool(getattr(row, "assistant_paused", False)),
        "has_followup": bool(getattr(row, "followup_id", None)),
        "has_prospect": bool(getattr(row, "prospect_id", None)),
        "handoff_reason": getattr(row, "handoff_reason", "") or "",
        "intent_last": getattr(row, "intent_last", "") or "",
        "total_messages": len(messages),
        "inbound_messages": inbound_count,
        "outbound_messages": outbound_count,
        "last_inbound_text": last_inbound_text,
        "last_outbound_text": last_outbound_text,
    }