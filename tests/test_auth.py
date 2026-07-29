# -*- coding: utf-8 -*-
"""Pruebas unitarias de hashing de contrasenas y JWT. No requieren
base de datos."""
import pytest
from jose import JWTError
from pydantic import ValidationError

from backend.core.security import crear_access_token, decodificar_access_token
from backend.schemas.usuario import UsuarioCreate
from db.auth import hash_password, validar_longitud_password, verificar_password


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


class TestValidarLongitudPassword:
    def test_password_menor_a_8_caracteres_rechazada(self):
        with pytest.raises(ValueError):
            validar_longitud_password("abc123")

    def test_password_de_8_o_mas_caracteres_aceptada(self):
        validar_longitud_password("abcd1234")  # no debe lanzar


class TestUsuarioCreateSchema:
    _DATOS_BASE = dict(
        nombre_completo="PYTEST Usuario", cedula="123", email="pytest@example.com",
        username="pytest_user", password="contraseña-larga", rol="docente",
    )

    def test_cedula_y_correo_son_obligatorios(self):
        UsuarioCreate(**self._DATOS_BASE)  # no debe lanzar: todos los campos requeridos presentes

        with pytest.raises(ValidationError):
            UsuarioCreate(**{**self._DATOS_BASE, "cedula": None})
        with pytest.raises(ValidationError):
            UsuarioCreate(**{**self._DATOS_BASE, "email": None})

    def test_telefono_es_opcional(self):
        # No debe lanzar sin telefono ni con telefono presente.
        UsuarioCreate(**self._DATOS_BASE)
        UsuarioCreate(**{**self._DATOS_BASE, "telefono": "3001234567"})

    def test_password_corta_rechazada_por_el_schema(self):
        with pytest.raises(ValidationError):
            UsuarioCreate(**{**self._DATOS_BASE, "password": "corta"})
