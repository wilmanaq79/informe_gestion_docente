# -*- coding: utf-8 -*-
"""Middleware ASGI que rechaza cualquier request cuyo Content-Length
declarado supere el maximo permitido -- protege TODOS los endpoints que
reciben archivos (entregas, repositorio de asignaturas, e informes.py,
que procesa Excel/PDF directamente en memoria sin pasar por
agente_notas.almacenamiento) contra un intento de agotar memoria/disco
subiendo un archivo enorme."""
from starlette.requests import Request
from starlette.responses import JSONResponse

TAMANO_MAXIMO_REQUEST_BYTES = 20 * 1024 * 1024  # 20 MB: cubre el archivo (15 MB) + overhead de multipart


async def limitar_tamano_request(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > TAMANO_MAXIMO_REQUEST_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"La solicitud pesa más de "
                            f"{TAMANO_MAXIMO_REQUEST_BYTES // (1024 * 1024)} MB, el máximo permitido."
                        )
                    },
                )
        except ValueError:
            pass
    return await call_next(request)
