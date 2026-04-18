from fastapi import Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import decode_token

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        # Redirigir al login en vez de 401 JSON
        raise _RedirectToLogin()

    try:
        data = decode_token(token)
    except Exception:
        raise _RedirectToLogin()

    user_id = data.get("sub")
    if not user_id:
        raise _RedirectToLogin()

    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise _RedirectToLogin()

    return user

def require_roles(allowed: list[str]):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in allowed:
            # Si no tiene permisos, lo mandamos al login o a una página de "sin permisos"
            raise _RedirectToLogin()
        return user
    return _dep

class _RedirectToLogin(Exception):
    pass

def redirect_to_login_handler(request: Request, exc: _RedirectToLogin):
    return RedirectResponse(url="/login", status_code=302)