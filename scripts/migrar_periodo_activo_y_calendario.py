"""Migracion puntual:
1) agrega la columna 'activo' a periodos_academicos (el periodo que el
   Director/Secretario marca como 'actual' para la carga de notas de los
   docentes), marcando activo=True al periodo mas reciente si ninguno lo
   esta todavia.
2) crea la tabla eventos_calendario (nueva -- Base.metadata.create_all ya
   la crea sola porque es tabla nueva, no requiere ALTER).

Idempotente: se puede correr varias veces sin duplicar nada.

Uso:
    python -m scripts.migrar_periodo_activo_y_calendario
"""
from sqlalchemy import text

from db.database import engine
from db.models import Base


def migrar():
    Base.metadata.create_all(engine)  # crea eventos_calendario si no existe

    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE periodos_academicos ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT FALSE")
        )
        hay_activo = conn.execute(
            text("SELECT 1 FROM periodos_academicos WHERE activo IS TRUE LIMIT 1")
        ).first()
        if hay_activo is None:
            conn.execute(
                text(
                    "UPDATE periodos_academicos SET activo = TRUE WHERE id = ("
                    "SELECT id FROM periodos_academicos ORDER BY anio DESC, semestre DESC LIMIT 1)"
                )
            )
            print("  Se marco como activo el periodo mas reciente (no habia ninguno activo todavia).")

    print("Listo: periodos_academicos.activo y eventos_calendario disponibles.")


if __name__ == "__main__":
    migrar()
