# -*- coding: utf-8 -*-
"""Migracion puntual: agrega a 'documentos_entrega' las columnas del
veredicto del agente de verificacion de firmas
(agente_notas.agente_firmas). Idempotente.

Uso:
    python -m scripts.migrar_agente_firmas
"""
from sqlalchemy import text

from db.database import engine


def migrar():
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE documentos_entrega ADD COLUMN IF NOT EXISTS firma_detectada BOOLEAN")
        )
        conn.execute(
            text("ALTER TABLE documentos_entrega ADD COLUMN IF NOT EXISTS firma_confianza VARCHAR(10)")
        )
        conn.execute(
            text("ALTER TABLE documentos_entrega ADD COLUMN IF NOT EXISTS firma_detalle VARCHAR(300)")
        )
    print("Listo: documentos_entrega ahora registra el veredicto del agente de firmas.")


if __name__ == "__main__":
    migrar()
