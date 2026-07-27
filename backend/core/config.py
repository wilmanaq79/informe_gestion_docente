"""Configuracion de la API, leida de las variables de entorno (.env en la
raiz del proyecto -- compartido con la app Streamlit)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(RAIZ / ".env"), extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://usuario:contrasena@localhost:5432/nombre_bd"
    JWT_SECRET_KEY: str = "cambia-esta-clave-por-una-generada-con-secrets.token_hex(32)"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    PERIODO_ACTUAL: str = "2026-1"

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",  # servidor de desarrollo de Vite (React)
        "http://127.0.0.1:5173",
    ]


settings = Settings()
