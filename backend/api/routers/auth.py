import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agente_notas.aviso_privacidad import acepto_politica_vigente
from agente_notas.notificaciones import notificar_recuperacion_password
from backend.api.deps import get_current_user, get_db
from backend.core.config import settings
from backend.core.rate_limit import bloqueado, limpiar, registrar_intento_fallido
from backend.core.security import crear_access_token
from backend.schemas.auth import (
    CambiarPasswordRequest,
    LoginRequest,
    MensajeGenericoOut,
    RestablecerPasswordRequest,
    SolicitarRecuperacionRequest,
    TokenResponse,
    UsuarioOut,
)
from db.auth import autenticar, hash_password, verificar_password
from db.models import Usuario
from db.repository import consumir_token_recuperacion, crear_token_recuperacion

router = APIRouter(prefix="/api/auth", tags=["auth"])

MENSAJE_RECUPERACION_GENERICO = "Si el usuario existe, se enviará un correo con instrucciones para recuperar la contraseña."


def _usuario_out(usuario: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=usuario.id,
        nombre_completo=usuario.nombre_completo,
        username=usuario.username,
        rol=usuario.rol.nombre,
        activo=usuario.activo,
        acepto_tratamiento_datos=acepto_politica_vigente(usuario),
        debe_cambiar_password=usuario.debe_cambiar_password,
        programa_id=usuario.programa_id,
        programa_nombre=usuario.programa.nombre if usuario.programa else None,
    )


def _clave_rate_limit_recuperacion(username: str) -> str:
    normalizado = username.strip().lower()
    return f"reset:{hashlib.sha256(normalizado.encode('utf-8')).hexdigest()[:16]}"


@router.post("/login", response_model=TokenResponse)
def login(datos: LoginRequest, db: Session = Depends(get_db)):
    clave_intentos = datos.username.strip().lower()
    if bloqueado(db, clave_intentos):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos con este usuario. Intenta de nuevo en unos minutos.",
        )

    usuario = autenticar(db, datos.username, datos.password)
    if usuario is None:
        registrar_intento_fallido(db, clave_intentos)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos")

    limpiar(db, clave_intentos)
    token = crear_access_token(usuario.id, usuario.username, usuario.rol.nombre)
    return TokenResponse(access_token=token, usuario=_usuario_out(usuario))


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_user)):
    return _usuario_out(usuario)


@router.post("/cambiar-password", response_model=UsuarioOut)
def cambiar_password(datos: CambiarPasswordRequest, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Disponible en cualquier momento para cualquier rol -- tanto para el
    cambio libre y voluntario como para el gate obligatorio de contraseña
    temporal (backend.api.deps.requiere_password_actualizada), que deja
    este endpoint sin bloquear porque el router 'auth' completo queda
    fuera del gate (ver backend/main.py)."""
    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta.")

    usuario.password_hash = hash_password(datos.password_nueva)
    usuario.debe_cambiar_password = False
    db.commit()
    db.refresh(usuario)
    return _usuario_out(usuario)


def _enviar_correo_recuperacion_en_segundo_plano(destinatario_email: str | None, destinatario_nombre: str, enlace: str) -> None:
    """Corre DESPUES de que la respuesta HTTP ya se envio (FastAPI
    BackgroundTasks), igual que _enviar_correo_aprobacion_en_segundo_plano
    en backend/api/routers/entregas.py -- el envio SMTP es sincrono y no
    debe bloquear la respuesta de 'solicitar-recuperacion'."""
    notificar_recuperacion_password(destinatario_email, destinatario_nombre, enlace)


@router.post("/solicitar-recuperacion", response_model=MensajeGenericoOut)
def solicitar_recuperacion(
    datos: SolicitarRecuperacionRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Sin autenticacion (es el paso previo al login). Responde SIEMPRE
    el mismo mensaje generico, exista o no el usuario, y sin importar si
    tiene correo registrado -- evita que alguien pueda usar este endpoint
    para averiguar que usernames existen en el sistema."""
    clave = _clave_rate_limit_recuperacion(datos.username)
    if bloqueado(db, clave):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes de recuperación para este usuario. Intenta de nuevo en unos minutos.",
        )
    registrar_intento_fallido(db, clave)

    usuario = db.scalar(select(Usuario).where(Usuario.username == datos.username.strip().lower()))
    if usuario is not None and usuario.activo and usuario.email:
        token = crear_token_recuperacion(db, usuario.id)
        enlace = f"{settings.FRONTEND_URL}/restablecer-password?token={token}"
        background_tasks.add_task(
            _enviar_correo_recuperacion_en_segundo_plano, usuario.email, usuario.nombre_completo, enlace
        )

    return MensajeGenericoOut(mensaje=MENSAJE_RECUPERACION_GENERICO)


@router.post("/restablecer-password", response_model=MensajeGenericoOut)
def restablecer_password(datos: RestablecerPasswordRequest, db: Session = Depends(get_db)):
    """Sin autenticacion -- el token en si mismo es la credencial. Un
    token invalido/vencido/ya usado responde con el mismo mensaje
    generico, sin distinguir el motivo (evita filtrar informacion util
    para un atacante)."""
    usuario = consumir_token_recuperacion(db, datos.token)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El enlace no es válido o ya expiró.")

    usuario.password_hash = hash_password(datos.password_nueva)
    usuario.debe_cambiar_password = False
    db.commit()
    return MensajeGenericoOut(mensaje="Contraseña restablecida. Ya puedes iniciar sesión con tu nueva contraseña.")
