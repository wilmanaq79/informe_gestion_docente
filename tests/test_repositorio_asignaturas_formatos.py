# -*- coding: utf-8 -*-
"""Pruebas de las funciones genericas de archivos del repositorio de
asignaturas (db.repository.adjuntar_archivo_repositorio /
quitar_archivo_repositorio / eliminar_repositorio_asignatura), que
reemplazaron las 4 funciones especificas adjuntar_silabo/
adjuntar_programa/quitar_silabo/quitar_programa (silabo y programa de
asignatura, ambos por materia). Los formatos institucionales
(gestion_docente, acuerdo_pedagogico, plan_actividades) NO viven aqui
-- son por PROGRAMA ACADEMICO completo, ver
tests/test_formatos_institucionales.py."""
import uuid

import pytest

from db.models import Programa
from db.repository import (
    TIPOS_ARCHIVO_REPOSITORIO,
    adjuntar_archivo_repositorio,
    crear_repositorio_asignatura,
    eliminar_repositorio_asignatura,
    quitar_archivo_repositorio,
)


def _crear_entrada(session):
    programa = Programa(nombre=f"PYTEST Programa {uuid.uuid4().hex[:6]}", codigo=f"pytest-{uuid.uuid4().hex[:8]}")
    session.add(programa)
    session.flush()
    return crear_repositorio_asignatura(
        session, f"PYTEST Materia {uuid.uuid4().hex[:6]}", None, creado_por_id=None, programa_id=programa.id
    )


class TestAdjuntarYQuitarArchivoRepositorio:
    @pytest.mark.parametrize("tipo", list(TIPOS_ARCHIVO_REPOSITORIO))
    def test_adjuntar_guarda_los_3_campos_del_tipo(self, db_session, tipo):
        entrada = _crear_entrada(db_session)
        actualizado = adjuntar_archivo_repositorio(
            db_session, entrada.id, tipo, "archivo.pdf", f"ruta/falsa/{uuid.uuid4().hex}.pdf", 1234, entrada.creado_por_id
        )
        assert getattr(actualizado, f"{tipo}_nombre_archivo") == "archivo.pdf"
        assert getattr(actualizado, f"{tipo}_tamano_bytes") == 1234
        assert getattr(actualizado, f"{tipo}_ruta_archivo") is not None

        # Los otros tipos de la misma fila no deben verse afectados.
        for otro in TIPOS_ARCHIVO_REPOSITORIO:
            if otro != tipo:
                assert getattr(actualizado, f"{otro}_nombre_archivo") is None

    def test_adjuntar_con_tipo_invalido_lanza_value_error(self, db_session):
        entrada = _crear_entrada(db_session)
        with pytest.raises(ValueError):
            adjuntar_archivo_repositorio(db_session, entrada.id, "tipo_que_no_existe", "x.pdf", "ruta", 1, entrada.creado_por_id)

    def test_adjuntar_a_entrada_inexistente_devuelve_none(self, db_session):
        assert adjuntar_archivo_repositorio(db_session, 999999999, "silabo", "x.pdf", "ruta", 1, 1) is None

    @pytest.mark.parametrize("tipo", list(TIPOS_ARCHIVO_REPOSITORIO))
    def test_quitar_limpia_los_3_campos_y_devuelve_true(self, db_session, tipo):
        entrada = _crear_entrada(db_session)
        adjuntar_archivo_repositorio(db_session, entrada.id, tipo, "archivo.pdf", "ruta/falsa.pdf", 100, entrada.creado_por_id)

        assert quitar_archivo_repositorio(db_session, entrada.id, tipo, entrada.creado_por_id) is True
        db_session.refresh(entrada)
        assert getattr(entrada, f"{tipo}_nombre_archivo") is None
        assert getattr(entrada, f"{tipo}_ruta_archivo") is None
        assert getattr(entrada, f"{tipo}_tamano_bytes") is None

    def test_quitar_sin_archivo_cargado_devuelve_false(self, db_session):
        entrada = _crear_entrada(db_session)
        assert quitar_archivo_repositorio(db_session, entrada.id, "silabo", entrada.creado_por_id) is False

    def test_quitar_con_tipo_invalido_lanza_value_error(self, db_session):
        entrada = _crear_entrada(db_session)
        with pytest.raises(ValueError):
            quitar_archivo_repositorio(db_session, entrada.id, "tipo_que_no_existe", entrada.creado_por_id)


class TestEliminarRepositorioAsignaturaConFormatos:
    def test_eliminar_funciona_con_los_tipos_de_archivo_cargados(self, db_session):
        """eliminar_repositorio_asignatura debe limpiar silabo y
        programa, sin lanzar aunque alguno este vacio."""
        entrada = _crear_entrada(db_session)
        for tipo in TIPOS_ARCHIVO_REPOSITORIO:
            adjuntar_archivo_repositorio(
                db_session, entrada.id, tipo, "archivo.pdf", f"ruta/falsa/{tipo}.pdf", 10, entrada.creado_por_id
            )
        assert eliminar_repositorio_asignatura(db_session, entrada.id) is True

    def test_eliminar_entrada_inexistente_devuelve_false(self, db_session):
        assert eliminar_repositorio_asignatura(db_session, 999999999) is False
