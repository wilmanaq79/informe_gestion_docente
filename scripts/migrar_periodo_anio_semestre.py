"""Migracion puntual: agrega las columnas 'anio' y 'semestre' a
periodos_academicos (antes solo tenia 'nombre', p.ej. '2026-1') y las
llena a partir del nombre de cada periodo ya existente.

db/seed.py usa Base.metadata.create_all(), que NO altera tablas que ya
existen -- por eso este script hace el ALTER TABLE manualmente. Es
idempotente: se puede correr varias veces sin duplicar nada.

Uso:
    python -m scripts.migrar_periodo_anio_semestre
"""
from sqlalchemy import text

from db.database import engine
from db.repository import parsear_periodo


def migrar():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE periodos_academicos ADD COLUMN IF NOT EXISTS anio INTEGER"))
        conn.execute(text("ALTER TABLE periodos_academicos ADD COLUMN IF NOT EXISTS semestre INTEGER"))

        filas = conn.execute(text("SELECT id, nombre FROM periodos_academicos WHERE anio IS NULL")).fetchall()
        for fila in filas:
            anio, semestre = parsear_periodo(fila.nombre)
            conn.execute(
                text("UPDATE periodos_academicos SET anio = :anio, semestre = :semestre WHERE id = :id"),
                {"anio": anio, "semestre": semestre, "id": fila.id},
            )
            print(f"  Periodo '{fila.nombre}' (id={fila.id}) -> anio={anio}, semestre={semestre}")

        conn.execute(text("ALTER TABLE periodos_academicos ALTER COLUMN anio SET NOT NULL"))
        conn.execute(text("ALTER TABLE periodos_academicos ALTER COLUMN semestre SET NOT NULL"))

        existe_constraint = conn.execute(
            text(
                "SELECT 1 FROM pg_constraint WHERE conname = 'uq_periodo_anio_semestre'"
            )
        ).first()
        if existe_constraint is None:
            conn.execute(
                text(
                    "ALTER TABLE periodos_academicos "
                    "ADD CONSTRAINT uq_periodo_anio_semestre UNIQUE (anio, semestre)"
                )
            )

    print("Listo: periodos_academicos ahora tiene anio/semestre.")


if __name__ == "__main__":
    migrar()
