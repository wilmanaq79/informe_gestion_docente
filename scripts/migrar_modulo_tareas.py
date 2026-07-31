# -*- coding: utf-8 -*-
"""Fase 1 del modulo de tareas (ver docs/especificacionModuloTareas.md):
crea las tablas de catalogo (categorias, prioridades, estados) y la
tabla de tareas con su tabla puente de responsables secundarios, y
siembra los catalogos iniciales de la especificacion. Idempotente
(CREATE TABLE IF NOT EXISTS / INSERT ... ON CONFLICT DO NOTHING).

Uso:
    python -m scripts.migrar_modulo_tareas
"""
from sqlalchemy import text

from db.database import engine

_PRIORIDADES = [
    # nombre, icono, color, orden, nivel
    ("BAJA", "🟢", "verde", 1, 1),
    ("MEDIA", "🟡", "dorado", 2, 2),
    ("ALTA", "🟠", "naranja", 3, 3),
    ("CRITICA", "🔴", "rojo", 4, 4),
]

_ESTADOS = [
    # nombre, orden
    ("BORRADOR", 1),
    ("PROGRAMADA", 2),
    ("SIN_COMENZAR", 3),
    ("EN_PROCESO", 4),
    ("PENDIENTE_REVISION", 5),
    ("DEVUELTA_OBSERVACIONES", 6),
    ("TERMINADA", 7),
    ("SUSPENDIDA", 8),
    ("CANCELADA", 9),
]

_CATEGORIAS = [
    "Docencia", "Investigación", "Proyección Social", "Dirección de Programa",
    "Secretaría", "Consejo Académico", "Autoevaluación", "Acreditación",
    "Gestión de Calidad", "Bienestar", "Eventos", "Reuniones", "Capacitación",
    "Tutorías", "Gestión Administrativa", "Internacionalización", "Egresados",
    "Prácticas profesionales", "Comunicaciones", "Planeación", "Personal", "Otras",
]


def migrar():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS categorias_tarea (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(60) NOT NULL UNIQUE,
                activa BOOLEAN NOT NULL DEFAULT TRUE
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prioridades_tarea (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(20) NOT NULL UNIQUE,
                icono VARCHAR(10) NOT NULL,
                color VARCHAR(20) NOT NULL,
                orden INTEGER NOT NULL,
                nivel INTEGER NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS estados_tarea (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(30) NOT NULL UNIQUE,
                orden INTEGER NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tareas (
                id SERIAL PRIMARY KEY,
                titulo VARCHAR(200) NOT NULL,
                descripcion TEXT,
                objetivo TEXT,
                resultado_esperado TEXT,
                tipo VARCHAR(20) NOT NULL,
                categoria_id INTEGER REFERENCES categorias_tarea(id),
                prioridad_id INTEGER NOT NULL REFERENCES prioridades_tarea(id),
                estado_id INTEGER NOT NULL REFERENCES estados_tarea(id),
                programa_id INTEGER NOT NULL REFERENCES programas(id),
                periodo_id INTEGER REFERENCES periodos_academicos(id),
                responsable_principal_id INTEGER REFERENCES usuarios(id),
                creado_por_id INTEGER REFERENCES usuarios(id),
                asignado_por_id INTEGER REFERENCES usuarios(id),
                fecha_inicio DATE,
                fecha_limite DATE,
                hora_limite TIME,
                fecha_fin_real TIMESTAMP,
                porcentaje_avance INTEGER NOT NULL DEFAULT 0,
                confidencialidad VARCHAR(20) NOT NULL DEFAULT 'normal',
                requiere_evidencia BOOLEAN NOT NULL DEFAULT FALSE,
                requiere_aprobacion BOOLEAN NOT NULL DEFAULT TRUE,
                permite_ampliacion BOOLEAN NOT NULL DEFAULT TRUE,
                motivo_cancelacion TEXT,
                justificacion_retraso TEXT,
                creado_en TIMESTAMP NOT NULL DEFAULT now(),
                actualizado_en TIMESTAMP NOT NULL DEFAULT now()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tareas_programa_id ON tareas (programa_id)"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_tareas_responsable_principal_id ON tareas (responsable_principal_id)"
        ))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tarea_responsables_secundarios (
                id SERIAL PRIMARY KEY,
                tarea_id INTEGER NOT NULL REFERENCES tareas(id) ON DELETE CASCADE,
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                creado_en TIMESTAMP NOT NULL DEFAULT now(),
                CONSTRAINT uq_tarea_responsable_secundario UNIQUE (tarea_id, usuario_id)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_tarea_resp_secundarios_tarea_id "
            "ON tarea_responsables_secundarios (tarea_id)"
        ))

        for nombre, icono, color, orden, nivel in _PRIORIDADES:
            conn.execute(
                text(
                    "INSERT INTO prioridades_tarea (nombre, icono, color, orden, nivel) "
                    "VALUES (:nombre, :icono, :color, :orden, :nivel) "
                    "ON CONFLICT (nombre) DO NOTHING"
                ),
                {"nombre": nombre, "icono": icono, "color": color, "orden": orden, "nivel": nivel},
            )
        for nombre, orden in _ESTADOS:
            conn.execute(
                text("INSERT INTO estados_tarea (nombre, orden) VALUES (:nombre, :orden) ON CONFLICT (nombre) DO NOTHING"),
                {"nombre": nombre, "orden": orden},
            )
        for nombre in _CATEGORIAS:
            conn.execute(
                text("INSERT INTO categorias_tarea (nombre) VALUES (:nombre) ON CONFLICT (nombre) DO NOTHING"),
                {"nombre": nombre},
            )

    print("Listo: tablas del modulo de tareas creadas y catalogos sembrados (Fase 1).")


if __name__ == "__main__":
    migrar()
