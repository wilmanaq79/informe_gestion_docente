"""Endpoints del flujo de carga y procesamiento de notas (rol docente)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.api.deps import get_db, requiere_roles
from backend.schemas.informe import (
    AsistenciaPreviewOut,
    PdfPreviewOut,
    ProcesarResponseOut,
)
from backend.services import informe_service
from db.models import Usuario
from db.repository import eliminar_informe_corte

router = APIRouter(prefix="/api/informes", tags=["informes"])


@router.post("/materias-excel", response_model=list[str])
def materias_de_plantilla(
    excel: UploadFile = File(...),
    usuario: Usuario = Depends(requiere_roles("docente", "director", "secretario")),
):
    try:
        return informe_service.listar_materias_excel(excel.file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer la plantilla: {exc}")


@router.post("/pdf-preview", response_model=PdfPreviewOut)
def previsualizar_pdf(
    pdf: UploadFile = File(...),
    corte: int = Form(...),
    usuario: Usuario = Depends(requiere_roles("docente")),
):
    try:
        return informe_service.previsualizar_pdf(pdf.file, corte)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el PDF: {exc}")


@router.post("/asistencia-preview", response_model=AsistenciaPreviewOut)
def previsualizar_asistencia(
    asistencia: UploadFile = File(...),
    usuario: Usuario = Depends(requiere_roles("docente")),
):
    try:
        return informe_service.previsualizar_asistencia(asistencia.file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer la planilla de asistencia: {exc}")


@router.post("/procesar", response_model=ProcesarResponseOut)
def procesar(
    corte: int = Form(...),
    excel: UploadFile = File(...),
    pdfs: list[UploadFile] = File(...),
    materias: list[str] = Form(...),
    asistencias_regular: list[str] = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles("docente")),
):
    if not (len(pdfs) == len(materias) == len(asistencias_regular)):
        raise HTTPException(
            status_code=400,
            detail="pdfs, materias y asistencias_regular deben tener la misma cantidad de elementos "
            "(uno por cada PDF cargado, usa '' cuando no haya asistencia para esa materia).",
        )

    items = []
    for pdf, materia, asistencia_txt in zip(pdfs, materias, asistencias_regular):
        asistencia_regular = int(asistencia_txt) if asistencia_txt.strip() != "" else None
        items.append({"pdf_stream": pdf.file, "materia": materia, "asistencia_regular": asistencia_regular})

    try:
        resultado = informe_service.procesar_materias(db, usuario.id, excel.file, corte, items)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error procesando las materias: {exc}")

    return resultado


@router.delete("/{informe_id}", status_code=204)
def borrar_informe(
    informe_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(requiere_roles("director")),
):
    """Borra un informe de corte ya guardado. Restringido SOLO al rol
    'director' (ni el docente ni el secretario pueden borrar), para que un
    error de un docente en pleno proceso no le bloquee su propio trabajo ni
    el de los demas -- solo el director puede limpiar datos de prueba o
    corregir un informe mal cargado."""
    if not eliminar_informe_corte(db, informe_id):
        raise HTTPException(status_code=404, detail="Informe no encontrado")
