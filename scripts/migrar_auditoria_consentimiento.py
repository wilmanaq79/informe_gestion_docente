# -*- coding: utf-8 -*-
"""Migracion puntual: crea la tabla 'aceptaciones_politica_tratamiento'
(nueva -- Base.metadata.create_all ya la crea sola porque es tabla
nueva, no requiere ALTER). Idempotente.

Bitacora de CADA aceptacion del Aviso de Privacidad y Autorizacion
para el Tratamiento de Datos Personales (Ley 1581 de 2012), a
diferencia de los campos en 'usuarios' que solo reflejan el estado
mas reciente.

Uso:
    python -m scripts.migrar_auditoria_consentimiento
"""
from db.database import engine
from db.models import Base


def migrar():
    Base.metadata.create_all(engine)
    print("Listo: tabla 'aceptaciones_politica_tratamiento' disponible.")


if __name__ == "__main__":
    migrar()
