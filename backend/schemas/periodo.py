from pydantic import BaseModel, Field


class PeriodoOut(BaseModel):
    id: int
    nombre: str
    anio: int
    semestre: int
    activo: bool


class PeriodoCreate(BaseModel):
    anio: int = Field(ge=2000, le=2100)
    semestre: int = Field(ge=1, le=2)
