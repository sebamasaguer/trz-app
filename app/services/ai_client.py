import json
from typing import Any

import httpx

from ..core.config import settings


def call_openai_agent(payload: dict[str, Any], fallback_fn) -> dict[str, Any]:
    if not settings.OPENAI_API_KEY:
        return fallback_fn(
            payload.get("incoming_text", ""),
            payload.get("recent_messages", []),
        )

    system_prompt = """
Sos el asistente comercial virtual de TRZ Funcional.
Tu trabajo es conversar por WhatsApp con alumnos inactivos y nuevos prospectos.

Reglas:
- Responder en español rioplatense, tono cálido, comercial y concreto.
- Ser claro y breve.
- Usar solo la información provista.
- No inventar datos.
- No derivar a humano salvo pedido explícito, intención fuerte de cierre, pago, reclamo o baja confianza.
- Si el usuario pregunta horarios, membresías o planes, precios o franjas horarias, seguir conversando sin derivar.
- Siempre devolver JSON válido.

Formato de salida obligatorio:
{
  "reply_text": "...",
  "intent": "...",
  "confidence": 0.0,
  "next_step": "...",
  "should_create_task": false,
  "should_handoff_human": false,
  "lead_temperature": "cold|warm|hot",
  "handoff_reason": ""
}
""".strip()

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }

    try:
        with httpx.Client(timeout=25.0) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            parsed.setdefault("reply_text", "")
            parsed.setdefault("intent", "general_query")
            parsed.setdefault("confidence", 0.5)
            parsed.setdefault("next_step", "answer_general")
            parsed.setdefault("should_create_task", False)
            parsed.setdefault("should_handoff_human", False)
            parsed.setdefault("lead_temperature", "cold")
            parsed.setdefault("handoff_reason", "")
            return parsed
    except Exception:
        return fallback_fn(
            payload.get("incoming_text", ""),
            payload.get("recent_messages", []),
        )