"""Autenticacion: hash/verificacion de contrasenas y login contra la BD."""
import bcrypt
from sqlalchemy import select

from db.models import Usuario


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
