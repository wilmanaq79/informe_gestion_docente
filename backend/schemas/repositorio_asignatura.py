from datetime import datetime

from pydantic import BaseModel


class RepositorioAsignaturaOut(BaseModel):
    id: int
    asignatura: str
    docente_id: int | None
    docente_nombre: str | None
    silabo_nombre_archivo: str | None
    silabo_tamano_bytes: int | None
    programa_nombre_archivo: str | None
    programa_tamano_bytes: int | None
    creado_en: datetime
    actualizado_en: datetime
    creado_por_nombre: str | None
    actualizado_por_nombre: str | None


class RepositorioAsignaturaCreate(BaseModel):
    asignatura: str
    docente_id: int | None = None


class RepositorioAsignaturaUpdate(BaseModel):
    asignatura: str | None = None
    docente_id: int | None = None
