from datetime import datetime, UTC


def utcnow_naive() -> datetime:
    """
    Devuelve fecha/hora UTC naive para mantener compatibilidad
    con el esquema actual y evitar datetime.utcnow().
    """
    return datetime.now(UTC).replace(tzinfo=None)