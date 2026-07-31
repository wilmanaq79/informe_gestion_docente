from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field


class CategoriaTareaOut(BaseModel):
    id: int
    nombre: str
    activa: bool


class CategoriaTareaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)


class PrioridadTareaOut(BaseModel):
    id: int
    nombre: str
    icono: str
    color: str
    orden: int
    nivel: int


class EstadoTareaOut(BaseModel):
    id: int
    nombre: str
    icono: str
    color: str
    orden: int


class ResponsableSecundarioOut(BaseModel):
    usuario_id: int
    nombre_completo: str


class TareaOut(BaseModel):
    id: int
    codigo: str
    titulo: str
    descripcion: str | None
    objetivo: str | None
    resultado_esperado: str | None
    tipo: str
    categoria_id: int | None
    categoria_nombre: str | None
    prioridad_id: int
    prioridad_nombre: str
    estado_id: int
    estado_nombre: str
    estado_icono: str
    programa_id: int
    periodo_id: int | None
    periodo_nombre: str | None
    responsable_principal_id: int | None
    responsable_principal_nombre: str | None
    responsables_secundarios: list[ResponsableSecundarioOut]
    creado_por_id: int | None
    creado_por_nombre: str | None
    asignado_por_id: int | None
    asignado_por_nombre: str | None
    fecha_inicio: date | None
    fecha_limite: date | None
    hora_limite: time | None
    fecha_fin_real: datetime | None
    porcentaje_avance: int
    confidencialidad: str
    requiere_evidencia: bool
    requiere_aprobacion: bool
    permite_ampliacion: bool
    motivo_cancelacion: str | None
    justificacion_retraso: str | None
    creado_en: datetime
    actualizado_en: datetime


class TareaCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    descripcion: str | None = None
    objetivo: str | None = None
    resultado_esperado: str | None = None
    tipo: Literal["institucional", "personal"] = "institucional"
    categoria_id: int | None = None
    prioridad_id: int
    periodo_id: int | None = None
    fecha_inicio: date | None = None
    fecha_limite: date | None = None
    hora_limite: time | None = None
    confidencialidad: Literal["normal", "confidencial"] = "normal"
    requiere_evidencia: bool = False
    requiere_aprobacion: bool = True
    permite_ampliacion: bool = True


class TareaUpdate(BaseModel):
    titulo: str | None = None
    descripcion: str | None = None
    objetivo: str | None = None
    resultado_esperado: str | None = None
    categoria_id: int | None = None
    prioridad_id: int | None = None
    fecha_inicio: date | None = None
    fecha_limite: date | None = None
    hora_limite: time | None = None
    confidencialidad: Literal["normal", "confidencial"] | None = None
    requiere_evidencia: bool | None = None
    requiere_aprobacion: bool | None = None
    permite_ampliacion: bool | None = None


class AsignarTareaIn(BaseModel):
    responsable_principal_id: int
    responsables_secundarios_ids: list[int] | None = None


class CancelarTareaIn(BaseModel):
    motivo: str = Field(min_length=1, max_length=500)


class DevolverTareaIn(BaseModel):
    motivo: str = Field(min_length=1, max_length=500)


class ReactivarTareaIn(BaseModel):
    nueva_fecha_limite: date


class EvidenciaTareaOut(BaseModel):
    id: int
    nombre_archivo: str
    tamano_bytes: int
    subido_por_id: int | None
    subido_por_nombre: str | None
    subido_en: datetime


class TareaProximaVencerOut(BaseModel):
    id: int
    codigo: str
    titulo: str
    fecha_limite: date
    dias_restantes: int
    responsable_principal_nombre: str | None


class IndicadoresTareasOut(BaseModel):
    """KPIs calculados al vuelo sobre las tareas visibles para quien
    consulta (ver db.repository.indicadores_tareas) -- no hay una tabla
    de indicadores persistida en esta fase."""

    total: int
    por_estado: dict[str, int]
    vencidas: int
    proximas_a_vencer: int
    proximas_a_vencer_detalle: list[TareaProximaVencerOut]
    cumplimiento_pct: float
