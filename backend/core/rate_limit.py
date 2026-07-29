# -*- coding: utf-8 -*-
"""Limitador de intentos de login en memoria (por proceso): protege
/api/auth/login contra fuerza bruta y credential stuffing sin depender
de infraestructura externa (Redis, etc.).

Limitacion aceptada: si el backend llegara a correr en varias
replicas/procesos, cada una lleva su propio contador (no es un limite
distribuido). Para el tamano de despliegue actual (un solo proceso
uvicorn en el VPS) esto es suficiente."""
import time
from collections import defaultdict
from threading import Lock

MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 15 * 60

_intentos: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _limpiar_viejos(clave: str, ahora: float) -> None:
    _intentos[clave] = [t for t in _intentos[clave] if ahora - t < VENTANA_SEGUNDOS]
    if not _intentos[clave]:
        _intentos.pop(clave, None)


def intentos_restantes(clave: str) -> int:
    with _lock:
        ahora = time.time()
        _limpiar_viejos(clave, ahora)
        return max(0, MAX_INTENTOS - len(_intentos.get(clave, [])))


def bloqueado(clave: str) -> bool:
    return intentos_restantes(clave) <= 0


def registrar_intento_fallido(clave: str) -> None:
    with _lock:
        ahora = time.time()
        _limpiar_viejos(clave, ahora)
        _intentos[clave].append(ahora)


def limpiar(clave: str) -> None:
    with _lock:
        _intentos.pop(clave, None)
