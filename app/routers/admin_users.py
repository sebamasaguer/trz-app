from pathlib import Path

from fastapi import APIRouter, Depends, Form, Path as FPath, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import Role, User
from ..security import hash_password
from ..services.user_admin_service import (
    PANEL_ALLOWED_ROLES,
    build_user_form_context,
    build_user_from_form,
    build_users_list_context,
    can_delete_user,
    can_manage_target,
    can_reset_password,
    can_toggle_user,
    count_users,
    generate_temp_password,
    load_users_paginated,
    parse_is_active,
    parse_users_list_filters,
    sanitize_user_form_input,
    validate_edit_user_payload,
    validate_new_user_payload,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_list(
    request: Request,
    q: str = "",
    role: str = "",
    is_active: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PANEL_ALLOWED_ROLES)),
):
    filters = parse_users_list_filters(
        q=q,
        role=role,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    total = count_users(
        db,
        q=filters["q"],
        role=filters["role"],
        is_active=filters["is_active"],
    )
    users = load_users_paginated(
        db,
        q=filters["q"],
        role=filters["role"],
        is_active=filters["is_active"],
        offset=filters["offset"],
        limit=filters["page_size"],
    )

    return templates.TemplateResponse(
        request,
        "users.html",
        build_users_list_context(
            request=request,
            me=me,
            users=users,
            q=filters["q"],
            role=filters["role"],
            is_active=filters["is_active"],
            page=filters["page"],
            page_size=filters["page_size"],
            total=total,
        ),
    )


@router.get("/admin/users/new", response_class=HTMLResponse)
def admin_users_new_page(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PANEL_ALLOWED_ROLES)),
):
    return templates.TemplateResponse(
        request,
        "user_form.html",
        build_user_form_context(
            request=request,
            me=me,
            user=None,
            mode="new",
            error=None,
        ),
    )


@router.post("/admin/users/new", response_class=HTMLResponse)
def admin_users_new_do(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    first_name: str = Form(""),
    last_name: str = Form(""),
    dni: str = Form(""),
    birth_date: str = Form(""),
    address: str = Form(""),
    phone: str = Form(""),
    emergency_contact_name: str = Form(""),
    emergency_contact_phone: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PANEL_ALLOWED_ROLES)),
):
    try:
        payload = sanitize_user_form_input(
            email=email,
            role=role,
            first_name=first_name,
            last_name=last_name,
            dni=dni,
            birth_date=birth_date,
            address=address,
            phone=phone,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "user_form.html",
            build_user_form_context(
                request=request,
                me=me,
                user=None,
                mode="new",
                error=str(exc),
            ),
            status_code=400,
        )

    if not (password or "").strip():
        return templates.TemplateResponse(
            request,
            "user_form.html",
            build_user_form_context(
                request=request,
                me=me,
                user=None,
                mode="new",
                error="La contraseña es obligatoria.",
            ),
            status_code=400,
        )

    error = validate_new_user_payload(
        db,
        me=me,
        email=payload["email"],
        role=payload["role"],
        dni=payload["dni"],
    )
    if error:
        return templates.TemplateResponse(
            request,
            "user_form.html",
            build_user_form_context(
                request=request,
                me=me,
                user=None,
                mode="new",
                error=error,
            ),
            status_code=400,
        )

    try:
        user = build_user_from_form(
            user=None,
            email=payload["email"],
            role=payload["role"],
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            dni=payload["dni"],
            birth_date=payload["birth_date"],
            address=payload["address"],
            phone=payload["phone"],
            emergency_contact_name=payload["emergency_contact_name"],
            emergency_contact_phone=payload["emergency_contact_phone"],
            is_active=True,
        )
        user.password_hash = hash_password(password.strip())
        user.must_change_password = False

        db.add(user)
        db.commit()
        return RedirectResponse(url="/admin/users", status_code=302)
    except Exception:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "user_form.html",
            build_user_form_context(
                request=request,
                me=me,
                user=None,
                mode="new",
                error="No se pudo crear el usuario.",
            ),
            status_code=500,
        )


