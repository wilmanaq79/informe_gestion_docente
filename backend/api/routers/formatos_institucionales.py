"""Los 3 formatos institucionales del programa académico (gestión y
autoevaluación docente, acuerdo pedagógico, plan de actividades): un
único juego de archivos por PROGRAMA completo, no por materia (a
diferencia del sílabo/programa de asignatura de
repositorio_asignaturas.py). Director, Secretario Académico y
Secretaria del Programa suben/reemplazan/eliminan; cualquier rol del
mismo programa consulta y descarga. No hay {id_} en la URL: el
programa objetivo siempre es el del usuario autenticado."""
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agente_notas.almacenamiento import (
    ArchivoInvalido,
    guardar_archivo_institucional,
    nombre_seguro_para_header,
    ruta_absoluta_segura,
    tipo_y_disposicion,
)
from backend.api.deps import get_db, requiere_roles
from backend.schemas.formato_institucional import FormatoInstitucionalOut
from db.models import Programa, Usuario
from db.repository import (
    TIPOS_FORMATO_INSTITUCIONAL,
    adjuntar_formato_institucional,
    quitar_formato_institucional,
)

router = APIRouter(prefix="/api/formatos-institucionales", tags=["formatos-institucionales"])

ROLES_EDITORES = ("director", "secretario", "secretaria_programa")
ROLES_TODOS = ("docente", *ROLES_EDITORES)

ETIQUETAS_TIPO = {
    "gestion_docente": "formato de gestión y autoevaluación docente",
    "acuerdo_pedagogico": "acuerdo pedagógico",
    "plan_actividades": "plan de actividades",
    "lista_asistencia": "lista de asistencia",
}


def _validar_tipo(tipo: str) -> None:
    if tipo not in TIPOS_FORMATO_INSTITUCIONAL:
        raise HTTPException(status_code=404, detail=f"Tipo de formato '{tipo}' no existe.")


def _programa_de(db: Session, usuario: Usuario) -> Programa:
    programa = db.get(Programa, usuario.programa_id)
    if programa is None:
        raise HTTPException(status_code=404, detail="Programa académico no encontrado.")
    return programa


def _out(programa: Programa) -> FormatoInstitucionalOut:
    return FormatoInstitucionalOut(
        programa_id=programa.id,
        gestion_docente_nombre_archivo=programa.gestion_docente_nombre_archivo,
        gestion_docente_tamano_bytes=programa.gestion_docente_tamano_bytes,
        acuerdo_pedagogico_nombre_archivo=programa.acuerdo_pedagogico_nombre_archivo,
        acuerdo_pedagogico_tamano_bytes=programa.acuerdo_pedagogico_tamano_bytes,
        plan_actividades_nombre_archivo=programa.plan_actividades_nombre_archivo,
        plan_actividades_tamano_bytes=programa.plan_actividades_tamano_bytes,
        lista_asistencia_nombre_archivo=programa.lista_asistencia_nombre_archivo,
        lista_asistencia_tamano_bytes=programa.lista_asistencia_tamano_bytes,
    )


@router.get("", response_model=FormatoInstitucionalOut)
def obtener(db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))):
    return _out(_programa_de(db, usuario))


@router.post("/{tipo}", response_model=FormatoInstitucionalOut)
def subir(
    tipo: str,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_EDITORES)),
):
    _validar_tipo(tipo)
    _programa_de(db, usuario)
    contenido = archivo.file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    try:
        ruta_relativa, tamano = guardar_archivo_institucional(
            usuario.programa_id, tipo, archivo.filename or "archivo", contenido
        )
    except ArchivoInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    programa = adjuntar_formato_institucional(
        db, usuario.programa_id, tipo, archivo.filename or "archivo", ruta_relativa, tamano
    )
    return _out(programa)


@router.delete("/{tipo}")
def borrar(
    tipo: str, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_EDITORES))
):
    _validar_tipo(tipo)
    _programa_de(db, usuario)
    if not quitar_formato_institucional(db, usuario.programa_id, tipo):
        raise HTTPException(status_code=404, detail=f"No hay {ETIQUETAS_TIPO[tipo]} cargado.")
    return {"ok": True}


@router.get("/{tipo}/descargar")
def descargar(
    tipo: str, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))
):
    _validar_tipo(tipo)
    programa = _programa_de(db, usuario)
    ruta_archivo = getattr(programa, f"{tipo}_ruta_archivo")
    nombre_archivo = getattr(programa, f"{tipo}_nombre_archivo")
    if not ruta_archivo:
        raise HTTPException(status_code=404, detail="No hay archivo cargado.")
    ruta = ruta_absoluta_segura(ruta_archivo)
    if ruta is None:
        raise HTTPException(status_code=404, detail="El archivo ya no existe en el servidor.")
    media_type, disposicion = tipo_y_disposicion(nombre_archivo or ruta.name)
    nombre_header = nombre_seguro_para_header(nombre_archivo or ruta.name)
    buffer = io.BytesIO(ruta.read_bytes())
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'{disposicion}; filename="{nombre_header}"'},
    )
