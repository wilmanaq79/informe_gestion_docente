# -*- coding: utf-8 -*-
"""Migracion puntual:
1) agrega el rol 'secretaria_programa' al catalogo de roles (la persona
   que revisa y aprueba las entregas documentales de los docentes).
2) crea las tablas 'entregas' y 'documentos_entrega' (nuevas --
   Base.metadata.create_all ya las crea solas porque son tablas nuevas,
   no requieren ALTER).

Idempotente: se puede correr varias veces sin duplicar nada.

Uso:
    python -m scripts.migrar_entregas_documentos
"""
from sqlalchemy import select

from db.database import engine, get_session
from db.models import Base, Rol


def migrar():
    Base.metadata.create_all(engine)  # crea entregas / documentos_entrega si no existen

    with get_session() as session:
        if session.scalar(select(Rol).where(Rol.nombre == "secretaria_programa")) is None:
            session.add(Rol(nombre="secretaria_programa"))
            session.commit()
            print("  Rol 'secretaria_programa' creado.")
        else:
            print("  El rol 'secretaria_programa' ya existía.")

    print("Listo: rol 'secretaria_programa' y tablas de entregas disponibles.")


if __name__ == "__main__":
    migrar()
