from pydantic import BaseModel, field_validator

from db.auth import validar_longitud_password


class UsuarioCreate(BaseModel):
    nombre_completo: str
    cedula: str
    email: str
    telefono: str | None = None
    username: str
    password: str
    rol: str  # 'docente' | 'director' | 'secretario' | 'secretaria_programa'

    @field_validator("password")
    @classmethod
    def _validar_password(cls, v: str) -> str:
        validar_longitud_password(v)
        return v


class UsuarioUpdate(BaseModel):
    """Edicion de un usuario ya existente -- solo los datos de perfil.
    username/password/rol quedan fuera de proposito: no se pidieron y
    cambiarlos requeriria reglas propias (unicidad, re-autenticacion)."""

    nombre_completo: str | None = None
    cedula: str | None = None
    email: str | None = None
    telefono: str | None = None


class UsuarioOut(BaseModel):
    id: int
    nombre_completo: str
    cedula: str | None = None
    email: str | None = None
    telefono: str | None = None
    username: str
    rol: str
    activo: bool
