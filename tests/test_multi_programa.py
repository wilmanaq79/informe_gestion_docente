# -*- coding: utf-8 -*-
"""Pruebas de aislamiento entre programas académicos -- la garantía
central del cambio multi-programa (ver docs/planEscalamiento.md): un
Director/Secretario/Secretaria de un programa NUNCA debe ver ni recibir
notificaciones sobre datos de otro programa, aunque ambos compartan la
misma base de datos e instancia del sistema.

Usa la fixture db_session (BD real, con rollback) -- ningún dato de
prueba queda persistido."""
import uuid

import pytest

from fastapi import HTTPException

from backend.api.deps import verificar_pertenece_a_programa
from db.models import Programa
from db.repository import (
    actualizar_usuario,
    corte_por_numero,
    crear_repositorio_asignatura,
    crear_usuario,
    emails_personal_revisor,
    ids_personal_revisor,
    listar_docentes,
    listar_entregas,
    listar_repositorio_asignaturas,
    listar_usuarios,
    obtener_o_crear_asignacion,
    obtener_o_crear_entrega,
    periodo_activo,
)


def _rol_id(session, nombre: str) -> int:
    from db.repository import listar_roles
    return next(r.id for r in listar_roles(session) if r.nombre == nombre)


def _crear_programa(session, etiqueta: str) -> Programa:
    programa = Programa(
        nombre=f"PYTEST {etiqueta} {uuid.uuid4().hex[:6]}", codigo=f"pytest-{etiqueta.lower()}-{uuid.uuid4().hex[:8]}"
    )
    session.add(programa)
    session.flush()
    return programa


@pytest.fixture()
def dos_programas_con_personal(db_session):
    """Crea 2 programas, cada uno con 1 docente + 1 director + 1
    secretario + 1 secretaria_programa, y una entrega + un repositorio
    de asignatura por programa. Devuelve un dict con todo lo creado,
    indexado por 'a'/'b'."""
    periodo = periodo_activo(db_session)
    assert periodo is not None, "Se necesita un periodo activo sembrado para esta prueba."
    corte = corte_por_numero(db_session, 1)
    assert corte is not None

    datos = {}
    for etiqueta in ("a", "b"):
        programa = _crear_programa(db_session, etiqueta.upper())
        sufijo = uuid.uuid4().hex[:8]
        docente = crear_usuario(
            db_session, f"PYTEST Docente {etiqueta.upper()}", None, None, f"__pytest_mp_doc_{etiqueta}_{sufijo}__",
            "hash", _rol_id(db_session, "docente"), programa_id=programa.id,
        )
        director = crear_usuario(
            db_session, f"PYTEST Director {etiqueta.upper()}", None, f"director_{etiqueta}_{sufijo}@example.com",
            f"__pytest_mp_dir_{etiqueta}_{sufijo}__", "hash", _rol_id(db_session, "director"), programa_id=programa.id,
        )
        secretario = crear_usuario(
            db_session, f"PYTEST Secretario {etiqueta.upper()}", None, f"secretario_{etiqueta}_{sufijo}@example.com",
            f"__pytest_mp_sec_{etiqueta}_{sufijo}__", "hash", _rol_id(db_session, "secretario"), programa_id=programa.id,
        )
        entrega = obtener_o_crear_entrega(db_session, docente.id, periodo.id, corte.id)
        repo = crear_repositorio_asignatura(
            db_session, f"Materia común {sufijo}", docente.id, director.id, programa.id
        )
        asignacion = obtener_o_crear_asignacion(db_session, docente.id, periodo.id, f"Asignatura {etiqueta.upper()}", None)

        datos[etiqueta] = {
            "programa": programa, "docente": docente, "director": director, "secretario": secretario,
            "entrega": entrega, "repo": repo, "asignacion": asignacion,
        }
    return datos


class TestAislamientoDeConsultas:
    def test_listar_docentes_no_mezcla_programas(self, db_session, dos_programas_con_personal):
        d = dos_programas_con_personal
        docentes_a = listar_docentes(db_session, d["a"]["programa"].id)
        ids_a = {u.id for u in docentes_a}
        assert d["a"]["docente"].id in ids_a
        assert d["b"]["docente"].id not in ids_a

    def test_listar_usuarios_no_mezcla_programas(self, db_session, dos_programas_con_personal):
        d = dos_programas_con_personal
        usuarios_a = listar_usuarios(db_session, d["a"]["programa"].id)
        ids_a = {u.id for u in usuarios_a}
        assert d["a"]["director"].id in ids_a
        assert d["b"]["director"].id not in ids_a
        assert d["b"]["docente"].id not in ids_a

    def test_listar_entregas_no_mezcla_programas(self, db_session, dos_programas_con_personal):
        d = dos_programas_con_personal
        entregas_a = listar_entregas(db_session, d["a"]["programa"].id)
        ids_a = {e.id for e in entregas_a}
        assert d["a"]["entrega"].id in ids_a
        assert d["b"]["entrega"].id not in ids_a

    def test_listar_repositorio_asignaturas_no_mezcla_programas(self, db_session, dos_programas_con_personal):
        d = dos_programas_con_personal
        repo_a = listar_repositorio_asignaturas(db_session, d["a"]["programa"].id)
        ids_a = {r.id for r in repo_a}
        assert d["a"]["repo"].id in ids_a
        assert d["b"]["repo"].id not in ids_a


