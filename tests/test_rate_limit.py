# -*- coding: utf-8 -*-
"""Pruebas del limitador de intentos de login, respaldado en Postgres
(backend/core/rate_limit.py + tabla intentos_login_fallidos). Usa la
fixture db_session (BD real, con rollback) porque el limitador ya no
vive en memoria del proceso -- se movió a la base de datos precisamente
para que el límite sea correcto sin importar cuántos workers de
uvicorn corran (ver docstring del módulo)."""
import uuid
from datetime import datetime, timedelta

from backend.core import rate_limit


def _clave() -> str:
    return f"__pytest_ratelimit_{uuid.uuid4().hex[:8]}__"


class TestRateLimit:
    def test_usuario_nuevo_no_esta_bloqueado(self, db_session):
        clave = _clave()
        assert rate_limit.bloqueado(db_session, clave) is False
        assert rate_limit.intentos_restantes(db_session, clave) == rate_limit.MAX_INTENTOS

    def test_se_bloquea_tras_max_intentos_fallidos(self, db_session):
        clave = _clave()
        for _ in range(rate_limit.MAX_INTENTOS - 1):
            rate_limit.registrar_intento_fallido(db_session, clave)
            assert rate_limit.bloqueado(db_session, clave) is False
        rate_limit.registrar_intento_fallido(db_session, clave)
        assert rate_limit.bloqueado(db_session, clave) is True

    def test_limpiar_desbloquea_de_inmediato(self, db_session):
        clave = _clave()
        for _ in range(rate_limit.MAX_INTENTOS):
            rate_limit.registrar_intento_fallido(db_session, clave)
        assert rate_limit.bloqueado(db_session, clave) is True
        rate_limit.limpiar(db_session, clave)
        assert rate_limit.bloqueado(db_session, clave) is False

    def test_intentos_de_usuarios_distintos_no_se_mezclan(self, db_session):
        clave_a, clave_b = _clave(), _clave()
        for _ in range(rate_limit.MAX_INTENTOS):
            rate_limit.registrar_intento_fallido(db_session, clave_a)
        assert rate_limit.bloqueado(db_session, clave_a) is True
        assert rate_limit.bloqueado(db_session, clave_b) is False

    def test_ventana_expirada_libera_el_bloqueo(self, db_session):
        clave = _clave()
        for _ in range(rate_limit.MAX_INTENTOS):
            rate_limit.registrar_intento_fallido(db_session, clave)
        assert rate_limit.bloqueado(db_session, clave) is True

        # Simula que la ventana de 15 minutos ya expiró, retrocediendo el
        # timestamp guardado en vez de manipular el reloj del sistema.
        fila = db_session.get(rate_limit.IntentoLoginFallido, clave)
        fila.primer_intento_en = datetime.utcnow() - timedelta(seconds=rate_limit.VENTANA_SEGUNDOS + 1)
        db_session.flush()

        assert rate_limit.bloqueado(db_session, clave) is False

    def test_dos_workers_comparten_el_mismo_contador(self, db_session):
        """Reproduce exactamente el problema que motivó este fix: con el
        limitador en memoria, dos 'workers' (dos procesos) no
        compartían contador. Aquí se simulan como dos sesiones
        distintas sobre la MISMA conexión de la fixture -- ambas deben
        ver el mismo estado en la tabla, a diferencia del diccionario en
        memoria de antes."""
        from sqlalchemy.orm import sessionmaker

        clave = _clave()
        SesionWorker = sessionmaker(bind=db_session.get_bind(), autoflush=False, expire_on_commit=False)
        sesion_worker_1 = SesionWorker()
        sesion_worker_2 = SesionWorker()
        try:
            for _ in range(rate_limit.MAX_INTENTOS):
                rate_limit.registrar_intento_fallido(sesion_worker_1, clave)
            # El "worker 2" (otra sesión) debe ver el bloqueo tambien.
            assert rate_limit.bloqueado(sesion_worker_2, clave) is True
        finally:
            sesion_worker_1.close()
            sesion_worker_2.close()
