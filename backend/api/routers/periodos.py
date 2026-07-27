"""Catalogo de periodos academicos (Año + Semestre), para poblar los
selectores de Año/Semestre/Corte del Director y el Secretario Academico
en los informes y el dashboard consolidados.

Tambien expone la creacion de un nuevo periodo (p.ej. dar de alta
'2026-2' antes de que empiece) y su activacion como el periodo 'actual'
donde caen las nuevas cargas de notas de los docentes -- ambas acciones
restringidas a Director y Secretario Academico."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db, requiere_roles
from backend.schemas.periodo import PeriodoCreate, PeriodoOut
from db.repository import activar_periodo, crear_o_obtener_periodo, listar_periodos

router = APIRouter(prefix="/api/periodos", tags=["periodos"])


def _out(p) -> PeriodoOut:
    return PeriodoOut(id=p.id, nombre=p.nombre, anio=p.anio, semestre=p.semestre, activo=p.activo)


@router.get("", response_model=list[PeriodoOut])
def listar(
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("docente", "director", "secretario", "secretaria_programa")),
):
    return [_out(p) for p in listar_periodos(db)]


@router.post("", response_model=PeriodoOut)
def crear(
    datos: PeriodoCreate,
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    periodo = crear_o_obtener_periodo(db, datos.anio, datos.semestre)
    return _out(periodo)


@router.post("/{periodo_id}/activar", response_model=PeriodoOut)
def activar(
    periodo_id: int,
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    try:
        periodo = activar_periodo(db, periodo_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(periodo)
