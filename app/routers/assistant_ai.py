import hmac
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..core.config import settings
from ..db import get_db
from ..deps import require_roles
from ..models import ContactConversation, User
from ..services.admin_list_service import (
    parse_pagination_params,
    build_pagination_context,
)
from ..services.assistant_admin_service import (
    change_conversation_stage,
    get_conversation_or_404,
    mark_conversation_handoff,
    mark_conversation_reactivated,
    pause_conversation,
    resume_conversation,
    send_manual_conversation_message,
    send_quick_conversation_message,
)
from ..services.assistant_inbound_service import process_inbound_message
from ..services.conversation_view_service import (
    build_conversation_detail_context,
    get_conversation_messages,
)

BASE_DIR = Path(__file__).resolve().parents[1]

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

logger = logging.getLogger(__name__)
auth_logger = logging.getLogger("app.assistant_auth")

ALLOWED = ["ADMINISTRADOR", "ADMINISTRATIVO"]

logger.info("assistant_ai inicializado")


def _get_assistant_inbound_token() -> str:
    return (
        getattr(settings, "ASSISTANT_INBOUND_TOKEN", "")
        or getattr(settings, "ASSISTANT_WEBHOOK_TOKEN", "")
        or getattr(settings, "ASSISTANT_TOKEN", "")
        or ""
    ).strip()


def _extract_presented_assistant_token(
    *,
    x_assistant_token: str | None,
    authorization: str | None,
) -> str:
    if x_assistant_token and x_assistant_token.strip():
        return x_assistant_token.strip()

    if authorization and authorization.strip():
        raw = authorization.strip()
        if raw.lower().startswith("bearer "):
            return raw[7:].strip()
        return raw

    return ""


def _validate_assistant_inbound_token(
    *,
    request: Request,
    presented_token: str,
) -> None:
    configured_token = _get_assistant_inbound_token()

    if not configured_token:
        auth_logger.warning(
            "assistant_inbound_auth_not_configured path=%s client=%s",
            request.url.path,
            request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=500,
            detail="Token del asistente no configurado",
        )

    if not presented_token:
        auth_logger.warning(
            "assistant_inbound_auth_missing path=%s client=%s",
            request.url.path,
            request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=401,
            detail="Token faltante",
        )

    if not hmac.compare_digest(presented_token, configured_token):
        auth_logger.warning(
            "assistant_inbound_auth_invalid path=%s client=%s",
            request.url.path,
            request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=401,
            detail="Token inválido",
        )


