# -*- coding: utf-8 -*-
"""Migracion puntual: agrega los indices que la auditoria de esquema/ACID
detecto faltantes -- indice unico parcial para garantizar "un solo
periodo activo" a nivel de base de datos (no solo por convencion en
db.repository.activar_periodo), e indices en 3 columnas de foreign key
de alto trafico que antes dependian de un sequential scan. Idempotente.

Uso:
    python -m scripts.migrar_indices_acid
"""
from sqlalchemy import text

from db.database import engine


def migrar():
    with engine.begin() as conn:
        # informes_corte.asignacion_id no tenia ON DELETE CASCADE en la BD,
        # inconsistente con lo que ya declara el ORM
        # (AsignacionAcademica.informes, cascade="all, delete-orphan").
        # Sin esto, borrar una asignacion por SQL directo (fuera del grafo
        # de sesion de SQLAlchemy) fallaria con una violacion de FK en vez
        # de cascadear como sugiere el modelo de datos.
        conn.execute(
            text(
                "ALTER TABLE informes_corte DROP CONSTRAINT IF EXISTS informes_corte_asignacion_id_fkey"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE informes_corte ADD CONSTRAINT informes_corte_asignacion_id_fkey "
                "FOREIGN KEY (asignacion_id) REFERENCES asignaciones_academicas(id) ON DELETE CASCADE"
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_un_solo_periodo_activo "
                "ON periodos_academicos (activo) WHERE activo"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_notas_estudiantes_informe_corte_id "
                "ON notas_estudiantes (informe_corte_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_documentos_entrega_entrega_id "
                "ON documentos_entrega (entrega_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_notificaciones_usuario_id "
                "ON notificaciones (usuario_id)"
            )
        )
    print("Listo: indice unico parcial de periodo activo + 3 indices de FK creados.")


if __name__ == "__main__":
    migrar()
