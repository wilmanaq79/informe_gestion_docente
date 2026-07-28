# -*- coding: utf-8 -*-
"""Migracion puntual: agrega a 'usuarios' las columnas necesarias para
registrar la aceptacion del Aviso de Privacidad y Autorizacion para el
Tratamiento de Datos Personales (Ley 1581 de 2012).

Idempotente: se puede correr varias veces sin duplicar nada.

Uso:
    python -m scripts.migrar_consentimiento_datos
"""
from sqlalchemy import text

from db.database import engine


def migrar():
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
                "acepto_tratamiento_datos BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        conn.execute(
            text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_aceptacion_tratamiento TIMESTAMP")
        )
        conn.execute(
            text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS version_politica_aceptada VARCHAR(20)")
        )
    print("Listo: usuarios ahora registra la aceptacion del tratamiento de datos.")


if __name__ == "__main__":
    migrar()
