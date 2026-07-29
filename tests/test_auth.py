# -*- coding: utf-8 -*-
"""Pruebas unitarias de hashing de contrasenas y JWT. No requieren
base de datos."""
import pytest
from jose import JWTError

from backend.core.security import crear_access_token, decodificar_access_token
from db.auth import hash_password, verificar_password


class TestHashPassword:
    def test_hash_no_guarda_la_contrasena_en_texto_plano(self):
        hashed = hash_password("miclave123")
        assert hashed != "miclave123"

    def test_verificar_password_correcta(self):
        hashed = hash_password("miclave123")
        assert verificar_password("miclave123", hashed) is True

    def test_verificar_password_incorrecta(self):
        hashed = hash_password("miclave123")
        assert verificar_password("otraclave", hashed) is False

    def test_dos_hashes_de_la_misma_password_son_distintos(self):
        # bcrypt usa un salt aleatorio por llamada -- confirma que no se
        # esta usando un hash determinista (MD5/SHA sin salt).
        assert hash_password("miclave123") != hash_password("miclave123")


class TestJWT:
    def test_token_valido_decodifica_al_mismo_payload(self):
        token = crear_access_token(usuario_id=42, username="wilman", rol="docente")
        payload = decodificar_access_token(token)
        assert payload["sub"] == "42"
        assert payload["username"] == "wilman"
        assert payload["rol"] == "docente"

    def test_token_manipulado_falla_al_decodificar(self):
        token = crear_access_token(usuario_id=1, username="x", rol="docente")
        manipulado = token[:-4] + "abcd"
        with pytest.raises(JWTError):
            decodificar_access_token(manipulado)
