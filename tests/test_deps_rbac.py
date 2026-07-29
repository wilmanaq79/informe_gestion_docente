# -*- coding: utf-8 -*-
"""Pruebas unitarias de control de acceso por rol
(backend/api/deps.py:requiere_roles). No requieren base de datos ni
HTTP real: se construye un Usuario "falso" minimo con el atributo que
la dependencia realmente lee (usuario.rol.nombre)."""
import pytest
from fastapi import HTTPException

from backend.api.deps import requiere_password_actualizada, requiere_roles, verificar_pertenece_a_programa


class _RolFalso:
    def __init__(self, nombre):
        self.nombre = nombre


class _UsuarioFalso:
    def __init__(self, rol_nombre, programa_id=None, debe_cambiar_password=False):
        self.rol = _RolFalso(rol_nombre)
        self.programa_id = programa_id
        self.debe_cambiar_password = debe_cambiar_password


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


class TestVerificarPerteneceAPrograma:
    def test_mismo_programa_pasa(self):
        usuario = _UsuarioFalso("director", programa_id=1)
        verificar_pertenece_a_programa(1, usuario)  # no debe lanzar

    def test_programa_distinto_lanza_403(self):
        usuario = _UsuarioFalso("director", programa_id=1)
        with pytest.raises(HTTPException) as exc_info:
            verificar_pertenece_a_programa(2, usuario)
        assert exc_info.value.status_code == 403

    def test_usuario_sin_programa_siempre_rechazado(self):
        # La cuenta bootstrap (db/seed.py) no pertenece a ningun programa
        # real -- no debe poder "colarse" como si perteneciera a uno.
        usuario = _UsuarioFalso("director", programa_id=None)
        with pytest.raises(HTTPException):
            verificar_pertenece_a_programa(1, usuario)
        with pytest.raises(HTTPException):
            verificar_pertenece_a_programa(None, usuario)


class TestRequierePasswordActualizada:
    def test_password_ya_actualizada_pasa(self):
        usuario = _UsuarioFalso("docente", debe_cambiar_password=False)
        assert requiere_password_actualizada(usuario) is usuario

    def test_password_temporal_lanza_403(self):
        usuario = _UsuarioFalso("docente", debe_cambiar_password=True)
        with pytest.raises(HTTPException) as exc_info:
            requiere_password_actualizada(usuario)
        assert exc_info.value.status_code == 403

    def test_aplica_a_los_4_roles_por_igual(self):
        for rol in ("docente", "director", "secretario", "secretaria_programa"):
            usuario = _UsuarioFalso(rol, debe_cambiar_password=True)
            with pytest.raises(HTTPException):
                requiere_password_actualizada(usuario)
