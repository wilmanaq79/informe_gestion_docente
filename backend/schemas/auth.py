from pydantic import BaseModel, field_validator

from db.auth import validar_longitud_password


class LoginRequest(BaseModel):
    username: str
    password: str


class UsuarioOut(BaseModel):
    id: int
    nombre_completo: str
    username: str
    rol: str
    activo: bool
    acepto_tratamiento_datos: bool
    debe_cambiar_password: bool
    programa_id: int | None
    programa_nombre: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str

    @field_validator("password_nueva")
    @classmethod
    def _validar_password_nueva(cls, v: str) -> str:
        validar_longitud_password(v)
        return v


class SolicitarRecuperacionRequest(BaseModel):
    username: str


class RestablecerPasswordRequest(BaseModel):
    token: str
    password_nueva: str

    @field_validator("password_nueva")
    @classmethod
    def _validar_password_nueva(cls, v: str) -> str:
        validar_longitud_password(v)
        return v


class MensajeGenericoOut(BaseModel):
    mensaje: str
