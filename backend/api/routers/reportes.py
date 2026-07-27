"""Generacion del informe PDF consolidado de un docente."""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agente_notas.reporte_pdf import generar_reporte_consolidado, generar_reporte_docente
from backend.api.deps import get_db, requiere_roles
from backend.core.config import settings
from db.repository import listar_docentes, resumen_dashboard_institucional

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


@router.get("/docente/{docente_id}")
def reporte_docente(
    docente_id: int,
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    docentes = listar_docentes(db)
    docente = next((d for d in docentes if d.id == docente_id), None)
    if docente is None:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    buffer = io.BytesIO()
    generar_reporte_docente(docente, buffer, settings.PERIODO_ACTUAL)
    buffer.seek(0)

    filename = f"Informe_{docente.nombre_completo.replace(' ', '_')}_{settings.PERIODO_ACTUAL}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/consolidado")
def reporte_consolidado(
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director")),
):
    """Un solo PDF con el informe de TODOS los docentes. Restringido solo al
    rol 'director' (el secretario no tiene este boton)."""
    docentes = listar_docentes(db)
    if not docentes:
        raise HTTPException(status_code=404, detail="No hay docentes registrados todavía.")

    resumen = resumen_dashboard_institucional(db, settings.PERIODO_ACTUAL)

    buffer = io.BytesIO()
    generar_reporte_consolidado(docentes, buffer, settings.PERIODO_ACTUAL, resumen_dashboard=resumen)
    buffer.seek(0)

    filename = f"Informe_consolidado_{settings.PERIODO_ACTUAL}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
