# -*- coding: utf-8 -*-
"""Pruebas unitarias del limitador de intentos de login en memoria
(backend/core/rate_limit.py). No requieren base de datos."""
from backend.core import rate_limit


def _limpiar(clave: str):
    rate_limit.limpiar(clave)


class TestRateLimit:
    def test_usuario_nuevo_no_esta_bloqueado(self):
        clave = "usuario_prueba_1"
        _limpiar(clave)
        assert rate_limit.bloqueado(clave) is False
        assert rate_limit.intentos_restantes(clave) == rate_limit.MAX_INTENTOS

    def test_se_bloquea_tras_max_intentos_fallidos(self):
        clave = "usuario_prueba_2"
        _limpiar(clave)
        for _ in range(rate_limit.MAX_INTENTOS - 1):
            rate_limit.registrar_intento_fallido(clave)
            assert rate_limit.bloqueado(clave) is False
        rate_limit.registrar_intento_fallido(clave)
        assert rate_limit.bloqueado(clave) is True

    def test_limpiar_desbloquea_de_inmediato(self):
        clave = "usuario_prueba_3"
        _limpiar(clave)
        for _ in range(rate_limit.MAX_INTENTOS):
            rate_limit.registrar_intento_fallido(clave)
        assert rate_limit.bloqueado(clave) is True
        rate_limit.limpiar(clave)
        assert rate_limit.bloqueado(clave) is False

    def test_intentos_de_usuarios_distintos_no_se_mezclan(self):
        clave_a, clave_b = "usuario_prueba_a", "usuario_prueba_b"
        _limpiar(clave_a)
        _limpiar(clave_b)
        for _ in range(rate_limit.MAX_INTENTOS):
            rate_limit.registrar_intento_fallido(clave_a)
        assert rate_limit.bloqueado(clave_a) is True
        assert rate_limit.bloqueado(clave_b) is False

    def test_ventana_expirada_libera_el_bloqueo(self, monkeypatch):
        clave = "usuario_prueba_ventana"
        _limpiar(clave)
        tiempo_actual = [1_000_000.0]
        monkeypatch.setattr(rate_limit.time, "time", lambda: tiempo_actual[0])

        for _ in range(rate_limit.MAX_INTENTOS):
            rate_limit.registrar_intento_fallido(clave)
        assert rate_limit.bloqueado(clave) is True

        # Avanza el reloj mas alla de la ventana de bloqueo.
        tiempo_actual[0] += rate_limit.VENTANA_SEGUNDOS + 1
        assert rate_limit.bloqueado(clave) is False
