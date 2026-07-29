# -*- coding: utf-8 -*-
"""Migracion puntual: agrega el flag 'debe_cambiar_password' a usuarios
(para forzar el cambio de contrasena temporal en cuentas nuevas) y crea
la tabla de tokens de recuperacion de contrasena por correo. Idempotente.

Uso:
    python -m scripts.migrar_password_recuperacion
"""
from sqlalchemy import text

from db.database import engine


def migrar():
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
                "debe_cambiar_password BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS tokens_recuperacion_password (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    creado_en TIMESTAMP NOT NULL DEFAULT now(),
                    expira_en TIMESTAMP NOT NULL,
                    usado_en TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tokens_recuperacion_usuario_id "
                "ON tokens_recuperacion_password (usuario_id)"
            )
        )
    print("Listo: columna debe_cambiar_password y tabla tokens_recuperacion_password creadas.")


if __name__ == "__main__":
    migrar()
