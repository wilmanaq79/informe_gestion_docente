"""Administracion de usuarios (altas de docentes, director, secretario)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db, requiere_roles, verificar_pertenece_a_programa
from backend.schemas.usuario import UsuarioCreate, UsuarioOut, UsuarioUpdate
from db.auth import hash_password
from db.models import Usuario
from db.repository import actualizar_usuario, crear_usuario, listar_roles, listar_usuarios

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


def _out(u: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=u.id,
        nombre_completo=u.nombre_completo,
        cedula=u.cedula,
        email=u.email,
        telefono=u.telefono,
        username=u.username,
        rol=u.rol.nombre,
        activo=u.activo,
    )


@router.get("", response_model=list[UsuarioOut])
def listar(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles("director", "secretario", "secretaria_programa")),
):
    return [_out(u) for u in listar_usuarios(db, usuario.programa_id)]


@router.post("", response_model=UsuarioOut, status_code=201)
def crear(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles("director", "secretario")),
):
    if usuario.programa_id is None:
        raise HTTPException(
            status_code=400,
            detail="Tu cuenta no pertenece a ningún programa académico y no puede crear usuarios. "
            "El alta del primer Director de un programa nuevo se hace mediante el script de onboarding.",
        )
    roles = {r.nombre: r.id for r in listar_roles(db)}
    if datos.rol not in roles:
        raise HTTPException(status_code=400, detail=f"Rol inválido: {datos.rol}. Debe ser uno de {list(roles)}.")
    try:
        usuario_creado = crear_usuario(
            db,
            datos.nombre_completo,
            datos.cedula,
            datos.email,
            datos.username,
            hash_password(datos.password),
            roles[datos.rol],
            # El nuevo usuario SIEMPRE queda en el mismo programa de quien lo
            # crea -- nunca es elegible desde el formulario, para que un
            # Director no pueda (ni por error) dar de alta a alguien en otro
            # programa academico.
            programa_id=usuario.programa_id,
            telefono=datos.telefono,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"No se pudo crear el usuario (¿usuario o cédula repetidos?): {exc}"
        )
    return _out(usuario_creado)


@router.put("/{usuario_id}", response_model=UsuarioOut)
def actualizar(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles("director", "secretario")),
):
    objetivo = db.get(Usuario, usuario_id)
    if objetivo is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    verificar_pertenece_a_programa(objetivo.programa_id, usuario)

    campos = datos.model_dump(exclude_unset=True)
    try:
        actualizado = actualizar_usuario(db, usuario_id, **campos)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"No se pudo actualizar el usuario (¿cédula repetida?): {exc}"
        )
    return _out(actualizado)
