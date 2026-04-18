from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import User, Role, Prospect, ProspectStatus


def normalize_phone(phone: str | None) -> str:
    raw = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not raw:
        return ""
    if raw.startswith("549"):
        return raw
    if raw.startswith("54"):
        return f"549{raw[2:]}"
    if raw.startswith("9"):
        return f"54{raw}"
    if raw.startswith("0"):
        raw = raw.lstrip("0")
    return f"549{raw}"


def find_student_by_phone(db: Session, phone: str) -> User | None:
    if not phone:
        return None

    candidates = {phone}
    if phone.startswith("549"):
        candidates.add(phone[2:])
        candidates.add(phone[3:])
    if phone.startswith("54"):
        candidates.add(phone[2:])

    rows = db.scalars(
        select(User).where(
            User.role == Role.ALUMNO,
            or_(*[User.phone.like(f"%{candidate}%") for candidate in candidates if candidate]),
        )
    ).all()

    return rows[0] if rows else None


def find_or_create_prospect(
    db: Session,
    name: str,
    phone: str,
    email: str = "",
    *,
    auto_commit: bool = True,
) -> Prospect:
    row = db.scalars(select(Prospect).where(Prospect.phone == phone)).first()

    if row:
        changed = False
        if name and not row.full_name:
            row.full_name = name
            changed = True
        if email and not row.email:
            row.email = email
            changed = True

        if auto_commit and changed:
            db.commit()
        return row

    row = Prospect(
        full_name=(name or "").strip(),
        phone=phone,
        email=(email or "").strip(),
        source="WHATSAPP",
        status=ProspectStatus.NUEVO,
    )
    db.add(row)

    if auto_commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()

    return row