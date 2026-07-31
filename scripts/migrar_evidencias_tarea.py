# -*- coding: utf-8 -*-
"""Crea la tabla evidencias_tarea (archivos de soporte subidos para una
tarea con requiere_evidencia=True). Ver docs/especificacionModuloTareas.md,
seccion 8. Idempotente.

Uso:
    python -m scripts.migrar_evidencias_tarea
"""
from sqlalchemy import text

from db.database import engine


def migrar():
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS evidencias_tarea (
                id SERIAL PRIMARY KEY,
                tarea_id INTEGER NOT NULL REFERENCES tareas(id) ON DELETE CASCADE,
                nombre_archivo VARCHAR(255) NOT NULL,
                ruta_archivo VARCHAR(500) NOT NULL,
                tamano_bytes INTEGER NOT NULL,
                subido_por_id INTEGER REFERENCES usuarios(id),
                subido_en TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_evidencias_tarea_tarea_id ON evidencias_tarea (tarea_id)"
        ))
    print("Listo: tabla evidencias_tarea creada.")


if __name__ == "__main__":
    migrar()
