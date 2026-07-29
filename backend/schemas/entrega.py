from datetime import datetime

from pydantic import BaseModel


class DocumentoEntregaOut(BaseModel):
    id: int
    tipo_documento: str
    descripcion_otro: str | None
    materia: str | None
    nombre_archivo: str
    tamano_bytes: int
    subido_en: datetime
    firma_detectada: bool | None
    firma_confianza: str | None
    firma_detalle: str | None


class EntregaOut(BaseModel):
    id: int
    docente_id: int
    docente_nombre: str
    periodo_id: int
    periodo_nombre: str
    corte_id: int
    corte_numero: int
    corte_nombre: str
    estado: str
    documentos_firmados_confirmado: bool
    comentario_revision: str | None
    revisado_por_nombre: str | None
    revisado_en: datetime | None
    notificacion_enviada: bool
    notificacion_error: str | None
    creado_en: datetime
    actualizado_en: datetime
    todos_firmados_agente: bool
    documentos: list[DocumentoEntregaOut]


class RechazarEntregaIn(BaseModel):
    comentario: str


class AprobarEntregaIn(BaseModel):
    comentario: str | None = None
