"""Conexion a PostgreSQL (motor y sesion de SQLAlchemy).

La cadena de conexion se lee de la variable de entorno DATABASE_URL (ver
.env en la raiz del proyecto -- nunca se versiona, contiene credenciales).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://usuario:contrasena@localhost:5432/nombre_bd"
)
if "DATABASE_URL" not in os.environ:
    raise RuntimeError(
        "Falta DATABASE_URL. Copia .env.example a .env y completa tus credenciales reales."
    )

# Tamano del pool de conexiones por proceso (cada worker de uvicorn/gunicorn
# tiene su propio pool). Configurable por entorno para produccion -- ver la
# seccion "Escalamiento" del README para la cuenta de conexiones totales
# (workers x (DB_POOL_SIZE + DB_MAX_OVERFLOW)) contra el max_connections de
# PostgreSQL.
DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", 10))
DB_MAX_OVERFLOW = int(os.environ.get("DB_MAX_OVERFLOW", 10))

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_recycle=1800,  # recicla conexiones inactivas antes de que el servidor/firewall las cierre
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session():
    return SessionLocal()
