# -*- coding: utf-8 -*-
"""Migracion puntual: crea la tabla que respalda el limitador de
intentos de login (backend/core/rate_limit.py) en Postgres, para que el
limite sea correcto sin importar cuantos workers de uvicorn corran
(antes vivia en un diccionario en memoria por proceso). Idempotente.

Uso:
    python -m scripts.migrar_rate_limit
"""
from sqlalchemy import text

from db.database import engine


def migrar():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS intentos_login_fallidos (
                    clave VARCHAR(50) PRIMARY KEY,
                    intentos INTEGER NOT NULL DEFAULT 0,
                    primer_intento_en TIMESTAMP NOT NULL
                )
                """
            )
        )
    print("Listo: tabla intentos_login_fallidos creada.")


if __name__ == "__main__":
    migrar()
