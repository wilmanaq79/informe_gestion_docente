# -*- coding: utf-8 -*-
"""Pruebas unitarias de control de acceso por rol
(backend/api/deps.py:requiere_roles). No requieren base de datos ni
HTTP real: se construye un Usuario "falso" minimo con el atributo que
la dependencia realmente lee (usuario.rol.nombre)."""
import pytest
from fastapi import HTTPException

from backend.api.deps import requiere_roles


class _RolFalso:
    def __init__(self, nombre):
        self.nombre = nombre


class _UsuarioFalso:
    def __init__(self, rol_nombre):
        self.rol = _RolFalso(rol_nombre)


class TestRequiereRoles:
    def test_rol_permitido_pasa(self):
        dependencia = requiere_roles("director", "secretario")
        usuario = _UsuarioFalso("director")
        assert dependencia(usuario) is usuario

    def test_rol_no_permitido_lanza_403(self):
        dependencia = requiere_roles("director", "secretario")
        usuario = _UsuarioFalso("docente")
        with pytest.raises(HTTPException) as exc_info:
            dependencia(usuario)
        assert exc_info.value.status_code == 403

    def test_lista_vacia_de_roles_rechaza_a_cualquiera(self):
        dependencia = requiere_roles()
        with pytest.raises(HTTPException):
            dependencia(_UsuarioFalso("director"))

    def test_mensaje_de_error_menciona_los_roles_permitidos(self):
        dependencia = requiere_roles("director", "secretario")
        with pytest.raises(HTTPException) as exc_info:
            dependencia(_UsuarioFalso("docente"))
        assert "director" in exc_info.value.detail
        assert "secretario" in exc_info.value.detail
