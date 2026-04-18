from datetime import date, timedelta
from urllib.parse import quote

from sqlalchemy import select

from ..models import (
    User,
    StudentFollowup,
    FollowupKind,
    FollowupStatus,
    FollowupPriority,
    MessageTemplate,
    MessageTemplateChannel,
)


def normalize_phone_ar(phone: str | None) -> str:
    raw = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not raw:
        return ""
    if raw.startswith("54"):
        return raw
    if raw.startswith("0"):
        raw = raw[1:]
    return f"54{raw}"


def phone_last10(phone: str | None) -> str:
    norm = normalize_phone_ar(phone)
    return norm[-10:] if norm else ""


def extract_digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def normalize_text_basic(text: str | None) -> str:
    t = (text or "").strip().lower()
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }
    for k, v in replacements.items():
        t = t.replace(k, v)
    return t


def classify_inbound_intent(text: str | None) -> str:
    t = normalize_text_basic(text)

    if not t:
        return "NEUTRO"

    positive_terms = [
        "si", "sí", "dale", "quiero", "me interesa", "voy", "ire", "iré",
        "vuelvo", "retomo", "retomar", "cuando puedo", "cuando voy",
        "quiero volver", "me gustaria volver", "me gustaría volver",
        "pasenme info", "pasen info", "mandame info", "mandame informacion",
        "mandame información", "quiero arrancar", "quiero empezar",
        "ok", "oka", "genial", "perfecto", "de una",
    ]

    negative_terms = [
        "no", "no quiero", "no me interesa", "no gracias", "gracias no",
        "no voy", "no vuelvo", "no puedo", "dejame", "dejame de escribir",
        "dejenme de escribir", "dejen de escribir", "baja", "dar de baja",
        "cancelar", "cancela", "no molestar", "no contactar",
        "no me contacten", "no escribir", "stop",
    ]

    for term in negative_terms:
        if term in t:
            return "NEGATIVO"

    for term in positive_terms:
        if term in t:
            return "POSITIVO"

    return "NEUTRO"


def infer_priority(kind: str, status: str, next_contact_date: date | None) -> FollowupPriority:
    today = date.today()

    if status in ["REACTIVADO", "DESCARTADO"]:
        return FollowupPriority.BAJA

    if next_contact_date:
        if next_contact_date < today:
            return FollowupPriority.CRITICA
        if next_contact_date == today:
            return FollowupPriority.ALTA
        if next_contact_date <= today + timedelta(days=7):
            return FollowupPriority.MEDIA

    if kind == "MOROSIDAD":
        return FollowupPriority.ALTA
    if kind == "INACTIVIDAD":
        return FollowupPriority.MEDIA

    return FollowupPriority.MEDIA


def status_group_title(status_value: str) -> str:
    mapping = {
        "PENDIENTE": "Pendiente",
        "CONTACTADO": "Contactado",
        "RESPONDIO": "Respondió",
        "REACTIVADO": "Reactivado",
        "DESCARTADO": "Descartado",
    }
    return mapping.get(status_value, status_value)


def render_template_text(template_body: str, student: User, row: StudentFollowup | None = None) -> str:
    nombre = (student.full_name or student.first_name or student.email or "Hola").strip()
    data = {
        "{nombre}": nombre,
        "{email}": student.email or "",
        "{telefono}": student.phone or "",
        "{titulo}": (row.title if row else "") or "",
        "{resultado}": (row.result_summary if row else "") or "",
        "{proximo_contacto}": row.next_contact_date.strftime("%d/%m/%Y") if row and row.next_contact_date else "",
    }

    text = template_body or ""
    for k, v in data.items():
        text = text.replace(k, v)
    return text


def find_best_template(db, kind_value: str, channel_value: str) -> MessageTemplate | None:
    rows = db.scalars(
        select(MessageTemplate)
        .where(
            MessageTemplate.kind == FollowupKind(kind_value),
            MessageTemplate.channel.in_([
                MessageTemplateChannel(channel_value),
                MessageTemplateChannel.GENERAL,
            ]),
            MessageTemplate.is_active == True,
        )
        .order_by(MessageTemplate.channel.asc(), MessageTemplate.id.asc())
        .limit(3)
    ).all()

    if rows:
        exact = [r for r in rows if r.channel.value == channel_value]
        return exact[0] if exact else rows[0]
    return None


def build_followup_message(
    db,
    student: User,
    row: StudentFollowup | None = None,
    kind_value: str | None = None,
    channel_value: str | None = None,
) -> tuple[str, str]:
    kind = kind_value or (row.kind.value if row else "GENERAL")
    channel = channel_value or (row.channel.value if row else "WHATSAPP")

    tpl = find_best_template(db, kind, channel)
    if tpl:
        subject = tpl.subject or f"Seguimiento TRZ Funcional - {kind}"
        body = render_template_text(tpl.body, student, row=row)
        return subject, body

    nombre = (student.full_name or student.first_name or student.email or "Hola").strip()

    if kind == "MOROSIDAD":
        body = (
            f"Hola {nombre}, ¿cómo estás? Te escribimos desde TRZ Funcional "
            "porque vimos una cuota pendiente y queremos ayudarte a regularizarla. "
            "Quedamos atentos."
        )
    elif kind == "INACTIVIDAD":
        body = (
            f"Hola {nombre}, ¿cómo estás? Te escribimos desde TRZ Funcional "
            "porque notamos que hace un tiempo no venís y queríamos saber si querés retomar. "
            "Quedamos atentos."
        )
    else:
        body = f"Hola {nombre}, ¿cómo estás? Te escribimos desde TRZ Funcional."

    return f"Seguimiento TRZ Funcional - {kind}", body


def whatsapp_url(student: User, message: str) -> str:
    phone = normalize_phone_ar(student.phone)
    encoded = quote(message)
    if phone:
        return f"https://wa.me/{phone}?text={encoded}"
    return f"https://web.whatsapp.com/send?text={encoded}"


def email_url(student: User, subject: str, body: str) -> str:
    to = quote(student.email or "")
    sub = quote(subject or "Seguimiento TRZ Funcional")
    bod = quote(body or "")
    return f"mailto:{to}?subject={sub}&body={bod}"


def serialize_followup_for_actions(db, row: StudentFollowup) -> dict:
    student = row.student
    if not student:
        return {}

    subject, message = build_followup_message(db, student, row=row)

    return {
        "subject": subject,
        "message": message,
        "whatsapp_url": whatsapp_url(student, message),
        "email_url": email_url(student, subject, message),
        "phone_normalized": normalize_phone_ar(student.phone),
    }