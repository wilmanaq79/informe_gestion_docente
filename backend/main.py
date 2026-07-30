"""
API REST -- Sistema de Gestión y Autoevaluación Docente.
Programa de Ingeniería de Sistemas, Universidad del Pacífico.

Ejecutar (desde la raíz del proyecto):
    uvicorn backend.main:app --reload --port 8000

Documentación interactiva: http://localhost:8000/docs
"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.deps import requiere_consentimiento, requiere_password_actualizada
from backend.api.routers import (
    auth,
    calendario,
    consentimiento,
    dashboard,
    docentes,
    entregas,
    formatos_institucionales,
    informes,
    notificaciones,
    periodos,
    repositorio_asignaturas,
    reportes,
    usuarios,
)
from backend.core.config import settings
from backend.core.limite_tamano import limitar_tamano_request

app = FastAPI(
    title="API Gestión Docente — Ing. de Sistemas UNPA",
    description=(
        "API para el sistema de Gestión y Autoevaluación Docente del "
        "Programa de Ingeniería de Sistemas, Universidad del Pacífico."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(limitar_tamano_request)

# auth y consentimiento quedan SIN los gates de negocio: deben seguir
# funcionando antes de que el usuario cambie su contrasena temporal o
# acepte la politica (login, /auth/me, cambiar-password, recuperacion,
# consultar y aceptar la politica). Todos los demas routers de negocio
# exigen primero una contrasena ya rotada y luego la politica vigente.
app.include_router(auth.router)
app.include_router(consentimiento.router)

_gate = [Depends(requiere_password_actualizada), Depends(requiere_consentimiento)]
app.include_router(informes.router, dependencies=_gate)
app.include_router(docentes.router, dependencies=_gate)
app.include_router(usuarios.router, dependencies=_gate)
app.include_router(reportes.router, dependencies=_gate)
app.include_router(dashboard.router, dependencies=_gate)
app.include_router(periodos.router, dependencies=_gate)
app.include_router(calendario.router, dependencies=_gate)
app.include_router(entregas.router, dependencies=_gate)
app.include_router(notificaciones.router, dependencies=_gate)
app.include_router(repositorio_asignaturas.router, dependencies=_gate)
app.include_router(formatos_institucionales.router, dependencies=_gate)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
