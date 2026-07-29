"""Calendario académico oficial (Inicio de clases, parciales, límites de
reporte de notas por corte, etc.) de un periodo. Docentes y Secretaria
del Programa solo lo consultan; el Director y el Secretario Académico
lo crean/editan/borran."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_db, requiere_roles
from backend.schemas.calendario import EventoCalendarioCreate, EventoCalendarioOut, EventoCalendarioUpdate
from db.repository import (
    actualizar_evento_calendario,
    crear_evento_calendario,
    eliminar_evento_calendario,
    listar_eventos_calendario,
)

router = APIRouter(prefix="/api/calendario", tags=["calendario"])


def _out(e) -> EventoCalendarioOut:
    return EventoCalendarioOut(
        id=e.id, periodo_id=e.periodo_id, actividad=e.actividad,
        fecha_inicio=e.fecha_inicio, fecha_fin=e.fecha_fin, orden=e.orden,
    )


@router.get("", response_model=list[EventoCalendarioOut])
def listar(
    periodo_id: int = Query(..., description="Id del PeriodoAcademico (ver /api/periodos)."),
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("docente", "director", "secretario", "secretaria_programa")),
):
    return [_out(e) for e in listar_eventos_calendario(db, periodo_id)]


@router.post("", response_model=EventoCalendarioOut)
def crear(
    datos: EventoCalendarioCreate,
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    evento = crear_evento_calendario(
        db, datos.periodo_id, datos.actividad, datos.fecha_inicio, datos.fecha_fin, datos.orden
    )
    return _out(evento)


@router.put("/{evento_id}", response_model=EventoCalendarioOut)
def actualizar(
    evento_id: int,
    datos: EventoCalendarioUpdate,
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    campos = {k: v for k, v in datos.model_dump().items() if v is not None}
    evento = actualizar_evento_calendario(db, evento_id, **campos)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return _out(evento)


@router.delete("/{evento_id}")
def eliminar(
    evento_id: int,
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    if not eliminar_evento_calendario(db, evento_id):
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return {"ok": True}
