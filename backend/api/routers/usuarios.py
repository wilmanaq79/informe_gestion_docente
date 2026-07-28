"""Administracion de usuarios (altas de docentes, director, secretario)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db, requiere_roles
from backend.schemas.usuario import UsuarioCreate, UsuarioOut
from db.auth import hash_password
from db.models import Usuario
from db.repository import crear_usuario, listar_roles, listar_usuarios

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


def _out(u: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=u.id,
        nombre_completo=u.nombre_completo,
        cedula=u.cedula,
        email=u.email,
        username=u.username,
        rol=u.rol.nombre,
        activo=u.activo,
    )


@router.get("", response_model=list[UsuarioOut])
def listar(
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario", "secretaria_programa")),
):
    return [_out(u) for u in listar_usuarios(db)]


@router.post("", response_model=UsuarioOut, status_code=201)
def crear(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(requiere_roles("director", "secretario")),
):
    roles = {r.nombre: r.id for r in listar_roles(db)}
    if datos.rol not in roles:
        raise HTTPException(status_code=400, detail=f"Rol inválido: {datos.rol}. Debe ser uno de {list(roles)}.")
    try:
        usuario = crear_usuario(
            db,
            datos.nombre_completo,
            datos.cedula,
            datos.email,
            datos.username,
            hash_password(datos.password),
            roles[datos.rol],
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"No se pudo crear el usuario (¿usuario o cédula repetidos?): {exc}"
        )
    return _out(usuario)
