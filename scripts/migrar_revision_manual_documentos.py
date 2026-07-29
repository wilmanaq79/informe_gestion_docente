# -*- coding: utf-8 -*-
"""Migracion puntual: agrega a 'documentos_entrega' las columnas para
forzar la revision humana de los documentos que el agente de firmas no
pudo confirmar como firmados (Revision manual o No firmado) antes de
poder aprobar la entrega. Idempotente.

Uso:
    python -m scripts.migrar_revision_manual_documentos
"""
from sqlalchemy import text

from db.database import engine


def migrar():
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE documentos_entrega ADD COLUMN IF NOT EXISTS visto_en TIMESTAMP")
        )
        conn.execute(
            text(
                "ALTER TABLE documentos_entrega ADD COLUMN IF NOT EXISTS revisado_manualmente "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE documentos_entrega ADD COLUMN IF NOT EXISTS revisado_por_id "
                "INTEGER REFERENCES usuarios(id)"
            )
        )
        conn.execute(
            text("ALTER TABLE documentos_entrega ADD COLUMN IF NOT EXISTS revisado_en TIMESTAMP")
        )
    print("Listo: documentos_entrega ahora registra si un revisor abrio y confirmo la revision manual.")


if __name__ == "__main__":
    migrar()
