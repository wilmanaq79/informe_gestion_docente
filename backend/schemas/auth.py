from pydantic import BaseModel


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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut
