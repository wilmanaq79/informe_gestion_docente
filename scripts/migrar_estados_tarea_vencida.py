# -*- coding: utf-8 -*-
"""Corrige el catalogo de estados del modulo de tareas (ver
docs/especificacionModuloTareas.md): agrega el estado VENCIDA -- que el
sistema asigna automaticamente cuando se supera la fecha limite y la
tarea no ha sido finalizada/cancelada (ver
db.repository._marcar_tareas_vencidas) -- y agrega icono/color a cada
estado, mismo patron que ya tienen las prioridades. Antes, "vencida" se
trataba solo como una condicion calculada aparte del estado operativo;
esta migracion la convierte en un estado real, a pedido del usuario.
Idempotente.

Uso:
    python -m scripts.migrar_estados_tarea_vencida
"""
from sqlalchemy import text

from db.database import engine

# icono/color por estado -- los primeros 6 son los que el usuario pidio
# explicitamente (con sus emojis); el resto sigue el mismo criterio para
# no dejar estados sin icono.
_ICONOS_ESTADO = {
    "BORRADOR": ("📝", "gris"),
    "PROGRAMADA": ("🗓️", "azul"),
    "SIN_COMENZAR": ("🟢", "verde"),
    "EN_PROCESO": ("🟡", "dorado"),
    "PENDIENTE_REVISION": ("🔵", "azul"),
    "DEVUELTA_OBSERVACIONES": ("🟠", "naranja"),
    "TERMINADA": ("✅", "verde"),
    "SUSPENDIDA": ("⏸️", "gris"),
    "CANCELADA": ("🔴", "rojo"),
    "VENCIDA": ("⏰", "rojo"),
}


def migrar():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE estados_tarea ADD COLUMN IF NOT EXISTS icono VARCHAR(10) NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE estados_tarea ADD COLUMN IF NOT EXISTS color VARCHAR(20) NOT NULL DEFAULT ''"))

        # VENCIDA es un estado nuevo -- orden 10, despues de CANCELADA.
        conn.execute(text(
            "INSERT INTO estados_tarea (nombre, orden) VALUES ('VENCIDA', 10) "
            "ON CONFLICT (nombre) DO NOTHING"
        ))

        for nombre, (icono, color) in _ICONOS_ESTADO.items():
            conn.execute(
                text("UPDATE estados_tarea SET icono = :icono, color = :color WHERE nombre = :nombre"),
                {"icono": icono, "color": color, "nombre": nombre},
            )

    print("Listo: estado VENCIDA agregado; iconos/colores asignados a todos los estados de tarea.")


if __name__ == "__main__":
    migrar()
