# -*- coding: utf-8 -*-
"""Migracion puntual: crea la tabla 'repositorio_asignaturas' (silabos y
programas de asignatura). Nueva -- Base.metadata.create_all ya la crea
sola porque no requiere ALTER. Idempotente.

Uso:
    python -m scripts.migrar_repositorio_asignaturas
"""
from db.database import engine
from db.models import Base


def migrar():
    Base.metadata.create_all(engine)
    print("Listo: tabla 'repositorio_asignaturas' disponible.")


if __name__ == "__main__":
    migrar()
