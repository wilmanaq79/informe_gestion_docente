# -*- coding: utf-8 -*-
"""Migracion puntual: agrega al repositorio de asignaturas 3 formatos
institucionales nuevos (ademas del silabo y el programa de asignatura
que ya existian) -- gestion y autoevaluacion docente (.xlsx), acuerdo
pedagogico (.doc/.docx) y plan de actividades (.doc/.docx). Mismo
permiso que el silabo: solo Director/Secretario/Secretaria los cargan,
cualquier rol los consulta. Idempotente.

Uso:
    python -m scripts.migrar_formatos_repositorio
"""
from sqlalchemy import text

from db.database import engine

_TIPOS = ("gestion_docente", "acuerdo_pedagogico", "plan_actividades")


def migrar():
    with engine.begin() as conn:
        for tipo in _TIPOS:
            conn.execute(
                text(
                    f"ALTER TABLE repositorio_asignaturas ADD COLUMN IF NOT EXISTS "
                    f"{tipo}_nombre_archivo VARCHAR(255)"
                )
            )
            conn.execute(
                text(
                    f"ALTER TABLE repositorio_asignaturas ADD COLUMN IF NOT EXISTS "
                    f"{tipo}_ruta_archivo VARCHAR(500)"
                )
            )
            conn.execute(
                text(
                    f"ALTER TABLE repositorio_asignaturas ADD COLUMN IF NOT EXISTS "
                    f"{tipo}_tamano_bytes INTEGER"
                )
            )
    print("Listo: columnas de gestion_docente, acuerdo_pedagogico y plan_actividades creadas.")


if __name__ == "__main__":
    migrar()
