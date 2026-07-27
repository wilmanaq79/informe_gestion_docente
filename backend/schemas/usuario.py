from pydantic import BaseModel


class UsuarioCreate(BaseModel):
    nombre_completo: str
    cedula: str | None = None
    email: str | None = None
    username: str
    password: str
    rol: str  # 'docente' | 'director' | 'secretario' | 'secretaria_programa'


class UsuarioOut(BaseModel):
    id: int
    nombre_completo: str
    cedula: str | None = None
    email: str | None = None
    username: str
    rol: str
    activo: bool
