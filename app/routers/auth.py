from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.exc import UnknownHashError

from ..db import get_db
from ..models import User
from ..security import verify_password, create_access_token, hash_password
from ..deps import get_current_user, require_roles

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]  # .../app
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ADMIN_PANEL = {"ADMINISTRADOR", "ADMINISTRATIVO"}
PROF_ONLY = ["PROFESOR"]
ALUM_ONLY = ["ALUMNO"]


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email_norm = email.strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()

    ok = False
    if user and user.password_hash:
        try:
            ok = verify_password(password, user.password_hash)
        except UnknownHashError:
            ok = False

    if (not user) or (not user.is_active) or (not ok):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "Credenciales inválidas"},
            status_code=400,
        )

    token = create_access_token({"sub": str(user.id), "role": user.role.value})

    if getattr(user, "must_change_password", False):
        next_url = "/change-password"
    else:
        if user.role.value in ADMIN_PANEL:
            next_url = "/admin/users"
        elif user.role.value == "PROFESOR":
            next_url = "/profesor/routines"
        elif user.role.value == "ALUMNO":
            next_url = "/alumno/app"
        else:
            next_url = "/"

    resp = RedirectResponse(url=next_url, status_code=302)
    resp.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 6,
    )
    return resp


@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("access_token")
    return resp


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html", {"request": request})


@router.get("/profesor", response_class=HTMLResponse)
def profesor_home(request: Request, me: User = Depends(require_roles(PROF_ONLY))):
    return templates.TemplateResponse(
        request,
        "home_simple.html",
        {
            "request": request,
            "me": me,
            "title": "Panel Profesor",
            "subtitle": "Acá va el módulo de Rutinas / Alumnos (siguiente paso).",
        },
    )


@router.get("/alumno", response_class=HTMLResponse)
def alumno_home(request: Request, me: User = Depends(require_roles(ALUM_ONLY))):
    return templates.TemplateResponse(
        request,
        "home_simple.html",
        {
            "request": request,
            "me": me,
            "title": "Panel Alumno",
            "subtitle": "Acá va tu perfil, asistencia, pagos y rutina activa (siguiente paso).",
        },
    )


@router.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request, me: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request,
        "change_password.html",
        {"request": request, "me": me, "error": None, "ok": None},
    )


@router.post("/change-password", response_class=HTMLResponse)
def change_password_do(
    request: Request,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    if len(new_password) < 6:
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {
                "request": request,
                "me": me,
                "error": "La contraseña debe tener al menos 6 caracteres.",
                "ok": None,
            },
            status_code=400,
        )

    if new_password != confirm_password:
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {
                "request": request,
                "me": me,
                "error": "Las contraseñas no coinciden.",
                "ok": None,
            },
            status_code=400,
        )

    u = db.get(User, me.id)
    u.password_hash = hash_password(new_password)
    u.must_change_password = False
    db.commit()

    if u.role.value in ADMIN_PANEL:
        next_url = "/admin/users"
    elif u.role.value == "PROFESOR":
        next_url = "/profesor/routines"
    elif u.role.value == "ALUMNO":
        next_url = "/alumno/app"
    else:
        next_url = "/"

    return RedirectResponse(url=next_url, status_code=302)