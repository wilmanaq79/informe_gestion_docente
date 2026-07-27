from pydantic import BaseModel


class KpisInstitucionalesOut(BaseModel):
    total_docentes: int
    total_materias: int
    total_matriculados: int
    total_evaluados: int
    total_aprobaron: int
    promedio_general: float
    pct_aprobacion_general: float


class MateriaDashboardOut(BaseModel):
    materia: str
    docente: str
    grupo: str | None
    corte_numero: int
    corte_nombre: str
    matriculados: int
    evaluados: int
    aprobaron: int
    promedio: float
    desviacion: float


class CorteDashboardOut(BaseModel):
    corte_numero: int
    matriculados: int
    evaluados: int
    aprobaron: int
    promedio: float
    pct_aprobacion: float


class DocenteDashboardOut(BaseModel):
    docente: str
    matriculados: int
    evaluados: int
    aprobaron: int
    promedio: float
    pct_aprobacion: float


class DashboardOut(BaseModel):
    kpis: KpisInstitucionalesOut
    por_materia: list[MateriaDashboardOut]
    por_corte: list[CorteDashboardOut]
    por_docente: list[DocenteDashboardOut]
    conteo_estado_actual: dict[str, int]
