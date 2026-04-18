from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import FollowupKind, MessageTemplate, MessageTemplateChannel
from .admin_list_service import build_pagination_context, parse_pagination_params


DEFAULT_PAGE_SIZE = 20
ALLOWED_PAGE_SIZES = {20, 50, 100}


def normalize_text(value: str | None) -> str:
    return (value or "").strip()


def parse_bool_filter(value: str | None) -> str:
    cleaned = normalize_text(value).lower()
    if cleaned in {"true", "false"}:
        return cleaned
    return ""


def parse_is_active_form(value: str | None) -> bool:
    return normalize_text(value) in {"1", "true", "on", "yes", "si", "sí"}


def parse_template_filters(
    *,
    q,
    kind,
    channel,
    is_active,
    page,
    page_size,
):
    pagination = parse_pagination_params(
        page,
        page_size,
        default_page_size=DEFAULT_PAGE_SIZE,
    )

    if pagination.page_size not in ALLOWED_PAGE_SIZES:
        pagination = parse_pagination_params(
            pagination.page,
            DEFAULT_PAGE_SIZE,
            default_page_size=DEFAULT_PAGE_SIZE,
        )

    return {
        "q": normalize_text(q),
        "kind": normalize_text(kind),
        "channel": normalize_text(channel),
        "is_active": parse_bool_filter(is_active),
        "page": pagination.page,
        "page_size": pagination.page_size,
        "offset": pagination.offset,
    }


def build_templates_query(
    *,
    q: str = "",
    kind: str = "",
    channel: str = "",
    is_active: str = "",
):
    stmt = select(MessageTemplate)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                MessageTemplate.name.ilike(like),
                MessageTemplate.subject.ilike(like),
                MessageTemplate.body.ilike(like),
            )
        )

    if kind:
        stmt = stmt.where(MessageTemplate.kind == FollowupKind(kind))

    if channel:
        stmt = stmt.where(MessageTemplate.channel == MessageTemplateChannel(channel))

    if is_active == "true":
        stmt = stmt.where(MessageTemplate.is_active.is_(True))
    elif is_active == "false":
        stmt = stmt.where(MessageTemplate.is_active.is_(False))

    return stmt


def count_templates(
    db: Session,
    *,
    q: str = "",
    kind: str = "",
    channel: str = "",
    is_active: str = "",
) -> int:
    stmt = build_templates_query(
        q=q,
        kind=kind,
        channel=channel,
        is_active=is_active,
    )
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


def load_templates_paginated(
    db: Session,
    *,
    q: str = "",
    kind: str = "",
    channel: str = "",
    is_active: str = "",
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
) -> list[MessageTemplate]:
    stmt = (
        build_templates_query(
            q=q,
            kind=kind,
            channel=channel,
            is_active=is_active,
        )
        .order_by(MessageTemplate.name.asc(), MessageTemplate.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(stmt).all()


def build_templates_list_context(
    *,
    request,
    me,
    rows: list[MessageTemplate],
    q: str,
    kind: str,
    channel: str,
    is_active: str,
    page: int,
    page_size: int,
    total: int,
):
    return {
        "request": request,
        "me": me,
        "rows": rows,
        "q": q,
        "kind": kind,
        "channel": channel,
        "is_active": is_active,
        "kinds": [k.value for k in FollowupKind],
        "channels": [c.value for c in MessageTemplateChannel],
        **build_pagination_context(
            page=page,
            page_size=page_size,
            total=total,
        ),
    }


def build_template_form_context(
    *,
    request,
    me,
    row,
    error: str | None,
):
    return {
        "request": request,
        "me": me,
        "row": row,
        "error": error,
        "kinds": [k.value for k in FollowupKind],
        "channels": [c.value for c in MessageTemplateChannel],
    }


def sanitize_template_payload(
    *,
    name: str,
    kind: str,
    channel: str,
    subject: str,
    body: str,
    is_active: str,
):
    return {
        "name": normalize_text(name),
        "kind": normalize_text(kind),
        "channel": normalize_text(channel),
        "subject": normalize_text(subject),
        "body": normalize_text(body),
        "is_active": parse_is_active_form(is_active),
    }


def validate_template_payload(
    db: Session,
    *,
    payload: dict,
    current_id: int | None = None,
) -> str | None:
    if not payload["name"]:
        return "El nombre es obligatorio."

    if not payload["body"]:
        return "El cuerpo es obligatorio."

    try:
        FollowupKind(payload["kind"])
    except Exception:
        return "Tipo inválido."

    try:
        MessageTemplateChannel(payload["channel"])
    except Exception:
        return "Canal inválido."

    stmt = select(MessageTemplate).where(MessageTemplate.name == payload["name"])
    if current_id is not None:
        stmt = stmt.where(MessageTemplate.id != current_id)

    if db.scalar(stmt):
        return "Ya existe una plantilla con ese nombre."

    return None


def apply_template_payload(row: MessageTemplate, payload: dict) -> MessageTemplate:
    row.name = payload["name"]
    row.kind = FollowupKind(payload["kind"])
    row.channel = MessageTemplateChannel(payload["channel"])
    row.subject = payload["subject"]
    row.body = payload["body"]
    row.is_active = payload["is_active"]
    return row