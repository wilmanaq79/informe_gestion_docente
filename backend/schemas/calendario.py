from datetime import date

from pydantic import BaseModel


class EventoCalendarioOut(BaseModel):
    id: int
    periodo_id: int
    actividad: str
    fecha_inicio: date
    fecha_fin: date | None
    orden: int


class EventoCalendarioCreate(BaseModel):
    periodo_id: int
    actividad: str
    fecha_inicio: date
    fecha_fin: date | None = None
    orden: int = 0


class EventoCalendarioUpdate(BaseModel):
    actividad: str | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    orden: int | None = None
