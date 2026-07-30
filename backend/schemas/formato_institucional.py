from pydantic import BaseModel


class FormatoInstitucionalOut(BaseModel):
    """Los 4 formatos institucionales (gestión y autoevaluación
    docente, acuerdo pedagógico, plan de actividades, lista de
    asistencia) son un único juego de archivos por PROGRAMA ACADÉMICO
    completo -- a diferencia del sílabo/programa de asignatura de
    RepositorioAsignaturaOut, que son por materia."""

    programa_id: int
    gestion_docente_nombre_archivo: str | None
    gestion_docente_tamano_bytes: int | None
    acuerdo_pedagogico_nombre_archivo: str | None
    acuerdo_pedagogico_tamano_bytes: int | None
    plan_actividades_nombre_archivo: str | None
    plan_actividades_tamano_bytes: int | None
    lista_asistencia_nombre_archivo: str | None
    lista_asistencia_tamano_bytes: int | None
