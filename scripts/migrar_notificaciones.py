# -*- coding: utf-8 -*-
"""Migracion puntual: crea la tabla 'notificaciones' (nueva --
Base.metadata.create_all ya la crea sola porque es tabla nueva, no
requiere ALTER). Idempotente.

Uso:
    python -m scripts.migrar_notificaciones
"""
from db.database import engine
from db.models import Base


def migrar():
    Base.metadata.create_all(engine)
    print("Listo: tabla 'notificaciones' disponible.")


if __name__ == "__main__":
    migrar()
