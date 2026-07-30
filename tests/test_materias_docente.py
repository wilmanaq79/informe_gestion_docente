# -*- coding: utf-8 -*-
"""Pruebas de las fuentes persistentes de nombres de materia usadas para
sugerir/prellenar selectores en vez de depender de texto libre o de
datos que solo viven en la ejecucion actual de Streamlit:

- materias_del_docente: alimenta 'Entrega de documentos' (vistas/
  docente.py). Antes, esa lista solo se derivaba de la plantilla Excel
  recien subida en la ejecucion de Streamlit, y por eso desaparecia en
  cualquier refresco de pagina (los file_uploader no sobreviven a un
  refresco del navegador).
- materias_del_programa: alimenta 'Agregar asignatura al repositorio'
  (vistas/repositorio_asignaturas.py), sugiriendo materias ya conocidas
  del programa en vez de un campo de texto siempre en blanco."""
import uuid

from db.models import Programa
from db.repository import (
    crear_usuario,
    listar_roles,
    materias_del_programa,
    obtener_o_crear_asignacion,
    periodo_activo,
    materias_del_docente,
)


def _rol_id(session, nombre: str) -> int:
    return next(r.id for r in listar_roles(session) if r.nombre == nombre)


def _crear_docente(session):
    programa = Programa(nombre=f"PYTEST Programa {uuid.uuid4().hex[:6]}", codigo=f"pytest-{uuid.uuid4().hex[:8]}")
    session.add(programa)
    session.flush()
    return crear_usuario(
        session, "PYTEST Materias Docente", None, None, f"__pytest_materias_{uuid.uuid4().hex[:8]}__",
        "hash", _rol_id(session, "docente"), programa_id=programa.id,
    )


class TestMateriasDelDocente:
    def test_devuelve_las_materias_ya_registradas_en_el_periodo(self, db_session):
        periodo = periodo_activo(db_session)
        assert periodo is not None, "Se necesita un periodo activo sembrado para esta prueba."
        docente = _crear_docente(db_session)

        nombre_1 = f"Sistemas Operativos {uuid.uuid4().hex[:6]}"
        nombre_2 = f"Inteligencia Artificial {uuid.uuid4().hex[:6]}"
        obtener_o_crear_asignacion(db_session, docente.id, periodo.id, nombre_1, None)
        obtener_o_crear_asignacion(db_session, docente.id, periodo.id, nombre_2, "Grupo A")

        materias = materias_del_docente(db_session, docente.id, periodo.id)
        assert nombre_1 in materias
        assert nombre_2 in materias

    def test_no_devuelve_materias_de_otro_docente(self, db_session):
        periodo = periodo_activo(db_session)
        assert periodo is not None
        docente_a = _crear_docente(db_session)
        docente_b = _crear_docente(db_session)

        nombre_propia = f"Materia De A {uuid.uuid4().hex[:6]}"
        nombre_ajena = f"Materia De B {uuid.uuid4().hex[:6]}"
        obtener_o_crear_asignacion(db_session, docente_a.id, periodo.id, nombre_propia, None)
        obtener_o_crear_asignacion(db_session, docente_b.id, periodo.id, nombre_ajena, None)

        materias_de_a = materias_del_docente(db_session, docente_a.id, periodo.id)
        assert nombre_propia in materias_de_a
        assert nombre_ajena not in materias_de_a

    def test_docente_sin_materias_registradas_devuelve_lista_vacia(self, db_session):
        periodo = periodo_activo(db_session)
        assert periodo is not None
        docente = _crear_docente(db_session)

        assert materias_del_docente(db_session, docente.id, periodo.id) == []


class TestMateriasDelPrograma:
    def test_devuelve_materias_de_cualquier_periodo_del_programa(self, db_session):
        """A diferencia de materias_del_docente, esta NO se filtra por
        periodo -- el repositorio de silabos no es por semestre."""
        periodo = periodo_activo(db_session)
        assert periodo is not None
        docente = _crear_docente(db_session)
        programa_id = docente.programa_id

        nombre = f"Sistemas Operativos {uuid.uuid4().hex[:6]}"
        obtener_o_crear_asignacion(db_session, docente.id, periodo.id, nombre, None)

        assert nombre in materias_del_programa(db_session, programa_id)

    def test_no_devuelve_materias_de_otro_programa(self, db_session):
        periodo = periodo_activo(db_session)
        assert periodo is not None
        docente_a = _crear_docente(db_session)
        docente_b = _crear_docente(db_session)

        nombre_propia = f"Materia Programa A {uuid.uuid4().hex[:6]}"
        nombre_ajena = f"Materia Programa B {uuid.uuid4().hex[:6]}"
        obtener_o_crear_asignacion(db_session, docente_a.id, periodo.id, nombre_propia, None)
        obtener_o_crear_asignacion(db_session, docente_b.id, periodo.id, nombre_ajena, None)

        materias_de_a = materias_del_programa(db_session, docente_a.programa_id)
        assert nombre_propia in materias_de_a
        assert nombre_ajena not in materias_de_a

    def test_no_repite_la_misma_materia_dictada_en_dos_periodos(self, db_session):
        from db.repository import crear_o_obtener_periodo

        docente = _crear_docente(db_session)
        periodo_1 = periodo_activo(db_session)
        assert periodo_1 is not None
        periodo_2 = crear_o_obtener_periodo(db_session, periodo_1.anio + 50, 1)

        nombre = f"Materia Repetida {uuid.uuid4().hex[:6]}"
        obtener_o_crear_asignacion(db_session, docente.id, periodo_1.id, nombre, None)
        obtener_o_crear_asignacion(db_session, docente.id, periodo_2.id, nombre, None)

        materias = materias_del_programa(db_session, docente.programa_id)
        assert materias.count(nombre) == 1
