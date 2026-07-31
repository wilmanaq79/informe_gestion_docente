# -*- coding: utf-8 -*-
"""Agrega tarea_id (nullable) a la tabla notificaciones ya existente, para
que el modulo de tareas reutilice el mismo sistema de notificaciones
in-app (campanita) ya usado por entregas, en vez de crear uno paralelo.
Ver docs/especificacionModuloTareas.md, seccion 22. Idempotente.

Uso:
    python -m scripts.migrar_notificaciones_tarea
"""
from sqlalchemy import text

from db.database import engine


def migrar():
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS tarea_id INTEGER "
            "REFERENCES tareas(id) ON DELETE SET NULL"
        ))
    print("Listo: columna tarea_id agregada a notificaciones.")


if __name__ == "__main__":
    migrar()
