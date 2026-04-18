from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import User
from ..services.dashboard_service import (
    build_dashboard_data,
    build_inactivos_rows,
    build_morosos_rows,
    normalize_date_range,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def excel_response(wb: Workbook, filename: str) -> StreamingResponse:
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/home", response_class=HTMLResponse)
def admin_home(
    request: Request,
    date_from: str = Query(""),
    date_to: str = Query(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(["ADMINISTRADOR", "ADMINISTRATIVO"])),
):
    date_range = normalize_date_range(date_from, date_to)
    data = build_dashboard_data(db, date_range.date_from, date_range.date_to)

    return templates.TemplateResponse(
        request,
        "admin_home.html",
        {
            "request": request,
            "me": me,
            **data,
        },
    )


@router.get("/admin/home/inactivos", response_class=HTMLResponse)
def admin_home_inactivos(
    request: Request,
    bucket: str = Query(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(["ADMINISTRADOR", "ADMINISTRATIVO"])),
):
    data = build_inactivos_rows(db, bucket=bucket)

    return templates.TemplateResponse(
        request,
        "admin_inactivos.html",
        {
            "request": request,
            "me": me,
            "rows": data["rows"],
            "bucket": data["bucket"],
            "period": data["period"],
        },
    )


@router.get("/admin/home/morosos", response_class=HTMLResponse)
def admin_home_morosos(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(["ADMINISTRADOR", "ADMINISTRATIVO"])),
):
    data = build_morosos_rows(db)

    return templates.TemplateResponse(
        request,
        "admin_morosos.html",
        {
            "request": request,
            "me": me,
            "rows": data["rows"],
            "period": data["period"],
        },
    )


@router.get("/admin/home/inactivos/export")
def export_inactivos(
    bucket: str = Query(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(["ADMINISTRADOR", "ADMINISTRATIVO"])),
):
    data = build_inactivos_rows(db, bucket=bucket)
    rows = data["rows"]

    wb = Workbook()
    ws = wb.active
    ws.title = "Inactivos"
    ws.append(["Alumno", "Email", "DNI", "Última asistencia", "Meses sin venir", "Grupo"])

    for row in rows:
        alumno = row["alumno"]
        ws.append(
            [
                alumno.full_name or alumno.email,
                alumno.email,
                alumno.dni or "",
                row["last_used_at"].strftime("%d/%m/%Y") if row["last_used_at"] else "Nunca",
                "" if row["months"] is None else row["months"],
                row["bucket"],
            ]
        )

    return excel_response(wb, "inactivos.xlsx")


@router.get("/admin/home/morosos/export")
def export_morosos(
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(["ADMINISTRADOR", "ADMINISTRATIVO"])),
):
    data = build_morosos_rows(db)
    rows = data["rows"]

    wb = Workbook()
    ws = wb.active
    ws.title = "Morosos"
    ws.append(["Alumno", "Email", "DNI", "Membresía", "Período", "Motivo"])

    for row in rows:
        alumno = row["alumno"]
        ws.append(
            [
                alumno.full_name or alumno.email,
                alumno.email,
                alumno.dni or "",
                row["membership_name"],
                row["periodo"],
                row["motivo"],
            ]
        )

    return excel_response(wb, "morosos.xlsx")