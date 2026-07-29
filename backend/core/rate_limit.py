# -*- coding: utf-8 -*-
"""Limitador de intentos de login, respaldado en Postgres
(IntentoLoginFallido, db/models.py): protege /api/auth/login contra
fuerza bruta y credential stuffing.

Se guarda en la base de datos -- y no en un diccionario en memoria del
proceso -- porque el backend corre con varios workers de uvicorn
(--workers, ver docs/DESPLIEGUE_VPS.md): cada worker es un proceso de
sistema operativo con su propia memoria, así que un contador en memoria
daría un límite efectivo de N_workers x MAX_INTENTOS en vez de
MAX_INTENTOS -- exactamente el problema detectado en la revisión de
escalabilidad. Con la tabla en Postgres, todos los workers comparten el
mismo contador real."""
from datetime import datetime, timedelta

from db.models import IntentoLoginFallido

MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 15 * 60


def _fila(session, clave: str) -> IntentoLoginFallido | None:
    return session.get(IntentoLoginFallido, clave)


def _ventana_vigente(fila: IntentoLoginFallido, ahora: datetime) -> bool:
    return ahora - fila.primer_intento_en < timedelta(seconds=VENTANA_SEGUNDOS)


def intentos_restantes(session, clave: str) -> int:
    fila = _fila(session, clave)
    if fila is None or not _ventana_vigente(fila, datetime.utcnow()):
        return MAX_INTENTOS
    return max(0, MAX_INTENTOS - fila.intentos)


def bloqueado(session, clave: str) -> bool:
    return intentos_restantes(session, clave) <= 0


def registrar_intento_fallido(session, clave: str) -> None:
    ahora = datetime.utcnow()
    fila = _fila(session, clave)
    if fila is None:
        session.add(IntentoLoginFallido(clave=clave, intentos=1, primer_intento_en=ahora))
    elif not _ventana_vigente(fila, ahora):
        fila.intentos = 1
        fila.primer_intento_en = ahora
    else:
        fila.intentos += 1
    session.commit()


def limpiar(session, clave: str) -> None:
    fila = _fila(session, clave)
    if fila is not None:
        session.delete(fila)
        session.commit()
