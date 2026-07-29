"""Autenticacion: hash/verificacion de contrasenas y login contra la BD."""
import bcrypt
from sqlalchemy import select

from db.models import Usuario

MIN_PASSWORD_LENGTH = 8


def validar_longitud_password(password: str) -> None:
    """Regla unica de fortaleza minima, reutilizada por los 3 lugares
    donde se recibe una contrasena nueva (creacion de usuario, cambio de
    contrasena y restablecimiento por token) via field_validator de
    Pydantic."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def autenticar(session, username: str, password: str) -> Usuario | None:
    usuario = session.scalar(
        select(Usuario).where(Usuario.username == username.strip().lower(), Usuario.activo.is_(True))
    )
    if usuario is None:
        return None
    if not verificar_password(password, usuario.password_hash):
        return None
    return usuario
