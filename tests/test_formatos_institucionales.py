# -*- coding: utf-8 -*-
"""Pruebas de los formatos institucionales (gestion y autoevaluacion
docente, acuerdo pedagogico, plan de actividades, lista de asistencia):
un unico juego de archivos por PROGRAMA ACADEMICO completo
(db.repository.adjuntar_formato_institucional /
quitar_formato_institucional), a diferencia del silabo/programa de
asignatura que son por materia (ver
tests/test_repositorio_asignaturas_formatos.py)."""
import uuid

import pytest

from db.models import Programa
from db.repository import (
    TIPOS_FORMATO_INSTITUCIONAL,
    adjuntar_formato_institucional,
    quitar_formato_institucional,
)


def _crear_programa(session):
    programa = Programa(nombre=f"PYTEST Programa {uuid.uuid4().hex[:6]}", codigo=f"pytest-{uuid.uuid4().hex[:8]}")
    session.add(programa)
    session.commit()
    session.refresh(programa)
    return programa


class TestAdjuntarYQuitarFormatoInstitucional:
    @pytest.mark.parametrize("tipo", list(TIPOS_FORMATO_INSTITUCIONAL))
    def test_adjuntar_guarda_los_3_campos_del_tipo(self, db_session, tipo):
        programa = _crear_programa(db_session)
        actualizado = adjuntar_formato_institucional(
            db_session, programa.id, tipo, "archivo.xlsx", f"ruta/falsa/{uuid.uuid4().hex}.xlsx", 1234
        )
        assert getattr(actualizado, f"{tipo}_nombre_archivo") == "archivo.xlsx"
        assert getattr(actualizado, f"{tipo}_tamano_bytes") == 1234
        assert getattr(actualizado, f"{tipo}_ruta_archivo") is not None

        # Los otros tipos del mismo programa no deben verse afectados.
        for otro in TIPOS_FORMATO_INSTITUCIONAL:
            if otro != tipo:
                assert getattr(actualizado, f"{otro}_nombre_archivo") is None

    def test_adjuntar_con_tipo_invalido_lanza_value_error(self, db_session):
        programa = _crear_programa(db_session)
        with pytest.raises(ValueError):
            adjuntar_formato_institucional(db_session, programa.id, "tipo_que_no_existe", "x.xlsx", "ruta", 1)

    def test_adjuntar_a_programa_inexistente_devuelve_none(self, db_session):
        assert adjuntar_formato_institucional(db_session, 999999999, "gestion_docente", "x.xlsx", "ruta", 1) is None

    @pytest.mark.parametrize("tipo", list(TIPOS_FORMATO_INSTITUCIONAL))
    def test_quitar_limpia_los_3_campos_y_devuelve_true(self, db_session, tipo):
        programa = _crear_programa(db_session)
        adjuntar_formato_institucional(db_session, programa.id, tipo, "archivo.xlsx", "ruta/falsa.xlsx", 100)

        assert quitar_formato_institucional(db_session, programa.id, tipo) is True
        db_session.refresh(programa)
        assert getattr(programa, f"{tipo}_nombre_archivo") is None
        assert getattr(programa, f"{tipo}_ruta_archivo") is None
        assert getattr(programa, f"{tipo}_tamano_bytes") is None

    def test_quitar_sin_archivo_cargado_devuelve_false(self, db_session):
        programa = _crear_programa(db_session)
        assert quitar_formato_institucional(db_session, programa.id, "gestion_docente") is False

    def test_quitar_con_tipo_invalido_lanza_value_error(self, db_session):
        programa = _crear_programa(db_session)
        with pytest.raises(ValueError):
            quitar_formato_institucional(db_session, programa.id, "tipo_que_no_existe")
