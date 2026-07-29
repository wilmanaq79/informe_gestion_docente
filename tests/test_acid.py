# -*- coding: utf-8 -*-
"""Pruebas ACID contra la base de datos real de desarrollo (Postgres).

Usan la fixture db_session (tests/conftest.py): cada prueba corre
dentro de una transaccion que SIEMPRE se revierte al final, asi que
ningun dato de prueba queda persistido en la base de datos real.

- TestAtomicidad: el fix del procesamiento por lotes (commit=False +
  un solo commit/rollback al final) realmente deja "todo o nada".
- TestConsistencia: las constraints de unicidad se respetan, incluido
  el indice unico parcial nuevo de "un solo periodo activo".
- TestAislamiento / TestDurabilidad: usan sus propias conexiones (no
  la fixture) porque necesitan demostrar comportamiento entre
  transacciones/conexiones realmente separadas; limpian sus datos de
  prueba explicitamente al terminar.
"""
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from db.database import SessionLocal, engine
from db.models import AsignacionAcademica, InformeCorte, PeriodoAcademico, Programa, Usuario
from db.repository import (
    corte_por_numero,
    crear_usuario,
    guardar_informe_corte,
    listar_roles,
    obtener_o_crear_asignacion,
    periodo_activo,
)


def _rol_id(session, nombre: str) -> int:
    return next(r.id for r in listar_roles(session) if r.nombre == nombre)


class TestAtomicidad:
    def test_lote_de_materias_no_deja_estado_parcial_si_una_falla(self, db_session):
        """Reproduce exactamente el bug critico encontrado: procesar un
        lote de 2 materias donde la segunda falla NO debe dejar la
        primera guardada a medias (antes del fix, cada llamada hacia su
        propio commit interno)."""
        periodo = periodo_activo(db_session)
        assert periodo is not None, "Se necesita un periodo activo sembrado para esta prueba."
        corte = corte_por_numero(db_session, 1)
        assert corte is not None

        programa = Programa(nombre=f"PYTEST Programa {uuid.uuid4().hex[:6]}", codigo=f"pytest-{uuid.uuid4().hex[:8]}")
        db_session.add(programa)
        db_session.flush()

        docente = crear_usuario(
            db_session, "PYTEST Atomicidad", None, None,
            f"__pytest_atom_{uuid.uuid4().hex[:8]}__", "hash-falso", _rol_id(db_session, "docente"),
            programa_id=programa.id,
        )

        materia_ok = f"Materia OK {uuid.uuid4().hex[:6]}"
        resumen = {
            "matriculados": 10, "asistencia_regular": 8, "evaluados": 10,
            "aprobaron": 7, "es_estimado": False,
        }
        try:
            # Materia 1: se guarda sin commit (como en el lote real).
            asignacion1 = obtener_o_crear_asignacion(
                db_session, docente.id, periodo.id, materia_ok, None, commit=False
            )
            guardar_informe_corte(db_session, asignacion1.id, 1, resumen, 3.5, 3.6, 0.4, [], commit=False)

            # Materia 2 "falla" a mitad del lote -> el caller debe hacer
            # rollback() en vez de dejar la materia 1 comprometida.
            db_session.rollback()

            # Tras el rollback, ni la asignacion ni el informe de la
            # materia 1 deben existir -- "todo o nada".
            encontrada = db_session.scalar(
                select(AsignacionAcademica).where(AsignacionAcademica.asignatura == materia_ok)
            )
            assert encontrada is None, "La materia 1 quedo guardada a pesar del rollback del lote."
        finally:
            db_session.rollback()