@router.get("/admin/users/{user_id}/edit", response_class=HTMLResponse)
def admin_users_edit_page(
    request: Request,
    user_id: int = FPath(...),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PANEL_ALLOWED_ROLES)),
):
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)

    if not can_manage_target(me, user):
        return RedirectResponse(url="/admin/users", status_code=302)

    return templates.TemplateResponse(
        request,
        "user_form.html",
        build_user_form_context(
            request=request,
            me=me,
            user=user,
            mode="edit",
            error=None,
        ),
    )


@router.post("/admin/users/{user_id}/edit", response_class=HTMLResponse)
def admin_users_edit_do(
    request: Request,
    user_id: int,
    email: str = Form(...),
    role: str = Form(...),
    first_name: str = Form(""),
    last_name: str = Form(""),
    dni: str = Form(""),
    birth_date: str = Form(""),
    address: str = Form(""),
    phone: str = Form(""),
    emergency_contact_name: str = Form(""),
    emergency_contact_phone: str = Form(""),
    is_active: str = Form("true"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PANEL_ALLOWED_ROLES)),
):
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)

    try:
        payload = sanitize_user_form_input(
            email=email,
            role=role,
            first_name=first_name,
            last_name=last_name,
            dni=dni,
            birth_date=birth_date,
            address=address,
            phone=phone,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "user_form.html",
            build_user_form_context(
                request=request,
                me=me,
                user=user,
                mode="edit",
                error=str(exc),
            ),
            status_code=400,
        )

    error = validate_edit_user_payload(
        db,
        me=me,
        target=user,
        email=payload["email"],
        role=payload["role"],
        dni=payload["dni"],
    )
    if error:
        return templates.TemplateResponse(
            request,
            "user_form.html",
            build_user_form_context(
                request=request,
                me=me,
                user=user,
                mode="edit",
                error=error,
            ),
            status_code=400,
        )

    try:
        build_user_from_form(
            user=user,
            email=payload["email"],
            role=payload["role"],
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            dni=payload["dni"],
            birth_date=payload["birth_date"],
            address=payload["address"],
            phone=payload["phone"],
            emergency_contact_name=payload["emergency_contact_name"],
            emergency_contact_phone=payload["emergency_contact_phone"],
            is_active=parse_is_active(is_active),
        )
        db.commit()
        return RedirectResponse(url="/admin/users", status_code=302)
    except Exception:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "user_form.html",
            build_user_form_context(
                request=request,
                me=me,
                user=user,
                mode="edit",
                error="No se pudo actualizar el usuario.",
            ),
            status_code=500,
        )


@router.post("/admin/users/{user_id}/disable")
def admin_users_disable(
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PANEL_ALLOWED_ROLES)),
):
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)

    if not can_toggle_user(me, user):
        return RedirectResponse(url="/admin/users", status_code=302)

    user.is_active = False
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/admin/users/{user_id}/reset-password", response_class=HTMLResponse)
def reset_password_page(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PANEL_ALLOWED_ROLES)),
):
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)

    if not can_reset_password(me, user):
        return RedirectResponse(url="/admin/users", status_code=302)

    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {
            "request": request,
            "user": user,
            "me": me,
            "temp_password": None,
        },
    )


@router.post("/admin/users/{user_id}/reset-password", response_class=HTMLResponse)
def reset_password_do(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PANEL_ALLOWED_ROLES)),
):
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)

    if not can_reset_password(me, user):
        return RedirectResponse(url="/admin/users", status_code=302)

    temp_password = generate_temp_password(12)
    user.password_hash = hash_password(temp_password)
    user.is_active = True
    user.must_change_password = True
    db.commit()

    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {
            "request": request,
            "user": user,
            "me": me,
            "temp_password": temp_password,
        },
    )


@router.post("/admin/users/{user_id}/toggle")
def admin_users_toggle(
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PANEL_ALLOWED_ROLES)),
):
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)

    if not can_toggle_user(me, user):
        return RedirectResponse(url="/admin/users", status_code=302)

    user.is_active = not user.is_active
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/admin/users/{user_id}/delete")
def admin_users_delete(
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles([Role.ADMINISTRADOR.value])),
):
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)

    if not can_delete_user(me, user):
        return RedirectResponse(url="/admin/users", status_code=302)

    user.is_active = False
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)