class TestAislamientoDeNotificaciones:
    def test_emails_personal_revisor_no_mezcla_programas(self, db_session, dos_programas_con_personal):
        """El hallazgo más urgente de la auditoría: antes, esta función
        devolvía TODOS los directores/secretarios/secretarias del
        sistema, sin importar programa."""
        d = dos_programas_con_personal
        emails_a = emails_personal_revisor(db_session, d["a"]["programa"].id)
        assert d["a"]["director"].email in emails_a
        assert d["a"]["secretario"].email in emails_a
        assert d["b"]["director"].email not in emails_a
        assert d["b"]["secretario"].email not in emails_a

    def test_ids_personal_revisor_no_mezcla_programas(self, db_session, dos_programas_con_personal):
        d = dos_programas_con_personal
        ids_a = ids_personal_revisor(db_session, d["a"]["programa"].id)
        assert d["a"]["director"].id in ids_a
        assert d["a"]["secretario"].id in ids_a
        assert d["b"]["director"].id not in ids_a
        assert d["b"]["secretario"].id not in ids_a


class TestAsignacionDeProgramaAutomatica:
    def test_obtener_o_crear_asignacion_usa_el_programa_del_docente(self, db_session, dos_programas_con_personal):
        """La asignación creada por el fixture debe quedar en el mismo
        programa que su docente -- nunca en otro, y nunca por un valor
        externo (el parámetro 'programa' string ya no existe)."""
        d = dos_programas_con_personal
        assert d["a"]["asignacion"].programa_id == d["a"]["programa"].id
        assert d["b"]["asignacion"].programa_id == d["b"]["programa"].id

    def test_obtener_o_crear_entrega_usa_el_programa_del_docente(self, db_session, dos_programas_con_personal):
        d = dos_programas_con_personal
        assert d["a"]["entrega"].programa_id == d["a"]["programa"].id
        assert d["b"]["entrega"].programa_id == d["b"]["programa"].id

    def test_docente_sin_programa_no_puede_crear_asignacion(self, db_session):
        rol_docente_id = _rol_id(db_session, "docente")
        docente_sin_programa = crear_usuario(
            db_session, "PYTEST Sin Programa", None, None, f"__pytest_sin_programa_{uuid.uuid4().hex[:8]}__",
            "hash", rol_docente_id,  # sin programa_id -- como la cuenta bootstrap 'admin'
        )
        periodo = periodo_activo(db_session)
        with pytest.raises(ValueError, match="programa académico"):
            obtener_o_crear_asignacion(db_session, docente_sin_programa.id, periodo.id, "Cualquier Materia", None)


class TestEdicionDeUsuarioRespetaAislamiento:
    def test_actualizar_usuario_edita_los_campos_pedidos(self, db_session, dos_programas_con_personal):
        d = dos_programas_con_personal
        actualizado = actualizar_usuario(
            db_session, d["a"]["docente"].id, nombre_completo="PYTEST Docente A Corregido", telefono="3001234567"
        )
        assert actualizado.nombre_completo == "PYTEST Docente A Corregido"
        assert actualizado.telefono == "3001234567"
        # Un docente de otro programa no debe verse afectado.
        assert d["b"]["docente"].nombre_completo != "PYTEST Docente A Corregido"

    def test_director_no_puede_editar_usuario_de_otro_programa(self, db_session, dos_programas_con_personal):
        """Reproduce exactamente el chequeo que hace
        backend.api.routers.usuarios.actualizar() antes de llamar a
        actualizar_usuario: el Director del programa A no puede editar a
        un usuario cuyo programa_id es el del programa B."""
        d = dos_programas_con_personal
        with pytest.raises(HTTPException) as exc_info:
            verificar_pertenece_a_programa(d["b"]["docente"].programa_id, d["a"]["director"])
        assert exc_info.value.status_code == 403
