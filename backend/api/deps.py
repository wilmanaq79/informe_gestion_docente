"""Dependencias de FastAPI: sesion de base de datos, usuario autenticado
(JWT), control de acceso por rol, y el gate de aceptacion del Aviso de
Privacidad y Tratamiento de Datos Personales (Ley 1581 de 2012)."""
from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from agente_notas.aviso_privacidad import acepto_politica_vigente
from backend.core.security import decodificar_access_token
from db.database import get_session
from db.models import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas o sesion expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decodificar_access_token(token)
        usuario_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credenciales_invalidas

    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise credenciales_invalidas
    return usuario


def requiere_consentimiento(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    """Bloquea cualquier endpoint de negocio si el usuario autenticado
    no ha aceptado la version vigente del Aviso de Privacidad y
    Tratamiento de Datos Personales. Se aplica a nivel de router (ver
    backend/main.py) a todos los routers salvo auth y consentimiento,
    que deben seguir funcionando ANTES de aceptar (login, /auth/me,
    consultar y aceptar la politica)."""
    if not acepto_politica_vigente(usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Debes aceptar el Aviso de Privacidad y Autorización para el Tratamiento de Datos "
                "Personales antes de continuar."
            ),
        )
    return usuario


def requiere_roles(*roles_permitidos: str):
    def dependencia(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol.nombre not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Esta accion requiere uno de estos roles: {', '.join(roles_permitidos)}",
            )
        return usuario

    return dependencia


def verificar_pertenece_a_programa(programa_id_entidad: int | None, usuario: Usuario) -> None:
    """Bloquea el acceso si una entidad (docente, entrega, informe,
    entrada del repositorio de asignaturas...) no pertenece al mismo
    programa academico que el usuario autenticado. Cada programa es
    administrativamente independiente -- un Director/Secretario/
    Secretaria del Programa X nunca debe poder ver ni modificar datos
    del Programa Y, aunque conozca su id.

    Generaliza el mismo tipo de chequeo que ya hacian
    _verificar_acceso_entrega (backend/api/routers/entregas.py) y
    _verificar_permiso_programa (backend/api/routers/
    repositorio_asignaturas.py) para "es tu propio recurso" -- este es
    el control ortogonal de "es de tu programa", y se usa ADEMAS de
    esos, no en su reemplazo."""
    if usuario.programa_id is None or programa_id_entidad != usuario.programa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes acceder a datos de otro programa académico.",
        )
