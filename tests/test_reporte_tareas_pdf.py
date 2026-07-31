# -*- coding: utf-8 -*-
"""Pruebas del informe PDF del modulo de tareas
(backend/services/reporte_tareas_pdf.py) y del endpoint
GET /api/tareas/informe: solo se verifica que genera un PDF valido y no
lanza con listas vacias -- el contenido visual exacto ya se cubre
manualmente (ver docs/especificacionModuloTareas.md seccion 21)."""
import io
import uuid

from backend.api.routers import tareas as tareas_router
from backend.services.reporte_tareas_pdf import generar_informe_tareas
from db.models import Programa
from db.repository import crear_tarea, crear_usuario, listar_prioridades_tarea, listar_roles


def _rol_id(session, nombre: str) -> int:
    return next(r.id for r in listar_roles(session) if r.nombre == nombre)


def _crear_programa(session) -> Programa:
    programa = Programa(nombre=f"PYTEST Programa {uuid.uuid4().hex[:6]}", codigo=f"pytest-{uuid.uuid4().hex[:8]}")
    session.add(programa)
    session.flush()
    return programa


def _crear_usuario(session, rol_nombre: str, programa_id: int):
    return crear_usuario(
        session, f"PYTEST {rol_nombre}", None, None, f"__pytest_informe_tareas_{uuid.uuid4().hex[:10]}__",
        "hash", _rol_id(session, rol_nombre), programa_id=programa_id,
    )


def _prioridad_id(session) -> int:
    return listar_prioridades_tarea(session)[0].id


INDICADORES_VACIOS = {
    "total": 0, "por_estado": {}, "vencidas": 0, "proximas_a_vencer": 0, "cumplimiento_pct": 0.0,
}


class TestGenerarInformeTareas:
    def test_pdf_valido_sin_tareas(self):
        buffer = io.BytesIO()
        generar_informe_tareas([], INDICADORES_VACIOS, buffer, "Ingeniería de Sistemas", "Administrador")
        contenido = buffer.getvalue()
        assert contenido.startswith(b"%PDF")
        assert len(contenido) > 0

    def test_pdf_valido_con_tareas(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Tarea para el informe", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        indicadores = {
            "total": 1, "por_estado": {"SIN_COMENZAR": 1}, "vencidas": 0,
            "proximas_a_vencer": 0, "cumplimiento_pct": 0.0,
        }
        buffer = io.BytesIO()
        generar_informe_tareas([tarea], indicadores, buffer, programa.nombre, director.nombre_completo)
        contenido = buffer.getvalue()
        assert contenido.startswith(b"%PDF")


class TestEndpointInforme:
    def test_informe_devuelve_pdf_streaming(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        crear_tarea(
            db_session, titulo="Tarea visible en el informe", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        respuesta = tareas_router.informe(db=db_session, usuario=director)
        assert respuesta.media_type == "application/pdf"
        assert "attachment" in respuesta.headers["Content-Disposition"]