class TestConsistencia:
    def test_username_duplicado_viola_unique_constraint(self, db_session):
        rol_docente = _rol_id(db_session, "docente")
        username = f"__pytest_dup_{uuid.uuid4().hex[:8]}__"
        crear_usuario(db_session, "PYTEST Uno", None, None, username, "hash1", rol_docente)

        with pytest.raises(IntegrityError):
            crear_usuario(db_session, "PYTEST Dos", None, None, username, "hash2", rol_docente)
        db_session.rollback()  # la sesion queda en estado abortado tras el IntegrityError

    def test_no_puede_haber_dos_periodos_activos_a_la_vez(self, db_session):
        """Ejercita directamente el indice unico parcial
        uq_un_solo_periodo_activo creado por
        scripts/migrar_indices_acid.py: activar un segundo periodo con
        UPDATE crudo (sin pasar por activar_periodo(), que desactiva los
        demas) debe chocar con la constraint de la base de datos."""
        # Desactiva temporalmente el periodo real activo dentro de esta
        # transaccion de prueba (se revierte solo al final, junto con
        # todo lo demas) para poder activar los dos periodos de prueba
        # uno a la vez y probar la constraint sin chocar con datos reales.
        db_session.execute(text("UPDATE periodos_academicos SET activo = false"))

        anio_base = 1900 + (uuid.uuid4().int % 90)  # anio arbitrario que no colisione con datos reales
        p1 = PeriodoAcademico(nombre=f"{anio_base}-1", anio=anio_base, semestre=1, activo=True)
        p2 = PeriodoAcademico(nombre=f"{anio_base}-2", anio=anio_base, semestre=2, activo=False)
        db_session.add_all([p1, p2])
        db_session.flush()

        with pytest.raises(IntegrityError):
            db_session.execute(
                text("UPDATE periodos_academicos SET activo = true WHERE id = :id"), {"id": p2.id}
            )
            db_session.flush()
        db_session.rollback()


class TestAislamiento:
    def test_una_transaccion_sin_commit_no_es_visible_para_otra_conexion(self):
        """READ COMMITTED (el nivel por defecto de Postgres): una fila
        insertada por la conexion A pero AUN NO confirmada no debe ser
        visible desde una conexion B completamente distinta."""
        conexion_a = engine.connect()
        transaccion_a = conexion_a.begin()
        username = f"__pytest_aislamiento_{uuid.uuid4().hex[:8]}__"
        try:
            conexion_a.execute(
                text(
                    "INSERT INTO usuarios (nombre_completo, username, password_hash, rol_id, activo, creado_en) "
                    "SELECT 'PYTEST Aislamiento', :username, 'x', id, true, now() "
                    "FROM roles WHERE nombre = 'docente'"
                ),
                {"username": username},
            )
            # NO se hace commit todavia.

            conexion_b = engine.connect()
            try:
                visible_desde_b = conexion_b.execute(
                    text("SELECT 1 FROM usuarios WHERE username = :username"), {"username": username}
                ).first()
                assert visible_desde_b is None, "Una fila sin commit no deberia ser visible desde otra conexion."
            finally:
                conexion_b.close()
        finally:
            transaccion_a.rollback()
            conexion_a.close()


class TestDurabilidad:
    def test_un_commit_persiste_y_es_visible_desde_una_conexion_nueva(self):
        """Un commit real debe sobrevivir al cierre de la sesion que lo
        hizo: se verifica reconectando desde cero (no la misma sesion ni
        conexion). Limpia el dato de prueba explicitamente al final."""
        session = SessionLocal()
        username = f"__pytest_durabilidad_{uuid.uuid4().hex[:8]}__"
        try:
            rol_docente_id = next(r.id for r in listar_roles(session) if r.nombre == "docente")
            crear_usuario(session, "PYTEST Durabilidad", None, None, username, "hash", rol_docente_id)
        finally:
            session.close()

        # Sesion COMPLETAMENTE NUEVA, conexion nueva del pool.
        verificacion = SessionLocal()
        try:
            encontrado = verificacion.scalar(select(Usuario).where(Usuario.username == username))
            assert encontrado is not None, "El commit no persistio: no es visible desde una sesion nueva."
        finally:
            # Limpieza explicita: esta prueba SI hace commits reales.
            verificacion.execute(text("DELETE FROM usuarios WHERE username = :username"), {"username": username})
            verificacion.commit()
            verificacion.close()
