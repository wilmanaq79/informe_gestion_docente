"""Dashboard institucional para el Director del Programa y el Secretario
Academico: como van evolucionando los estudiantes y las asignaturas de todo
el programa, para apoyar decisiones y estrategias de mejora."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_db, requiere_roles
from backend.core.config import settings
from backend.schemas.dashboard import DashboardOut
from db.repository import resumen_dashboard_institucional

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    return resumen_dashboard_institucional(db, settings.PERIODO_ACTUAL)
