from pathlib import Path
import json
import logging

from fastapi import APIRouter, Request, Depends, Form, Query, Header
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import User, FollowupKind, FollowupStatus, FollowupPriority
from ..services.followup_rules_service import run_followup_rules_for_all
from ..services.followup_message_service import send_via_n8n
from ..services.followup_webhook_service import process_followup_webhook
from ..services.followup_admin_service import (
    list_followups,
    get_dashboard_data,
    get_automation_data,
    list_inbox_actions,
    get_agenda_data,
    get_kanban_data,
    get_reminders_data,
    mark_reminder_sent_service,
    get_new_followup_page_data,
    create_followup,
    get_followup_edit_page_data,
    update_followup,
    mark_channel_sent_service,
    get_followups_by_student_data,
    get_actions_by_student_data,
    get_followup_or_none,
)
from ..utils.pagination import normalize_page, normalize_page_size
from ..services.followup_observability_service import get_followup_observability_data

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
logger = logging.getLogger(__name__)

ALLOWED = ["ADMINISTRADOR", "ADMINISTRATIVO"]


@router.get("/admin/followups", response_class=HTMLResponse)
def followups_list(
    request: Request,
    q: str = "",
    kind: str = "",
    status: str = "",
    priority: str = "",
    page: int = Query(1),
    page_size: int = Query(25),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    page = normalize_page(page)
    page_size = normalize_page_size(page_size, default=25, min_value=10, max_value=100)

    data = list_followups(
        db,
        q=q,
        kind=kind,
        status=status,
        priority=priority,
        page=page,
        page_size=page_size,
    )

    return templates.TemplateResponse(
        request,
        "followups_list.html",
        {
            "request": request,
            "me": me,
            "rows": data["rows"],
            "row_actions": data["row_actions"],
            "pagination": data["pagination"],
            "q": q,
            "kind": kind,
            "status": status,
            "priority": priority,
            "kinds": [k.value for k in FollowupKind],
            "statuses": [s.value for s in FollowupStatus],
            "priorities": [p.value for p in FollowupPriority],
        },
    )


@router.get("/admin/followups/dashboard", response_class=HTMLResponse)
def followups_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    data = get_dashboard_data(db)

    return templates.TemplateResponse(
        request,
        "followups_dashboard.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )

@router.get("/admin/followups/observability", response_class=HTMLResponse)
def followups_observability(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    data = get_followup_observability_data(db)

    return templates.TemplateResponse(
        request,
        "followups_observability.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )


@router.get("/admin/followups/automation", response_class=HTMLResponse)
def followups_automation_page(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    data = get_automation_data(db)

    return templates.TemplateResponse(
        request,
        "followups_automation.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )


@router.post("/admin/followups/automation/run")
def followups_automation_run(
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    result = run_followup_rules_for_all(db, me=me)
    logger.info("FOLLOWUPS AUTOMATION RUN | %s", json.dumps(result, ensure_ascii=False))
    return RedirectResponse("/admin/followups/automation", status_code=302)


@router.get("/admin/followups/inbox", response_class=HTMLResponse)
def followups_inbox(
    request: Request,
    q: str = "",
    status: str = "",
    page: int = Query(1),
    page_size: int = Query(25),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    page = normalize_page(page)
    page_size = normalize_page_size(page_size, default=25, min_value=10, max_value=100)

    data = list_inbox_actions(
        db,
        q=q,
        status=status,
        page=page,
        page_size=page_size,
    )

    return templates.TemplateResponse(
        request,
        "followups_inbox.html",
        {
            "request": request,
            "me": me,
            "actions": data["actions"],
            "followup_map": data["followup_map"],
            "pagination": data["pagination"],
            "q": q,
            "status": status,
            "statuses": data["statuses"],
        },
    )


@router.get("/admin/followups/agenda", response_class=HTMLResponse)
def followups_agenda(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    data = get_agenda_data(db)

    return templates.TemplateResponse(
        request,
        "followups_agenda.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )


@router.get("/admin/followups/kanban", response_class=HTMLResponse)
def followups_kanban(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    data = get_kanban_data(db)

    return templates.TemplateResponse(
        request,
        "followups_kanban.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )


@router.get("/admin/followups/reminders", response_class=HTMLResponse)
def reminders_page(
    request: Request,
    page: int = Query(1),
    page_size: int = Query(25),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    page = normalize_page(page)
    page_size = normalize_page_size(page_size, default=25, min_value=10, max_value=100)

    data = get_reminders_data(
        db,
        page=page,
        page_size=page_size,
    )

    return templates.TemplateResponse(
        request,
        "followup_reminders.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )


@router.post("/admin/followups/{followup_id}/mark-reminder")
def mark_reminder_sent(
    followup_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    mark_reminder_sent_service(db, followup_id=followup_id, me=me)
    return RedirectResponse("/admin/followups/reminders", status_code=302)


@router.get("/admin/followups/new", response_class=HTMLResponse)
def followup_new_page(
    request: Request,
    student_id: int = Query(...),
    kind: str = Query("GENERAL"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    data = get_new_followup_page_data(db, student_id=student_id, kind=kind)
    if not data:
        return RedirectResponse("/admin/users", status_code=302)

    return templates.TemplateResponse(
        request,
        "followup_form.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )


@router.post("/admin/followups/new")
def followup_new_do(
    student_id: int = Form(...),
    kind: str = Form(...),
    status: str = Form(...),
    channel: str = Form("WHATSAPP"),
    title: str = Form(""),
    notes: str = Form(""),
    next_contact_date: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = create_followup(
        db,
        student_id=student_id,
        kind=kind,
        status=status,
        channel=channel,
        title=title,
        notes=notes,
        next_contact_date=next_contact_date,
        me=me,
    )
    if not row:
        return RedirectResponse("/admin/users", status_code=302)

    return RedirectResponse("/admin/followups", status_code=302)


@router.get("/admin/followups/{followup_id}/edit", response_class=HTMLResponse)
def followup_edit_page(
    request: Request,
    followup_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    data = get_followup_edit_page_data(db, followup_id=followup_id)
    if not data:
        return RedirectResponse("/admin/followups", status_code=302)

    return templates.TemplateResponse(
        request,
        "followup_edit.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )


@router.post("/admin/followups/{followup_id}/edit")
def followup_edit_do(
    followup_id: int,
    kind: str = Form(...),
    status: str = Form(...),
    priority: str = Form(""),
    channel: str = Form("WHATSAPP"),
    title: str = Form(""),
    notes: str = Form(""),
    next_contact_date: str = Form(""),
    result_summary: str = Form(""),
    automation_enabled: str = Form("1"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    ok = update_followup(
        db,
        followup_id=followup_id,
        kind=kind,
        status=status,
        priority=priority,
        channel=channel,
        title=title,
        notes=notes,
        next_contact_date=next_contact_date,
        result_summary=result_summary,
        automation_enabled=automation_enabled,
        me=me,
    )
    if not ok:
        return RedirectResponse("/admin/followups", status_code=302)

    return RedirectResponse("/admin/followups", status_code=302)


@router.post("/admin/followups/{followup_id}/mark-whatsapp")
def mark_whatsapp_sent(
    followup_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    mark_channel_sent_service(
        db,
        followup_id=followup_id,
        channel="WHATSAPP",
        me=me,
    )
    return RedirectResponse("/admin/followups", status_code=302)


@router.post("/admin/followups/{followup_id}/mark-email")
def mark_email_sent(
    followup_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    mark_channel_sent_service(
        db,
        followup_id=followup_id,
        channel="EMAIL",
        me=me,
    )
    return RedirectResponse("/admin/followups", status_code=302)


@router.post("/admin/followups/{followup_id}/send-whatsapp")
def send_whatsapp_real(
    followup_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_followup_or_none(db, followup_id)
    if not row:
        return RedirectResponse("/admin/followups", status_code=302)

    send_via_n8n(db=db, row=row, me=me, channel="WHATSAPP")
    return RedirectResponse("/admin/followups", status_code=302)


@router.post("/admin/followups/{followup_id}/send-email")
def send_email_real(
    followup_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = get_followup_or_none(db, followup_id)
    if not row:
        return RedirectResponse("/admin/followups", status_code=302)

    send_via_n8n(db=db, row=row, me=me, channel="EMAIL")
    return RedirectResponse("/admin/followups", status_code=302)


@router.post("/admin/followups/webhook/result")
def followup_webhook_result(
    payload: dict,
    x_followup_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    result = process_followup_webhook(db=db, payload=payload, header_token=x_followup_token)
    return JSONResponse(result)


@router.get("/admin/alumnos/{student_id}/followups", response_class=HTMLResponse)
def followups_by_student(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    data = get_followups_by_student_data(db, student_id=student_id)
    if not data:
        return RedirectResponse("/admin/users", status_code=302)

    return templates.TemplateResponse(
        request,
        "student_followups_history.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )


@router.get("/admin/alumnos/{student_id}/actions", response_class=HTMLResponse)
def actions_by_student(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    data = get_actions_by_student_data(db, student_id=student_id)
    if not data:
        return RedirectResponse("/admin/users", status_code=302)

    return templates.TemplateResponse(
        request,
        "student_actions_timeline.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )