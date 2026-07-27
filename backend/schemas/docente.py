from pydantic import BaseModel


class InformeCorteOut(BaseModel):
    id: int
    corte_numero: int
    corte_nombre: str
    matriculados: int
    asistencia_regular: int | None
    evaluados: int
    aprobaron: int
    es_estimado: bool
    promedio: float | None
    mediana: float | None
    desviacion: float | None


class AsignacionOut(BaseModel):
    id: int
    asignatura: str
    grupo: str | None
    programa: str | None
    informes: list[InformeCorteOut]


class DocenteResumenOut(BaseModel):
    id: int
    nombre_completo: str
    materias_periodo: int
    informes_cargados: int
    ultimo_corte: int | None


class DocenteDetalleOut(BaseModel):
    id: int
    nombre_completo: str
    cedula: str | None
    email: str | None
    asignaciones: list[AsignacionOut]