@router.post("/api/assistant/inbound")
async def assistant_inbound(
    request: Request,
    db: Session = Depends(get_db),
    x_assistant_token: str | None = Header(default=None, alias="X-Assistant-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    presented_token = _extract_presented_assistant_token(
        x_assistant_token=x_assistant_token,
        authorization=authorization,
    )
    _validate_assistant_inbound_token(
        request=request,
        presented_token=presented_token,
    )

    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)

    try:
        return process_inbound_message(db, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/admin/conversations", response_class=HTMLResponse)
def conversations_list(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    qp = request.query_params
    pagination = parse_pagination_params(
        qp.get("page"),
        qp.get("page_size"),
        default_page_size=20,
        max_page_size=100,
    )

    status = (qp.get("status") or "").strip()
    paused = (qp.get("paused") or "").strip()
    q = (qp.get("q") or "").strip()

    base_query = select(ContactConversation)
    count_query = select(func.count()).select_from(ContactConversation)

    filters = []

    if status:
        filters.append(ContactConversation.status == status)

    if paused == "1":
        filters.append(ContactConversation.assistant_paused.is_(True))
    elif paused == "0":
        filters.append(ContactConversation.assistant_paused.is_(False))

    if q:
        filters.append(
            or_(
                ContactConversation.phone.ilike(f"%{q}%"),
                ContactConversation.intent_last.ilike(f"%{q}%"),
                ContactConversation.handoff_reason.ilike(f"%{q}%"),
            )
        )

    for f in filters:
        base_query = base_query.where(f)
        count_query = count_query.where(f)

    total = db.scalar(count_query) or 0

    rows = db.scalars(
        base_query.options(
            joinedload(ContactConversation.student),
            joinedload(ContactConversation.prospect),
            joinedload(ContactConversation.followup),
        )
        .order_by(ContactConversation.id.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    ).all()

    pagination_ctx = build_pagination_context(
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )

    return templates.TemplateResponse(
        request,
        "conversations_list.html",
        {
            "request": request,
            "me": me,
            "rows": rows,
            "filters": {
                "status": status,
                "paused": paused,
                "q": q,
            },
            **pagination_ctx,
        },
    )


@router.get("/admin/conversations/{conversation_id}", response_class=HTMLResponse)
def conversation_detail(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = db.scalars(
        select(ContactConversation)
        .options(
            joinedload(ContactConversation.student),
            joinedload(ContactConversation.prospect),
            joinedload(ContactConversation.followup),
        )
        .where(ContactConversation.id == conversation_id)
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    detail_ctx = build_conversation_detail_context(db, row)

    qp = request.query_params
    sent = qp.get("sent") == "1"
    paused = qp.get("paused") == "1"
    resumed = qp.get("resumed") == "1"
    reactivated = qp.get("reactivated") == "1"
    stage_updated = qp.get("stage_updated") == "1"

    return templates.TemplateResponse(
        request,
        "conversation_detail.html",
        {
            "request": request,
            "me": me,
            "row": row,
            "messages": detail_ctx["messages"],
            "sent": sent,
            "paused": paused,
            "resumed": resumed,
            "reactivated": reactivated,
            "stage_updated": stage_updated,
            "contact_name": detail_ctx["contact_name"],
            "contact_email": detail_ctx["contact_email"],
            "contact_phone": detail_ctx["contact_phone"],
            "suggestions": detail_ctx["suggestions"],
            "commercial_summary": detail_ctx["commercial_summary"],
        },
    )


@router.post("/admin/conversations/{conversation_id}/pause")
def conversation_pause(
    conversation_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_conversation_or_404(db, conversation_id)
    pause_conversation(db, row, me)

    return RedirectResponse(
        url=f"/admin/conversations/{conversation_id}?paused=1",
        status_code=303,
    )


@router.post("/admin/conversations/{conversation_id}/resume")
def conversation_resume(
    conversation_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_conversation_or_404(db, conversation_id)
    resume_conversation(db, row)

    return RedirectResponse(
        url=f"/admin/conversations/{conversation_id}?resumed=1",
        status_code=303,
    )


@router.post("/admin/conversations/{conversation_id}/send")
def conversation_send_message(
    conversation_id: int,
    message_text: str = Form(...),
    pause_assistant: str = Form("1"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_conversation_or_404(db, conversation_id)

    send_manual_conversation_message(
        db=db,
        row=row,
        me=me,
        text=message_text,
        pause_assistant=(pause_assistant == "1"),
    )

    return RedirectResponse(
        url=f"/admin/conversations/{conversation_id}?sent=1&paused={'1' if pause_assistant == '1' else '0'}",
        status_code=303,
    )


@router.get("/admin/conversations/{conversation_id}/messages", response_class=HTMLResponse)
def conversation_messages_partial(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_conversation_or_404(db, conversation_id)
    messages = get_conversation_messages(db, row.id)

    return templates.TemplateResponse(
        request,
        "partials/conversation_messages.html",
        {
            "request": request,
            "row": row,
            "messages": messages,
        },
    )


@router.post("/admin/conversations/{conversation_id}/mark-reactivated")
def conversation_mark_reactivated(
    conversation_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_conversation_or_404(db, conversation_id)
    mark_conversation_reactivated(db=db, row=row, me=me)

    return RedirectResponse(
        url=f"/admin/conversations/{conversation_id}?reactivated=1",
        status_code=303,
    )


@router.post("/admin/conversations/{conversation_id}/mark-handoff")
def conversation_mark_handoff(
    conversation_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_conversation_or_404(db, conversation_id)
    mark_conversation_handoff(db=db, row=row, me=me)

    return RedirectResponse(
        url=f"/admin/conversations/{conversation_id}?paused=1",
        status_code=303,
    )


@router.post("/admin/conversations/{conversation_id}/quick-send")
def conversation_quick_send(
    conversation_id: int,
    kind: str = Form(...),
    pause_assistant: str = Form("1"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_conversation_or_404(db, conversation_id)

    send_quick_conversation_message(
        db=db,
        row=row,
        me=me,
        kind=kind,
        pause_assistant=(pause_assistant == "1"),
    )

    return RedirectResponse(
        url=f"/admin/conversations/{conversation_id}?sent=1&paused={'1' if pause_assistant == '1' else '0'}",
        status_code=303,
    )


@router.post("/admin/conversations/{conversation_id}/stage")
def conversation_change_stage(
    conversation_id: int,
    stage: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_conversation_or_404(db, conversation_id)

    change_conversation_stage(
        db=db,
        row=row,
        me=me,
        stage=stage,
        note=note,
    )

    return RedirectResponse(
        url=f"/admin/conversations/{conversation_id}?stage_updated=1",
        status_code=303,
    )