"""Aviso de Privacidad y Autorización para el Tratamiento de Datos
Personales: los 4 roles deben aceptarlo antes de usar el resto del
sistema (Ley 1581 de 2012)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from agente_notas.aviso_privacidad import TEXTO_POLITICA, TITULO_POLITICA, VERSION_POLITICA
from backend.api.deps import get_current_user, get_db
from backend.api.routers.auth import _usuario_out
from backend.schemas.auth import UsuarioOut
from backend.schemas.consentimiento import PoliticaOut
from db.models import Usuario
from db.repository import registrar_aceptacion_tratamiento_datos

router = APIRouter(prefix="/api/consentimiento", tags=["consentimiento"])


@router.get("/politica", response_model=PoliticaOut)
def politica():
    return PoliticaOut(version=VERSION_POLITICA, titulo=TITULO_POLITICA, texto=TEXTO_POLITICA)


@router.post("/aceptar", response_model=UsuarioOut)
def aceptar(request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    direccion_ip = request.client.host if request.client else None
    usuario = registrar_aceptacion_tratamiento_datos(db, usuario.id, VERSION_POLITICA, direccion_ip)
    return _usuario_out(usuario)
