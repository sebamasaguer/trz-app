from __future__ import annotations

from datetime import datetime
import secrets
import string

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Role, User
from .admin_list_service import build_pagination_context, parse_pagination_params


PANEL_ALLOWED_ROLES = [Role.ADMINISTRADOR.value, Role.ADMINISTRATIVO.value]
RESET_ALLOWED_ROLES = [Role.ADMINISTRADOR.value]

CHECKBOX_TRUE_VALUES = {"true", "1", "on", "yes", "si", "sí"}
ACTIVE_FILTER_VALUES = {"true", "false"}
DEFAULT_PAGE_SIZE = 20


def role_values_for_user(me: User) -> list[str]:
    if me.role == Role.ADMINISTRADOR:
        return [r.value for r in Role]
    return [
        Role.ADMINISTRATIVO.value,
        Role.PROFESOR.value,
        Role.ALUMNO.value,
    ]


def can_manage_target(me: User, target: User) -> bool:
    if me.role == Role.ADMINISTRADOR:
        return True

    if me.role == Role.ADMINISTRATIVO:
        return target.role != Role.ADMINISTRADOR

    return False


def can_assign_role(me: User, role_value: str) -> bool:
    if me.role == Role.ADMINISTRADOR:
        return role_value in {r.value for r in Role}

    if me.role == Role.ADMINISTRATIVO:
        return role_value in {
            Role.ADMINISTRATIVO.value,
            Role.PROFESOR.value,
            Role.ALUMNO.value,
        }

    return False


def can_reset_password(me: User, target: User) -> bool:
    return me.role == Role.ADMINISTRADOR and target.id != me.id


def can_toggle_user(me: User, target: User) -> bool:
    if target.id == me.id:
        return False
    return can_manage_target(me, target)


def can_delete_user(me: User, target: User) -> bool:
    if target.id == me.id:
        return False
    return me.role == Role.ADMINISTRADOR


def normalize_text(value: str | None) -> str:
    return (value or "").strip()


def normalize_optional_text(value: str | None) -> str | None:
    cleaned = normalize_text(value)
    return cleaned or None


def normalize_email(value: str | None) -> str:
    return normalize_text(value).lower()


def parse_birth_date(value: str | None):
    raw = normalize_text(value)
    if not raw:
        return None

    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Fecha inválida (YYYY-MM-DD).")


def parse_is_active(value: str | None) -> bool:
    return normalize_text(value).lower() in CHECKBOX_TRUE_VALUES


def build_full_name(first_name: str | None, last_name: str | None) -> str:
    return " ".join(part for part in [normalize_text(first_name), normalize_text(last_name)] if part).strip()


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def build_users_list_query(
    *,
    q: str = "",
    role: str = "",
    is_active: str = "",
):
    stmt = select(User)

    q_clean = normalize_text(q)
    if q_clean:
        like = f"%{q_clean}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.dni.ilike(like),
                User.full_name.ilike(like),
            )
        )

    role_clean = normalize_text(role)
    if role_clean:
        stmt = stmt.where(User.role == Role(role_clean))

    active_clean = normalize_text(is_active).lower()
    if active_clean == "true":
        stmt = stmt.where(User.is_active.is_(True))
    elif active_clean == "false":
        stmt = stmt.where(User.is_active.is_(False))

    return stmt


def count_users(
    db: Session,
    *,
    q: str = "",
    role: str = "",
    is_active: str = "",
) -> int:
    stmt = build_users_list_query(q=q, role=role, is_active=is_active)
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


def load_users_paginated(
    db: Session,
    *,
    q: str = "",
    role: str = "",
    is_active: str = "",
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
) -> list[User]:
    stmt = (
        build_users_list_query(q=q, role=role, is_active=is_active)
        .order_by(User.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(stmt).all()


def build_users_list_context(
    *,
    request,
    me: User,
    users: list[User],
    q: str,
    role: str,
    is_active: str,
    page: int,
    page_size: int,
    total: int,
) -> dict:
    return {
        "request": request,
        "me": me,
        "users": users,
        "q": q,
        "role": role,
        "is_active": is_active,
        "roles": [r.value for r in Role],
        **build_pagination_context(
            page=page,
            page_size=page_size,
            total=total,
        ),
    }


def build_user_form_context(
    *,
    request,
    me: User,
    user,
    mode: str,
    error: str | None,
) -> dict:
    return {
        "request": request,
        "me": me,
        "user": user,
        "mode": mode,
        "error": error,
        "roles": role_values_for_user(me),
    }


def validate_new_user_payload(
    db: Session,
    *,
    me: User,
    email: str,
    role: str,
    dni: str | None,
) -> str | None:
    if not email:
        return "El email es obligatorio."

    if not can_assign_role(me, role):
        return "No tenés permisos para asignar ese rol."

    if db.scalar(select(User).where(User.email == email)):
        return "Ese email ya existe."

    if dni and db.scalar(select(User).where(User.dni == dni)):
        return "Ese DNI ya existe."

    return None


def validate_edit_user_payload(
    db: Session,
    *,
    me: User,
    target: User,
    email: str,
    role: str,
    dni: str | None,
) -> str | None:
    if not can_manage_target(me, target):
        return "No tenés permisos para editar este usuario."

    if not email:
        return "El email es obligatorio."

    if not can_assign_role(me, role):
        return "No tenés permisos para asignar ese rol."

    if db.scalar(select(User).where(User.email == email, User.id != target.id)):
        return "Ese email ya existe."

    if dni and db.scalar(select(User).where(User.dni == dni, User.id != target.id)):
        return "Ese DNI ya existe."

    return None


def build_user_from_form(
    *,
    user: User | None,
    email: str,
    role: str,
    first_name: str,
    last_name: str,
    dni: str | None,
    birth_date,
    address: str,
    phone: str,
    emergency_contact_name: str,
    emergency_contact_phone: str,
    is_active: bool,
) -> User:
    target = user or User()

    target.email = email
    target.role = Role(role)
    target.first_name = first_name
    target.last_name = last_name
    target.full_name = build_full_name(first_name, last_name)
    target.dni = dni
    target.birth_date = birth_date
    target.address = address
    target.phone = phone
    target.emergency_contact_name = emergency_contact_name
    target.emergency_contact_phone = emergency_contact_phone
    target.is_active = is_active

    return target


def sanitize_user_form_input(
    *,
    email: str,
    role: str,
    first_name: str,
    last_name: str,
    dni: str,
    birth_date: str,
    address: str,
    phone: str,
    emergency_contact_name: str,
    emergency_contact_phone: str,
):
    return {
        "email": normalize_email(email),
        "role": normalize_text(role),
        "first_name": normalize_text(first_name),
        "last_name": normalize_text(last_name),
        "dni": normalize_optional_text(dni),
        "birth_date": parse_birth_date(birth_date),
        "address": normalize_text(address),
        "phone": normalize_text(phone),
        "emergency_contact_name": normalize_text(emergency_contact_name),
        "emergency_contact_phone": normalize_text(emergency_contact_phone),
    }


def parse_users_list_filters(
    *,
    q,
    role,
    is_active,
    page,
    page_size,
):
    pagination = parse_pagination_params(page, page_size, default_page_size=DEFAULT_PAGE_SIZE)
    return {
        "q": normalize_text(q),
        "role": normalize_text(role),
        "is_active": normalize_text(is_active).lower(),
        "page": pagination.page,
        "page_size": pagination.page_size,
        "offset": pagination.offset,
    }