# -*- coding: utf-8 -*-
"""Pruebas de integracion (BD real, con rollback) del bloqueo de
aprobacion de una entrega sin revision manual confirmada -- la funcion
agregada para que Director/Secretario/Secretaria del Programa deban
abrir el archivo antes de poder confirmar y aprobar (ver
db/repository.py: marcar_documento_visto, confirmar_revision_documento,
aprobar_entrega)."""
import uuid

import pytest

from db.repository import (
    agregar_documento_entrega,
    aprobar_entrega,
    confirmar_revision_documento,
    corte_por_numero,
    crear_usuario,
    listar_roles,
    marcar_documento_visto,
    obtener_o_crear_entrega,
    periodo_activo,
)


def _rol_id(session, nombre: str) -> int:
    return next(r.id for r in listar_roles(session) if r.nombre == nombre)


@pytest.fixture()
def entrega_con_documento_sin_firma(db_session):
    """Crea un docente + un director de prueba, una entrega, y un
    documento con firma_detectada=False (necesita revision manual).
    Devuelve (entrega, documento, director)."""
    periodo = periodo_activo(db_session)
    assert periodo is not None
    corte = corte_por_numero(db_session, 1)
    assert corte is not None

    sufijo = uuid.uuid4().hex[:8]
    docente = crear_usuario(
        db_session, "PYTEST Gate Docente", None, None, f"__pytest_gate_doc_{sufijo}__",
        "hash", _rol_id(db_session, "docente"),
    )
    director = crear_usuario(
        db_session, "PYTEST Gate Director", None, None, f"__pytest_gate_dir_{sufijo}__",
        "hash", _rol_id(db_session, "director"),
    )
    entrega = obtener_o_crear_entrega(db_session, docente.id, periodo.id, corte.id)
    documento = agregar_documento_entrega(
        db_session, entrega.id, "lista_asistencia", "asistencia.pdf", "ruta/falsa.pdf", 1024,
        firma_detectada=False, firma_confianza="media", firma_detalle="sin mencion de firma",
    )
    return entrega, documento, director


class TestConfirmarRevision:
    def test_no_se_puede_confirmar_sin_haber_abierto_el_archivo(self, db_session, entrega_con_documento_sin_firma):
        _entrega, documento, director = entrega_con_documento_sin_firma
        with pytest.raises(ValueError, match="abrir o descargar"):
            confirmar_revision_documento(db_session, documento.id, director.id)

    def test_se_puede_confirmar_despues_de_marcar_visto(self, db_session, entrega_con_documento_sin_firma):
        _entrega, documento, director = entrega_con_documento_sin_firma
        marcar_documento_visto(db_session, documento.id)
        confirmado = confirmar_revision_documento(db_session, documento.id, director.id)
        assert confirmado.revisado_manualmente is True
        assert confirmado.revisado_por_id == director.id

    def test_marcar_visto_es_idempotente_no_pisa_la_fecha(self, db_session, entrega_con_documento_sin_firma):
        _entrega, documento, _director = entrega_con_documento_sin_firma
        marcar_documento_visto(db_session, documento.id)
        primera_fecha = db_session.get(type(documento), documento.id).visto_en
        marcar_documento_visto(db_session, documento.id)
        segunda_fecha = db_session.get(type(documento), documento.id).visto_en
        assert primera_fecha == segunda_fecha


class TestAprobarEntregaConGate:
    def test_no_se_puede_aprobar_sin_confirmar_la_revision_manual(self, db_session, entrega_con_documento_sin_firma):
        entrega, _documento, director = entrega_con_documento_sin_firma
        with pytest.raises(ValueError, match="revisión manual"):
            aprobar_entrega(db_session, entrega.id, director.id)

    def test_se_puede_aprobar_despues_de_abrir_y_confirmar(self, db_session, entrega_con_documento_sin_firma):
        entrega, documento, director = entrega_con_documento_sin_firma
        marcar_documento_visto(db_session, documento.id)
        confirmar_revision_documento(db_session, documento.id, director.id)

        entrega_aprobada = aprobar_entrega(db_session, entrega.id, director.id, "todo en orden")
        assert entrega_aprobada.estado == "aprobado"

    def test_documento_firmado_no_necesita_confirmacion(self, db_session):
        """Un documento con firma_detectada=True NO debe bloquear la
        aprobacion, aunque nunca se haya marcado como visto/confirmado."""
        periodo = periodo_activo(db_session)
        corte = corte_por_numero(db_session, 1)
        sufijo = uuid.uuid4().hex[:8]
        docente = crear_usuario(
            db_session, "PYTEST Firmado Docente", None, None, f"__pytest_firmado_{sufijo}__",
            "hash", _rol_id(db_session, "docente"),
        )
        director = crear_usuario(
            db_session, "PYTEST Firmado Director", None, None, f"__pytest_firmado_dir_{sufijo}__",
            "hash", _rol_id(db_session, "director"),
        )
        entrega = obtener_o_crear_entrega(db_session, docente.id, periodo.id, corte.id)
        agregar_documento_entrega(
            db_session, entrega.id, "lista_asistencia", "firmada.pdf", "ruta/falsa2.pdf", 1024,
            firma_detectada=True, firma_confianza="alta", firma_detalle="firma digital detectada",
        )

        entrega_aprobada = aprobar_entrega(db_session, entrega.id, director.id)
        assert entrega_aprobada.estado == "aprobado"
