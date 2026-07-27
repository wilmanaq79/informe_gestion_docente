from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, get_db
from backend.core.security import crear_access_token
from backend.schemas.auth import LoginRequest, TokenResponse, UsuarioOut
from db.auth import autenticar
from db.models import Usuario

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _usuario_out(usuario: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=usuario.id,
        nombre_completo=usuario.nombre_completo,
        username=usuario.username,
        rol=usuario.rol.nombre,
        activo=usuario.activo,
    )


@router.post("/login", response_model=TokenResponse)
def login(datos: LoginRequest, db: Session = Depends(get_db)):
    usuario = autenticar(db, datos.username, datos.password)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos")

    token = crear_access_token(usuario.id, usuario.username, usuario.rol.nombre)
    return TokenResponse(access_token=token, usuario=_usuario_out(usuario))


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_user)):
    return _usuario_out(usuario)
