from pydantic import BaseModel


class EstudianteNotaOut(BaseModel):
    nombre: str
    documento: str | None = None
    corte1: float | None = None
    corte2: float | None = None
    corte3: float | None = None
    def_pond: float
    nota_necesaria: float | None = None
    estado: str


class PdfPreviewOut(BaseModel):
    materia_detectada: str | None
    grupo: str | None
    n_estudiantes: int
    progreso: list[EstudianteNotaOut]
    conteo_estado: dict[str, int]


class AsistenciaPreviewOut(BaseModel):
    matriculados_asistencia: int
    asistencia_regular: int


class NotaSimpleOut(BaseModel):
    nombre: str
    nota: float


class ResumenMateriaOut(BaseModel):
    materia: str
    grupo: str | None
    matriculados: int
    asistencia_regular: int | None
    evaluados: int
    aprobaron: int
    es_estimado: bool
    promedio: float
    mediana: float
    desviacion: float
    mejor_nombre: str
    mejor_nota: float
    coef_variacion: float
    interpretacion: str
    notas: list[NotaSimpleOut]
    conteo_estado: dict[str, int]


class ProcesarResponseOut(BaseModel):
    resultados: list[ResumenMateriaOut]
    interpretacion_general: str
    excel_base64: str
    excel_filename: str
