"""Emision y verificacion de tokens JWT para la API. El hash/verificacion
de contrasenas vive en db/auth.py (compartido con Streamlit)."""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from backend.core.config import settings


def crear_access_token(usuario_id: int, username: str, rol: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(usuario_id), "username": username, "rol": rol, "exp": expira}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decodificar_access_token(token: str) -> dict:
    """Lanza jose.JWTError si el token es invalido o expiro."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
