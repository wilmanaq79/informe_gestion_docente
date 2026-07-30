# -*- coding: utf-8 -*-
"""Migracion correctiva: los formatos institucionales (gestion y
autoevaluacion docente, acuerdo pedagogico, plan de actividades, lista
de asistencia) no son por MATERIA -- son un unico juego de archivos por
PROGRAMA ACADEMICO completo. scripts/migrar_formatos_repositorio.py
habia agregado los primeros 3 por error a repositorio_asignaturas (una
fila por materia); esta migracion los mueve/agrega a programas
(incluida lista_asistencia, nueva) y elimina las columnas equivocadas
de repositorio_asignaturas. Idempotente.

Uso:
    python -m scripts.migrar_formatos_institucionales_programa
"""
from sqlalchemy import text

from db.database import engine

_TIPOS = ("gestion_docente", "acuerdo_pedagogico", "plan_actividades", "lista_asistencia")
_TIPOS_A_LIMPIAR_DE_REPOSITORIO = ("gestion_docente", "acuerdo_pedagogico", "plan_actividades")


def migrar():
    with engine.begin() as conn:
        for tipo in _TIPOS:
            conn.execute(
                text(f"ALTER TABLE programas ADD COLUMN IF NOT EXISTS {tipo}_nombre_archivo VARCHAR(255)")
            )
            conn.execute(
                text(f"ALTER TABLE programas ADD COLUMN IF NOT EXISTS {tipo}_ruta_archivo VARCHAR(500)")
            )
            conn.execute(
                text(f"ALTER TABLE programas ADD COLUMN IF NOT EXISTS {tipo}_tamano_bytes INTEGER")
            )
        for tipo in _TIPOS_A_LIMPIAR_DE_REPOSITORIO:
            conn.execute(text(f"ALTER TABLE repositorio_asignaturas DROP COLUMN IF EXISTS {tipo}_nombre_archivo"))
            conn.execute(text(f"ALTER TABLE repositorio_asignaturas DROP COLUMN IF EXISTS {tipo}_ruta_archivo"))
            conn.execute(text(f"ALTER TABLE repositorio_asignaturas DROP COLUMN IF EXISTS {tipo}_tamano_bytes"))
    print("Listo: formatos institucionales en 'programas' (incluida lista_asistencia); columnas equivocadas en 'repositorio_asignaturas' eliminadas.")


if __name__ == "__main__":
    migrar()
