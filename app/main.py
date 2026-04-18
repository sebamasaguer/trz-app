import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.logging_config import setup_logging
# ya no necesitamos engine ni Base acá
from .deps import _RedirectToLogin, redirect_to_login_handler
from .routers import auth, admin_users, profesor, alumno
from .routers import admin_memberships
from .routers import admin_payments
from .routers import admin_cash
from .routers import admin_dashboard
from .routers import admin_followups
from .routers import admin_templates
from .routers import admin_classes
from .routers import assistant_ai


setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)
app.add_exception_handler(_RedirectToLogin, redirect_to_login_handler)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

logger.info("Aplicación iniciada")

app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(profesor.router)
app.include_router(alumno.router)
app.include_router(admin_memberships.router)
app.include_router(admin_payments.router)
app.include_router(admin_cash.router, prefix="/admin/caja", tags=["Caja"])
app.include_router(admin_dashboard.router, tags=["Dashboard"])
app.include_router(admin_followups.router)
app.include_router(admin_templates.router)
app.include_router(admin_classes.router)
app.include_router(assistant_ai.router)


@app.get("/")
def root():
    return {"ok": True, "go": "/login"}