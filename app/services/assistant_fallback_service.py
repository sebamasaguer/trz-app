from ..core.config import settings


def _normalize_text_basic(text: str | None) -> str:
    t = (text or "").strip().lower()
    repl = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
    }
    for k, v in repl.items():
        t = t.replace(k, v)
    return " ".join(t.split())


def local_intent_fallback(text: str, recent_messages: list[dict] | None = None) -> dict:
    t = _normalize_text_basic(text)
    recent_messages = recent_messages or []

    history_text = " ".join(
        _normalize_text_basic(message.get("text", "")) for message in recent_messages[-8:]
    )

    if any(
        x in t
        for x in [
            "hablar con alguien",
            "hablar con una persona",
            "persona",
            "asesor",
            "asesora",
            "humano",
            "vendedor",
            "encargado",
        ]
    ):
        return {
            "reply_text": f"Perfecto. Te derivamos con {settings.TRZ_HUMAN_HANDOFF_NAME} para seguir por acá y ayudarte mejor.",
            "intent": "handoff_requested",
            "confidence": 0.95,
            "next_step": "handoff_human",
            "should_create_task": True,
            "should_handoff_human": True,
            "lead_temperature": "hot",
            "handoff_reason": "Pidió hablar con una persona",
        }

    if any(
        x in t
        for x in [
            "quiero volver",
            "quiero arrancar",
            "quiero empezar",
            "me interesa",
            "horario",
            "horarios",
        ]
    ):
        return {
            "reply_text": "¡Buenísimo! Te ayudo. Contame si preferís mañana, tarde o noche, y también te paso las opciones de membresía disponibles.",
            "intent": "interes_alto",
            "confidence": 0.82,
            "next_step": "ask_schedule_preference",
            "should_create_task": True,
            "should_handoff_human": False,
            "lead_temperature": "warm",
            "handoff_reason": "",
        }

    if any(x in t for x in ["mañana", "manana", "tarde", "noche"]):
        franja = "mañana"
        if "tarde" in t:
            franja = "tarde"
        elif "noche" in t:
            franja = "noche"

        return {
            "reply_text": f"Perfecto, te interesa el turno {franja}. También puedo pasarte las opciones de membresía y ayudarte a coordinar el ingreso. ¿Querés que te pase precios?",
            "intent": "schedule_preference_defined",
            "confidence": 0.88,
            "next_step": "offer_prices",
            "should_create_task": True,
            "should_handoff_human": False,
            "lead_temperature": "warm",
            "handoff_reason": "",
        }

    if any(
        x in t
        for x in [
            "precio",
            "precios",
            "cuanto sale",
            "cuánto sale",
            "valor",
            "valores",
            "membresia",
            "membresía",
            "plan",
            "planes",
        ]
    ):
        return {
            "reply_text": "Perfecto. Te puedo pasar las opciones de membresía disponibles y ayudarte a elegir la que más te convenga. Si querés, también te derivamos con una persona para cerrar tu ingreso.",
            "intent": "price_request",
            "confidence": 0.86,
            "next_step": "inform_membership_options",
            "should_create_task": True,
            "should_handoff_human": False,
            "lead_temperature": "warm",
            "handoff_reason": "",
        }

    if any(
        x in t
        for x in [
            "quiero inscribirme",
            "quiero anotarme",
            "quiero pagar",
            "quiero ir",
            "quiero empezar ya",
            "quiero arrancar mañana",
        ]
    ):
        return {
            "reply_text": f"Excelente. Ya estás para avanzar 🙌 Si querés, te derivamos con {settings.TRZ_HUMAN_HANDOFF_NAME} para coordinar tu ingreso.",
            "intent": "ready_to_close",
            "confidence": 0.92,
            "next_step": "offer_handoff",
            "should_create_task": True,
            "should_handoff_human": True,
            "lead_temperature": "hot",
            "handoff_reason": "Intención alta de cierre",
        }

    if any(k in history_text for k in ["horario", "horarios", "membresia", "membresía", "precio", "precios"]):
        return {
            "reply_text": "Perfecto. También puedo pasarte las opciones de membresía o derivarte con una persona para coordinar tu ingreso. ¿Qué preferís?",
            "intent": "contextual_followup",
            "confidence": 0.72,
            "next_step": "offer_membership_or_handoff",
            "should_create_task": False,
            "should_handoff_human": False,
            "lead_temperature": "warm",
            "handoff_reason": "",
        }

    return {
        "reply_text": "Gracias por tu mensaje. Te ayudo con horarios, clases, membresías o inscripción. ¿Qué te gustaría saber primero?",
        "intent": "general_query",
        "confidence": 0.60,
        "next_step": "answer_general",
        "should_create_task": False,
        "should_handoff_human": False,
        "lead_temperature": "cold",
        "handoff_reason": "",
    }