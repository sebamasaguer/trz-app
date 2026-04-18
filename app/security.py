import hmac
import hashlib
import secrets
import logging
from datetime import timedelta, date
from app.utils.datetime_utils import utcnow_naive

from jose import jwt, JWTError
from passlib.context import CryptContext

from .core.config import settings


logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _pepper_sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return pwd_context.hash(_pepper_sha256(password))


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(_pepper_sha256(password), password_hash)


def create_access_token(payload: dict) -> str:
    exp = utcnow_naive() + timedelta(minutes=settings.JWT_ACCESS_MIN)
    to_encode = {**payload, "exp": exp}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        logger.warning("Token inválido o expirado")
        raise ValueError("Token inválido o expirado") from exc


def qr_make_payload(service: str, d: date | None = None) -> str:
    d = d or date.today()
    nonce = secrets.token_hex(6)
    base = f"{service}|{d.isoformat()}|{nonce}"
    sig = hmac.new(
        settings.QR_SECRET.encode(),
        base.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]
    return f"TRZ|{service}|{d.isoformat()}|{nonce}|{sig}"


def qr_verify_payload(payload: str) -> tuple[bool, str, date]:
    try:
        parts = payload.strip().split("|")
        if len(parts) != 5 or parts[0] != "TRZ":
            return (False, "", date.today())

        service = parts[1]
        d_str = parts[2]
        nonce = parts[3]
        sig = parts[4]
        d = date.fromisoformat(d_str)

        if service not in ("FUNCIONAL", "MUSCULACION"):
            return (False, "", d)

        base = f"{service}|{d.isoformat()}|{nonce}"
        expected = hmac.new(
            settings.QR_SECRET.encode(),
            base.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]

        if not hmac.compare_digest(sig, expected):
            return (False, "", d)

        return (True, service, d)
    except Exception:
        return (False, "", date.today())