"""Generacion de los informes PDF (individual y consolidado), filtrables
por Año, Semestre (opcional, si se omite incluye ambos semestres del Año)
y Corte (opcional, si se omite usa el corte mas reciente de cada
materia). La fecha de generacion que se ve en el PDF es la del reloj del
sistema al momento de generarlo."""
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agente_notas.reporte_pdf import describir_alcance, generar_reporte_consolidado, generar_reporte_docente
from backend.api.deps import get_db, requiere_roles
from db.repository import (
    listar_docentes,
    periodo_activo,
    periodo_mas_reciente,
    resolver_periodo_ids,
    resumen_dashboard_institucional,
)

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


def _resolver_alcance(db: Session, anio: int | None, semestre: int | None):
    if anio is None:
        p = periodo_activo(db) or periodo_mas_reciente(db)
        anio = p.anio if p else 0
    periodo_ids = resolver_periodo_ids(db, anio, semestre)
    return anio, periodo_ids


@router.get("/docente/{docente_id}")
def reporte_docente(
    docente_id: int,
    anio: int | None = Query(None, description="Año academico. Si se omite, usa el año del periodo actual."),
    semestre: int | None = Query(None, ge=1, le=2, description="1 o 2. Si se omite, incluye ambos semestres del año."),
    corte: int | None = Query(None, ge=1, le=3, description="1, 2 o 3. Si se omite, muestra el historial completo de cortes."),
    db: Session = Depends(get_db),
    usuario=Depends(requiere_roles("director", "secretario")),
):
    docentes = listar_docentes(db, usuario.programa_id)
    docente = next((d for d in docentes if d.id == docente_id), None)
    if docente is None:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    anio, periodo_ids = _resolver_alcance(db, anio, semestre)
    etiqueta = describir_alcance(anio, semestre, corte)

    buffer = io.BytesIO()
    generar_reporte_docente(docente, buffer, etiqueta, periodo_ids=periodo_ids, corte_filtro=corte)
    buffer.seek(0)

    filename = f"Informe_{docente.nombre_completo.replace(' ', '_')}_{anio}" + (f"-{semestre}" if semestre else "") + ".pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/consolidado")
def reporte_consolidado(
    anio: int | None = Query(None, description="Año academico. Si se omite, usa el año del periodo actual."),
    semestre: int | None = Query(None, ge=1, le=2, description="1 o 2. Si se omite, incluye ambos semestres del año."),
    corte: int | None = Query(None, ge=1, le=3, description="1, 2 o 3. Si se omite, usa el corte mas reciente de cada materia."),
    db: Session = Depends(get_db),
    usuario=Depends(requiere_roles("director")),
):
    """Un solo PDF con el informe de TODOS los docentes DE TU PROGRAMA.
    Restringido solo al rol 'director' (el secretario no tiene este
    boton)."""
    docentes = listar_docentes(db, usuario.programa_id)
    if not docentes:
        raise HTTPException(status_code=404, detail="No hay docentes registrados todavía.")

    anio, periodo_ids = _resolver_alcance(db, anio, semestre)
    etiqueta = describir_alcance(anio, semestre, corte)
    resumen = resumen_dashboard_institucional(db, usuario.programa_id, anio, semestre, corte)

    buffer = io.BytesIO()
    generar_reporte_consolidado(
        docentes, buffer, etiqueta, periodo_ids=periodo_ids, corte_filtro=corte, resumen_dashboard=resumen
    )
    buffer.seek(0)

    filename = f"Informe_consolidado_{anio}" + (f"-{semestre}" if semestre else "") + (f"_corte{corte}" if corte else "") + ".pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
