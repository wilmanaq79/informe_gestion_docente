"""Notificaciones dentro de la aplicación (independientes del correo):
la campanita que ven los 4 roles con avisos de entregas aprobadas o
rechazadas."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, get_db
from backend.schemas.notificacion import NotificacionOut
from db.models import Usuario
from db.repository import (
    contar_notificaciones_no_leidas,
    listar_notificaciones,
    marcar_notificacion_leida,
    marcar_todas_notificaciones_leidas,
)

router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])


@router.get("", response_model=list[NotificacionOut])
def listar(
    solo_no_leidas: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    return listar_notificaciones(db, usuario.id, solo_no_leidas=solo_no_leidas)


@router.get("/contador")
def contador(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    return {"no_leidas": contar_notificaciones_no_leidas(db, usuario.id)}


@router.post("/{notificacion_id}/leer")
def leer(notificacion_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    if not marcar_notificacion_leida(db, notificacion_id, usuario.id):
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return {"ok": True}


@router.post("/leer-todas")
def leer_todas(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    marcar_todas_notificaciones_leidas(db, usuario.id)
    return {"ok": True}
