from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form, Path as FPath, File, UploadFile, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..db import get_db
from ..deps import require_roles
from ..models import User, Exercise, Routine, RoutineItem, RoutineAssignment, RoutineType, Role, ProfesorAlumno

from ..services.professor_query_service import (
    load_professor_active_assignments,
    load_professor_active_assignments_map,
    load_professor_assignment_history,
    load_professor_exercises,
    load_professor_routines,
    load_professor_students,
)


from ..services.routine_assignment_service import assign_routine_to_student
from ..services.professor_security_service import (
    load_professor_owned_routine,
    load_professor_owned_student,
)

from ..services.exercise_video_service import (
    build_private_video_response,
    delete_private_exercise_video,
    has_uploaded_file,
    save_private_exercise_video,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

PROF_ONLY = ["PROFESOR", "ADMINISTRADOR"]


def is_admin_user(user: User) -> bool:
    return user.role.value == "ADMINISTRADOR"


def professor_scope_id(user: User) -> int | None:
    """
    PROFESOR: devuelve su id para filtrar datos propios.
    ADMINISTRADOR: devuelve None para ver todo.
    """
    if is_admin_user(user):
        return None
    return user.id


def can_manage_professor_resource(user: User, professor_id: int) -> bool:
    """
    ADMINISTRADOR puede gestionar cualquier recurso del módulo profesor.
    PROFESOR solo puede gestionar recursos propios.
    """
    return is_admin_user(user) or professor_id == user.id


# =========================
# EJERCICIOS (biblioteca)
# =========================

@router.get("/profesor/exercises", response_class=HTMLResponse)
def exercises_list(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    items = load_professor_exercises(db, professor_id=professor_scope_id(me), q=q)

    return templates.TemplateResponse(
        request,
        "prof_exercises.html",
        {"request": request, "me": me, "items": items, "q": q},
    )


@router.get("/profesor/exercises/new", response_class=HTMLResponse)
def exercises_new_page(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    return templates.TemplateResponse(
        request,
        "prof_exercise_form.html",
        {"request": request, "me": me, "error": None, "item": None},
    )


@router.post("/profesor/exercises/new")
def exercises_new(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    muscle_group: str = Form(""),
    equipment: str = Form(""),
    video_url: str = Form(""),
    video_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    name_clean = name.strip()
    if not name_clean:
        return templates.TemplateResponse(
            request,
            "prof_exercise_form.html",
            {"request": request, "me": me, "error": "El nombre del ejercicio es obligatorio.", "item": None},
            status_code=400,
        )

    e = Exercise(
        professor_id=me.id,
        name=name_clean,
        description=description.strip(),
        muscle_group=muscle_group.strip(),
        equipment=equipment.strip(),
        video_url=video_url.strip() or None,
    )

    db.add(e)
    db.flush()

    if has_uploaded_file(video_file):
        save_private_exercise_video(
            db,
            exercise=e,
            upload=video_file,
            replace_existing=True,
        )

    db.commit()
    return RedirectResponse(url="/profesor/exercises", status_code=302)


@router.get("/profesor/exercises/{exercise_id}/edit", response_class=HTMLResponse)
def exercises_edit_page(
    request: Request,
    exercise_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    item = db.get(Exercise, exercise_id)
    if (not item) or (not can_manage_professor_resource(me, item.professor_id)):
        return RedirectResponse(url="/profesor/exercises", status_code=302)

    return templates.TemplateResponse(
        request,
        "prof_exercise_form.html",
        {"request": request, "me": me, "error": None, "item": item},
    )


@router.post("/profesor/exercises/{exercise_id}/edit")
@router.post("/profesor/exercises/{exercise_id}/edit")
def exercises_edit_save(
    request: Request,
    exercise_id: int,
    name: str = Form(...),
    description: str = Form(""),
    muscle_group: str = Form(""),
    equipment: str = Form(""),
    video_url: str = Form(""),
    video_file: UploadFile | None = File(None),
    delete_video: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    item = db.get(Exercise, exercise_id)
    if (not item) or (not can_manage_professor_resource(me, item.professor_id)):
        return RedirectResponse(url="/profesor/exercises", status_code=302)

    name_clean = name.strip()
    if not name_clean:
        return templates.TemplateResponse(
            request,
            "prof_exercise_form.html",
            {"request": request, "me": me, "error": "El nombre del ejercicio es obligatorio.", "item": item},
            status_code=400,
        )

    item.name = name_clean
    item.description = description.strip()
    item.muscle_group = muscle_group.strip()
    item.equipment = equipment.strip()
    item.video_url = video_url.strip() or None

    if delete_video == "1":
        delete_private_exercise_video(item)

    if has_uploaded_file(video_file):
        save_private_exercise_video(
            db,
            exercise=item,
            upload=video_file,
            replace_existing=True,
        )

    db.commit()
    return RedirectResponse(url="/profesor/exercises", status_code=302)

@router.get("/profesor/exercises/{exercise_id}/video")
def professor_exercise_video(
    exercise_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    exercise = db.get(Exercise, exercise_id)
    if (not exercise) or (not can_manage_professor_resource(me, exercise.professor_id)):
        raise HTTPException(status_code=404, detail="Video no encontrado.")

    return build_private_video_response(exercise)


# =========================
# RUTINAS
# =========================

@router.get("/profesor/routines", response_class=HTMLResponse)
def routines_list(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    routines = load_professor_routines(db, professor_id=professor_scope_id(me))

    return templates.TemplateResponse(
        request,
        "prof_routines.html",
        {"request": request, "me": me, "routines": routines},
    )


@router.get("/profesor/routines/new", response_class=HTMLResponse)
def routines_new_page(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    return templates.TemplateResponse(
        request,
        "prof_routine_form.html",
        {"request": request, "me": me, "error": None, "routine": None, "types": [t.value for t in RoutineType]},
    )


@router.post("/profesor/routines/new")
def routines_new(
    title: str = Form(...),
    notes: str = Form(""),
    routine_type: str = Form("DIAS"),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    r = Routine(
        professor_id=me.id,
        title=title.strip(),
        notes=notes.strip(),
        routine_type=RoutineType(routine_type),
    )
    db.add(r)
    db.commit()
    return RedirectResponse(url=f"/profesor/routines/{r.id}", status_code=302)


@router.get("/profesor/routines/{routine_id}", response_class=HTMLResponse)
def routine_detail(
    request: Request,
    routine_id: int = FPath(...),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    r = db.get(Routine, routine_id)
    if (not r) or (not can_manage_professor_resource(me, r.professor_id)):
        return RedirectResponse(url="/profesor/routines", status_code=302)

    # ✅ ACÁ VA (leer el parámetro err y armar el mensaje)
    err = request.query_params.get("err")
    error_msg = None
    if err == "asignada":
        error_msg = "No podés eliminar esta rutina porque está asignada a uno o más alumnos."

    exercises = load_professor_exercises(
        db,
        professor_id=professor_scope_id(me),
    )

    items = db.scalars(
        select(RoutineItem).where(RoutineItem.routine_id == r.id).order_by(RoutineItem.order_index.asc())
    ).all()

    students = load_professor_students(
        db,
        professor_id=professor_scope_id(me),
        q="",
    )

    return templates.TemplateResponse(
        request,
        "prof_routine_detail.html",
        {
            "request": request,
            "me": me,
            "routine": r,
            "items": items,
            "exercises": exercises,
            "students": students,
            "error": error_msg,  # ✅ acá lo enviás al template
        },
    )

@router.post("/profesor/routines/{routine_id}/delete")
def routine_delete(
    request: Request,
    routine_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    r = db.get(Routine, routine_id)
    if (not r) or (not can_manage_professor_resource(me, r.professor_id)):
        return RedirectResponse(url="/profesor/routines", status_code=302)

    # ❌ Bloquear si está asignada a cualquier alumno (activa o histórica)
    assigned_any = db.scalar(
        select(RoutineAssignment.id).where(RoutineAssignment.routine_id == r.id).limit(1)
    )
    if assigned_any:
        # Volvemos al detalle con mensaje
        return RedirectResponse(
            url=f"/profesor/routines/{r.id}?err=asignada",
            status_code=302
        )

    # ✅ Si no hay asignaciones, se puede borrar
    db.delete(r)
    db.commit()
    return RedirectResponse(url="/profesor/routines", status_code=302)

@router.post("/profesor/routines/{routine_id}/items/add")
def routine_add_item(
    routine_id: int,
    exercise_id: int = Form(...),

    # SEMANAS: "Semana 1"
    day_label: str = Form(""),

    # Día (Lunes..Domingo)
    weekday: str = Form(""),

    sets: int = Form(0),
    reps: str = Form(""),
    rest_seconds: int = Form(0),
    notes: str = Form(""),

    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    r = db.get(Routine, routine_id)
    if (not r) or (not can_manage_professor_resource(me, r.professor_id)):
        return RedirectResponse(url="/profesor/routines", status_code=302)

    ex = db.get(Exercise, exercise_id)
    if (not ex) or (not can_manage_professor_resource(me, ex.professor_id)):
        return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)

    day_label_clean = day_label.strip()
    weekday_clean = weekday.strip()

    max_order = db.scalar(
        select(func.max(RoutineItem.order_index)).where(
            RoutineItem.routine_id == r.id,
            RoutineItem.day_label == day_label_clean,
            RoutineItem.weekday == weekday_clean,
        )
    ) or 0

    it = RoutineItem(
        routine_id=r.id,
        exercise_id=ex.id,
        day_label=day_label_clean,
        weekday=weekday_clean,
        sets=sets,
        reps=reps.strip(),
        rest_seconds=rest_seconds,
        order_index=max_order + 1,
        notes=notes.strip(),
    )

    db.add(it)
    db.commit()
    return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)


# =========================
# EDITAR ITEM DE RUTINA
# =========================

@router.get("/profesor/routines/{routine_id}/items/{item_id}/edit", response_class=HTMLResponse)
def routine_item_edit_page(
    request: Request,
    routine_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    r = db.get(Routine, routine_id)
    if (not r) or (not can_manage_professor_resource(me, r.professor_id)):
        return RedirectResponse(url="/profesor/routines", status_code=302)

    it = db.get(RoutineItem, item_id)
    if (not it) or (it.routine_id != r.id):
        return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)

    # ejercicios disponibles (del prof)
    exercises = load_professor_exercises(
        db,
        professor_id=professor_scope_id(me),
    )

    days = [f"Día {i}" for i in range(1, 8)]  # Día 1..Día 7

    return templates.TemplateResponse(
        request,
        "prof_routine_item_edit.html",
        {
            "request": request,
            "me": me,
            "routine": r,
            "item": it,
            "exercises": exercises,
            "days": days,
            "error": None,
        },
    )


@router.post("/profesor/routines/{routine_id}/items/{item_id}/edit")
def routine_item_edit_save(
    routine_id: int,
    item_id: int,

    exercise_id: int = Form(...),
    day_label: str = Form(""),     # semana o etiqueta
    weekday: str = Form(""),       # día
    sets: int = Form(0),
    reps: str = Form(""),
    rest_seconds: int = Form(0),
    notes: str = Form(""),

    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    r = db.get(Routine, routine_id)
    if (not r) or (not can_manage_professor_resource(me, r.professor_id)):
        return RedirectResponse(url="/profesor/routines", status_code=302)

    it = db.get(RoutineItem, item_id)
    if (not it) or (it.routine_id != r.id):
        return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)

    ex = db.get(Exercise, exercise_id)
    if (not ex) or (not can_manage_professor_resource(me, ex.professor_id)):
        return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)

    it.exercise_id = ex.id
    it.day_label = day_label.strip()
    it.weekday = weekday.strip()
    it.sets = sets
    it.reps = reps.strip()
    it.rest_seconds = rest_seconds
    it.notes = notes.strip()

    db.commit()
    return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)

@router.post("/profesor/routines/{routine_id}/items/{item_id}/delete")
def routine_item_delete(
    routine_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    r = db.get(Routine, routine_id)
    if (not r) or (not can_manage_professor_resource(me, r.professor_id)):
        return RedirectResponse(url="/profesor/routines", status_code=302)

    it = db.get(RoutineItem, item_id)
    if (not it) or (it.routine_id != r.id):
        return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)

    db.delete(it)
    db.commit()
    return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)


# =========================
# ASIGNAR A ALUMNO
# =========================

@router.post("/profesor/routines/{routine_id}/assign")
def routine_assign(
    routine_id: int,
    student_id: int = Form(...),
    start_date: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    r = load_professor_owned_routine(
        db,
        professor_id=professor_scope_id(me),
        routine_id=routine_id,
    )
    if not r:
        return RedirectResponse(url="/profesor/routines", status_code=302)

    student = load_professor_owned_student(
        db,
        professor_id=professor_scope_id(me),
        student_id=student_id,
    )
    if not student:
        return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)

    sd = None
    if start_date.strip():
        sd = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()

    try:
        assign_routine_to_student(
            db,
            routine_id=r.id,
            student_id=student.id,
            assigned_by=me.id,
            start_date=sd,
        )
        db.commit()
    except Exception:
        db.rollback()

    return RedirectResponse(url=f"/profesor/routines/{routine_id}", status_code=302)

# =========================
# ASIGNACIONES (GLOBAL)
# =========================

@router.get("/profesor/assignments", response_class=HTMLResponse)
def assignments_page(
    request: Request,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    routines = load_professor_routines(db, professor_id=professor_scope_id(me))

    students = load_professor_students(
        db,
        professor_id=professor_scope_id(me),
        q="",
    )

    active_assignments = load_professor_active_assignments(db, professor_id=professor_scope_id(me))

    return templates.TemplateResponse(
        request,
        "prof_assignments.html",
        {
            "request": request,
            "me": me,
            "routines": routines,
            "students": students,
            "active_assignments": active_assignments,
            "error": None,
            "ok": None,
        },
    )


@router.post("/profesor/assignments")
def assignments_do(
    request: Request,
    student_id: int = Form(...),
    routine_id: int = Form(...),
    start_date: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    r = load_professor_owned_routine(
        db,
        professor_id=professor_scope_id(me),
        routine_id=routine_id,
    )
    if not r:
        return RedirectResponse(url="/profesor/assignments", status_code=302)

    student = load_professor_owned_student(
        db,
        professor_id=professor_scope_id(me),
        student_id=student_id,
    )
    if not student:
        return RedirectResponse(url="/profesor/assignments", status_code=302)

    sd = None
    if start_date.strip():
        sd = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()

    try:
        assign_routine_to_student(
            db,
            routine_id=r.id,
            student_id=student.id,
            assigned_by=me.id,
            start_date=sd,
        )
        db.commit()
    except Exception:
        db.rollback()

    return RedirectResponse(url="/profesor/assignments", status_code=302)


@router.post("/profesor/assignments/{student_id}/deactivate")
def deactivate_active_assignment(
    student_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    student = load_professor_owned_student(
        db,
        professor_id=professor_scope_id(me),
        student_id=student_id,
    )
    if not student:
        return RedirectResponse(url="/profesor/assignments", status_code=302)

    stmt = (
        select(RoutineAssignment)
        .join(Routine, Routine.id == RoutineAssignment.routine_id)
        .where(
            RoutineAssignment.student_id == student_id,
            RoutineAssignment.is_active.is_(True),
        )
        .order_by(RoutineAssignment.id.desc())
    )

    if not is_admin_user(me):
        stmt = stmt.where(Routine.professor_id == me.id)

    a = db.scalars(stmt).first()

    if a:
        try:
            a.is_active = False
            db.commit()
        except Exception:
            db.rollback()

    return RedirectResponse(url="/profesor/assignments", status_code=302)


@router.get("/profesor/assignments/history/{student_id}", response_class=HTMLResponse)
def assignment_history(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    student = load_professor_owned_student(
        db,
        professor_id=professor_scope_id(me),
        student_id=student_id,
    )
    if not student:
        return RedirectResponse(url="/profesor/assignments", status_code=302)

    assignments = load_professor_assignment_history(
        db,
        professor_id=professor_scope_id(me),
        student_id=student_id,
    )

    return templates.TemplateResponse(
        request,
        "prof_assignment_history.html",
        {
            "request": request,
            "me": me,
            "student": student,
            "assignments": assignments,
        },
    )

# =========================
# MIS ALUMNOS (a cargo)
# =========================

@router.get("/profesor/alumnos", response_class=HTMLResponse)
def mis_alumnos(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    alumnos = load_professor_students(db, professor_id=professor_scope_id(me), q=q)
    routines = load_professor_routines(db, professor_id=professor_scope_id(me))

    active_by_student = load_professor_active_assignments_map(
        db,
        professor_id=professor_scope_id(me),
        student_ids=[a.id for a in alumnos],
    )

    return templates.TemplateResponse(
        request,
        "prof_mis_alumnos.html",
        {
            "request": request,
            "me": me,
            "alumnos": alumnos,
            "q": q,
            "routines": routines,
            "active_by_student": active_by_student,
        },
    )


@router.post("/profesor/alumnos/{student_id}/assign")
def asignar_rutina_a_mi_alumno(
    student_id: int,
    routine_id: int = Form(...),
    start_date: str = Form(""),
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(PROF_ONLY)),
):
    student = load_professor_owned_student(
        db,
        professor_id=professor_scope_id(me),
        student_id=student_id,
    )
    if not student:
        return RedirectResponse(url="/profesor/alumnos", status_code=302)

    r = load_professor_owned_routine(
        db,
        professor_id=professor_scope_id(me),
        routine_id=routine_id,
    )
    if not r:
        return RedirectResponse(url="/profesor/alumnos", status_code=302)

    sd = None
    if start_date.strip():
        sd = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()

    assign_routine_to_student(
        db,
        routine_id=r.id,
        student_id=student.id,
        assigned_by=me.id,
        start_date=sd,
    )
    db.commit()

    return RedirectResponse(url="/profesor/alumnos", status_code=302)