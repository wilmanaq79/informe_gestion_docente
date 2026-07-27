"""Dashboard institucional para el Director del Programa y el Secretario
Academico: como van evolucionando los estudiantes y las asignaturas de todo
el programa, para apoyar decisiones y estrategias de mejora.

Filtrable por Año, Semestre (opcional; si no se indica, agrega los dos
semestres del Año) y Corte (opcional; si no se indica, usa el corte mas
reciente cargado de cada asignatura)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_db, requiere_roles
from backend.schemas.dashboard import DashboardOut
from db.repository import periodo_activo, periodo_mas_reciente, resumen_dashboard_institucional

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(
    anio: int | None = Query(None, description="Año academico. Si se omite, usa el año del periodo activo."),
    semestre: int | None = Query(None, ge=1, le=2, description="1 o 2. Si se omite, agrega ambos semestres del año."),
    corte: int | None = Query(None, ge=1, le=3, description="1, 2 o 3. Si se omite, usa el corte mas reciente."),
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    if anio is None:
        p = periodo_activo(db) or periodo_mas_reciente(db)
        anio = p.anio if p else None
    if anio is None:
        return resumen_dashboard_institucional(db, 0)  # sin periodos registrados todavia -> vacio
    return resumen_dashboard_institucional(db, anio, semestre, corte)
