# -*- coding: utf-8 -*-
"""Pruebas del flujo de recuperacion de contrasena (db.repository.
crear_token_recuperacion / consumir_token_recuperacion) contra la BD real
de desarrollo. Usa la fixture db_session (rollback al final)."""
import uuid
from datetime import datetime, timedelta

import pytest

from db.auth import validar_longitud_password
from db.models import Programa, TokenRecuperacionPassword
from db.repository import consumir_token_recuperacion, crear_token_recuperacion, crear_usuario, listar_roles


def _rol_id(session, nombre: str) -> int:
    return next(r.id for r in listar_roles(session) if r.nombre == nombre)


def _crear_docente(session):
    programa = Programa(nombre=f"PYTEST Prog {uuid.uuid4().hex[:6]}", codigo=f"pytest-{uuid.uuid4().hex[:8]}")
    session.add(programa)
    session.flush()
    return crear_usuario(
        session, "PYTEST Recuperacion", None, f"recuperacion_{uuid.uuid4().hex[:8]}@example.com",
        f"__pytest_recuperacion_{uuid.uuid4().hex[:8]}__", "hash-falso", _rol_id(session, "docente"),
        programa_id=programa.id,
    )


class TestTokenRecuperacion:
    def test_token_generado_solo_persiste_el_hash(self, db_session):
        docente = _crear_docente(db_session)
        token = crear_token_recuperacion(db_session, docente.id)

        fila = db_session.query(TokenRecuperacionPassword).filter_by(usuario_id=docente.id).one()
        assert fila.token_hash != token
        assert len(fila.token_hash) == 64  # sha256 hexdigest
        assert fila.usado_en is None

    def test_token_valido_se_puede_canjear_una_vez(self, db_session):
        docente = _crear_docente(db_session)
        token = crear_token_recuperacion(db_session, docente.id)

        usuario = consumir_token_recuperacion(db_session, token)
        assert usuario is not None
        assert usuario.id == docente.id

        # Segundo canje del MISMO token debe fallar (uso unico).
        assert consumir_token_recuperacion(db_session, token) is None

    def test_token_invalido_retorna_none(self, db_session):
        assert consumir_token_recuperacion(db_session, "token-que-no-existe") is None

    def test_token_vencido_retorna_none(self, db_session):
        docente = _crear_docente(db_session)
        token = crear_token_recuperacion(db_session, docente.id)

        fila = db_session.query(TokenRecuperacionPassword).filter_by(usuario_id=docente.id).one()
        fila.expira_en = datetime.utcnow() - timedelta(minutes=1)
        db_session.flush()

        assert consumir_token_recuperacion(db_session, token) is None

    def test_canjear_un_token_invalida_los_demas_del_mismo_usuario(self, db_session):
        """Si el usuario pidio el enlace dos veces (dos tokens vigentes a
        la vez), canjear cualquiera de los dos debe dejar al otro
        inservible -- no deben quedar dos enlaces activos en paralelo."""
        docente = _crear_docente(db_session)
        token_1 = crear_token_recuperacion(db_session, docente.id)
        token_2 = crear_token_recuperacion(db_session, docente.id)

        assert consumir_token_recuperacion(db_session, token_1) is not None
        # token_2 seguia vigente antes del canje de token_1, pero queda
        # invalidado como efecto secundario de ese canje.
        assert consumir_token_recuperacion(db_session, token_2) is None


class TestValidarLongitudPassword:
    def test_password_corta_rechazada(self):
        with pytest.raises(ValueError):
            validar_longitud_password("corta12")

    def test_password_de_8_caracteres_aceptada(self):
        validar_longitud_password("12345678")  # no debe lanzar
