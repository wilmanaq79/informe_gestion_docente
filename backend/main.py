"""
API REST -- Sistema de Gestión y Autoevaluación Docente.
Programa de Ingeniería de Sistemas, Universidad del Pacífico.

Ejecutar (desde la raíz del proyecto):
    uvicorn backend.main:app --reload --port 8000

Documentación interactiva: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import (
    auth,
    calendario,
    dashboard,
    docentes,
    entregas,
    informes,
    notificaciones,
    periodos,
    repositorio_asignaturas,
    reportes,
    usuarios,
)
from backend.core.config import settings

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

app.include_router(auth.router)
app.include_router(informes.router)
app.include_router(docentes.router)
app.include_router(usuarios.router)
app.include_router(reportes.router)
app.include_router(dashboard.router)
app.include_router(periodos.router)
app.include_router(calendario.router)
app.include_router(entregas.router)
app.include_router(notificaciones.router)
app.include_router(repositorio_asignaturas.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
