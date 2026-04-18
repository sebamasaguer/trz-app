from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=False)


def _get_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, str(default))).strip().lower()
    return raw in {"1", "true", "yes", "on", "si", "sí"}


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "TRZ FUNCIONAL")
    ENV: str = os.getenv("ENV", "dev").strip().lower()

    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

    JWT_SECRET: str = os.getenv("JWT_SECRET", "").strip()
    JWT_ACCESS_MIN: int = int(os.getenv("JWT_ACCESS_MIN", "120"))
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256").strip()

    QR_SECRET: str = os.getenv("QR_SECRET", "cambiame_una_clave_larga_y_random").strip()

    COOKIE_SECURE: bool = _get_bool("COOKIE_SECURE", False)
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
    COOKIE_MAX_AGE: int = int(os.getenv("COOKIE_MAX_AGE", str(60 * 60 * 12)))

    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "").strip()

    N8N_FOLLOWUP_WEBHOOK_URL: str = os.getenv("N8N_FOLLOWUP_WEBHOOK_URL", "").strip()
    FOLLOWUP_WEBHOOK_TOKEN: str = os.getenv("FOLLOWUP_WEBHOOK_TOKEN", "").strip()

    ASSISTANT_WEBHOOK_TOKEN: str = os.getenv("ASSISTANT_WEBHOOK_TOKEN", "").strip()
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

    TRZ_HUMAN_HANDOFF_PHONE: str = os.getenv("TRZ_HUMAN_HANDOFF_PHONE", "").strip()
    TRZ_HUMAN_HANDOFF_NAME: str = os.getenv("TRZ_HUMAN_HANDOFF_NAME", "asesor comercial").strip()

    N8N_MANUAL_MESSAGE_WEBHOOK_URL: str = os.getenv("N8N_MANUAL_MESSAGE_WEBHOOK_URL", "").strip()
    N8N_MANUAL_MESSAGE_TOKEN: str = os.getenv("N8N_MANUAL_MESSAGE_TOKEN", "").strip()

    @property
    def is_production(self) -> bool:
        return self.ENV in {"prod", "production"}

    @property
    def is_dev(self) -> bool:
        return self.ENV in {"dev", "development", "local"}


settings = Settings()


if not settings.DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está definido en .env")

if len(settings.JWT_SECRET) < 16:
    raise RuntimeError("JWT_SECRET demasiado corto. Usá una clave larga (mínimo 16).")