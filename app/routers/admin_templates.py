from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_db
from ..deps import require_roles
from ..models import User, MessageTemplate, FollowupKind, MessageTemplateChannel
from ..services.template_admin_service import (
    apply_template_payload,
    build_template_form_context,
    build_templates_list_context,
    count_templates,
    load_templates_paginated,
    parse_template_filters,
    sanitize_template_payload,
    validate_template_payload,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ALLOWED = ["ADMINISTRADOR", "ADMINISTRATIVO"]


@router.get("/admin/templates", response_class=HTMLResponse)
def templates_list(
    request: Request,
    q: str = "",
    kind: str = "",
    channel: str = "",
    is_active: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    filters = parse_template_filters(
        q=q,
        kind=kind,
        channel=channel,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    total = count_templates(
        db,
        q=filters["q"],
        kind=filters["kind"],
        channel=filters["channel"],
        is_active=filters["is_active"],
    )
    rows = load_templates_paginated(
        db,
        q=filters["q"],
        kind=filters["kind"],
        channel=filters["channel"],
        is_active=filters["is_active"],
        offset=filters["offset"],
        limit=filters["page_size"],
    )

    return templates.TemplateResponse(
        request,
        "templates_list.html",
        build_templates_list_context(
            request=request,
            me=me,
            rows=rows,
            q=filters["q"],
            kind=filters["kind"],
            channel=filters["channel"],
            is_active=filters["is_active"],
            page=filters["page"],
            page_size=filters["page_size"],
            total=total,
        ),
    )


@router.get("/admin/templates/new", response_class=HTMLResponse)
def template_new_page(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    return templates.TemplateResponse(
        request,
        "template_form.html",
        build_template_form_context(
            request=request,
            me=me,
            row=None,
            error=None,
        ),
    )


@router.post("/admin/templates/new", response_class=HTMLResponse)
def template_new_do(
    request: Request,
    name: str = Form(...),
    kind: str = Form(...),
    channel: str = Form(...),
    subject: str = Form(""),
    body: str = Form(""),
    is_active: str = Form("1"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    payload = sanitize_template_payload(
        name=name,
        kind=kind,
        channel=channel,
        subject=subject,
        body=body,
        is_active=is_active,
    )

    error = validate_template_payload(db, payload=payload)
    if error:
        temp_row = MessageTemplate()
        apply_template_payload(temp_row, payload)
        return templates.TemplateResponse(
            request,
            "template_form.html",
            build_template_form_context(
                request=request,
                me=me,
                row=temp_row,
                error=error,
            ),
            status_code=400,
        )

    try:
        row = apply_template_payload(MessageTemplate(), payload)
        db.add(row)
        db.commit()
        return RedirectResponse("/admin/templates", status_code=302)
    except Exception:
        db.rollback()
        temp_row = MessageTemplate()
        apply_template_payload(temp_row, payload)
        return templates.TemplateResponse(
            request,
            "template_form.html",
            build_template_form_context(
                request=request,
                me=me,
                row=temp_row,
                error="No se pudo crear la plantilla.",
            ),
            status_code=500,
        )


@router.get("/admin/templates/{template_id}/edit", response_class=HTMLResponse)
def template_edit_page(
    request: Request,
    template_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = db.get(MessageTemplate, template_id)
    if not row:
        return RedirectResponse("/admin/templates", status_code=302)

    return templates.TemplateResponse(
        request,
        "template_form.html",
        build_template_form_context(
            request=request,
            me=me,
            row=row,
            error=None,
        ),
    )


@router.post("/admin/templates/{template_id}/edit", response_class=HTMLResponse)
def template_edit_do(
    request: Request,
    template_id: int,
    name: str = Form(...),
    kind: str = Form(...),
    channel: str = Form(...),
    subject: str = Form(""),
    body: str = Form(""),
    is_active: str = Form("1"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    row = db.get(MessageTemplate, template_id)
    if not row:
        return RedirectResponse("/admin/templates", status_code=302)

    payload = sanitize_template_payload(
        name=name,
        kind=kind,
        channel=channel,
        subject=subject,
        body=body,
        is_active=is_active,
    )

    error = validate_template_payload(db, payload=payload, current_id=template_id)
    if error:
        apply_template_payload(row, payload)
        return templates.TemplateResponse(
            request,
            "template_form.html",
            build_template_form_context(
                request=request,
                me=me,
                row=row,
                error=error,
            ),
            status_code=400,
        )

    try:
        apply_template_payload(row, payload)
        db.commit()
        return RedirectResponse("/admin/templates", status_code=302)
    except Exception:
        db.rollback()
        apply_template_payload(row, payload)
        return templates.TemplateResponse(
            request,
            "template_form.html",
            build_template_form_context(
                request=request,
                me=me,
                row=row,
                error="No se pudo actualizar la plantilla.",
            ),
            status_code=500,
        )


@router.post("/admin/templates/seed")
def templates_seed(
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(ALLOWED)),
):
    defaults = [
        {
            "name": "Morosidad WhatsApp",
            "kind": FollowupKind.MOROSIDAD,
            "channel": MessageTemplateChannel.WHATSAPP,
            "subject": "Seguimiento de pago TRZ Funcional",
            "body": """Hola {nombre}, ¿cómo estás? Te escribimos desde TRZ Funcional porque registramos una cuota pendiente.

Si querés, te ayudamos a regularizarla y te pasamos los medios de pago disponibles.

Quedamos atentos.""",
        },
        {
            "name": "Morosidad Email",
            "kind": FollowupKind.MOROSIDAD,
            "channel": MessageTemplateChannel.EMAIL,
            "subject": "Regularización de cuota pendiente - TRZ Funcional",
            "body": """Hola {nombre},

Te escribimos desde TRZ Funcional porque registramos una cuota pendiente.

Si querés, podemos ayudarte a regularizarla y enviarte la información necesaria.

Saludos,
Equipo TRZ Funcional""",
        },
        {
            "name": "Inactividad WhatsApp",
            "kind": FollowupKind.INACTIVIDAD,
            "channel": MessageTemplateChannel.WHATSAPP,
            "subject": "Queremos verte de nuevo en TRZ",
            "body": """Hola {nombre}, ¿cómo estás? Notamos que hace un tiempo no venís a TRZ Funcional y queríamos saber si te gustaría retomar.

Si querés, te contamos horarios, opciones y te ayudamos a volver.

Quedamos atentos.""",
        },
        {
            "name": "Inactividad Email",
            "kind": FollowupKind.INACTIVIDAD,
            "channel": MessageTemplateChannel.EMAIL,
            "subject": "Te esperamos nuevamente en TRZ Funcional",
            "body": """Hola {nombre},

Notamos que hace un tiempo no estás viniendo a TRZ Funcional y queríamos saber si te gustaría retomar.

Podemos enviarte horarios, opciones de asistencia y ayudarte a volver.

Saludos,
Equipo TRZ Funcional""",
        },
        {
            "name": "General WhatsApp",
            "kind": FollowupKind.GENERAL,
            "channel": MessageTemplateChannel.WHATSAPP,
            "subject": "Seguimiento TRZ Funcional",
            "body": """Hola {nombre}, ¿cómo estás? Te escribimos desde TRZ Funcional para hacer seguimiento de tu situación.

Si necesitás información sobre horarios, clases o membresías, estamos para ayudarte.""",
        },
        {
            "name": "General Email",
            "kind": FollowupKind.GENERAL,
            "channel": MessageTemplateChannel.EMAIL,
            "subject": "Seguimiento TRZ Funcional",
            "body": """Hola {nombre},

Te escribimos desde TRZ Funcional para hacer seguimiento y ponernos a disposición por cualquier consulta.

Si necesitás información sobre clases, membresías u horarios, respondé este mensaje.

Saludos,
Equipo TRZ Funcional""",
        },
    ]

    existing_names = set(db.scalars(select(MessageTemplate.name)).all())

    created = 0
    for item in defaults:
        if item["name"] in existing_names:
            continue

        row = MessageTemplate(
            name=item["name"],
            kind=item["kind"],
            channel=item["channel"],
            subject=item["subject"],
            body=item["body"],
            is_active=True,
        )
        db.add(row)
        created += 1

    db.commit()
    return RedirectResponse("/admin/templates", status_code=302)