"""Endpoints de consulta para el Director del Programa y el Secretario
Academico: resumen y detalle de cada docente. Filtrables por Año y
Semestre (opcional; si se omite, incluye ambos semestres del Año)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_db, requiere_roles
from backend.schemas.docente import (
    AsignacionOut,
    DocenteDetalleOut,
    DocenteResumenOut,
    InformeCorteOut,
)
from db.repository import listar_docentes, periodo_activo, periodo_mas_reciente, resolver_periodo_ids

router = APIRouter(prefix="/api/docentes", tags=["docentes"])


def _resolver_periodo_ids(db: Session, anio: int | None, semestre: int | None) -> list[int]:
    if anio is None:
        p = periodo_activo(db) or periodo_mas_reciente(db)
        if p is None:
            return []
        anio = p.anio
        if semestre is None:
            semestre = p.semestre
    return resolver_periodo_ids(db, anio, semestre)


def _informe_out(informe) -> InformeCorteOut:
    return InformeCorteOut(
        id=informe.id,
        corte_numero=informe.corte.numero,
        corte_nombre=informe.corte.nombre,
        matriculados=informe.matriculados,
        asistencia_regular=informe.asistencia_regular,
        evaluados=informe.evaluados,
        aprobaron=informe.aprobaron,
        es_estimado=informe.es_estimado,
        promedio=float(informe.promedio) if informe.promedio is not None else None,
        mediana=float(informe.mediana) if informe.mediana is not None else None,
        desviacion=float(informe.desviacion) if informe.desviacion is not None else None,
    )


@router.get("", response_model=list[DocenteResumenOut])
def listar(
    anio: int | None = Query(None, description="Año academico. Si se omite, usa el periodo actual."),
    semestre: int | None = Query(None, ge=1, le=2, description="1 o 2. Si se omite junto con anio, usa el semestre actual; si solo se omite semestre, incluye ambos."),
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    periodo_ids = _resolver_periodo_ids(db, anio, semestre)
    docentes = listar_docentes(db)
    salida = []
    for d in docentes:
        asign_periodo = [a for a in d.asignaciones if a.periodo_id in periodo_ids]
        total_informes = sum(len(a.informes) for a in asign_periodo)
        ultimo_corte = max((i.corte.numero for a in asign_periodo for i in a.informes), default=None)
        salida.append(
            DocenteResumenOut(
                id=d.id,
                nombre_completo=d.nombre_completo,
                materias_periodo=len(asign_periodo),
                informes_cargados=total_informes,
                ultimo_corte=ultimo_corte,
            )
        )
    return salida


@router.get("/{docente_id}", response_model=DocenteDetalleOut)
def detalle(
    docente_id: int,
    anio: int | None = Query(None, description="Año academico. Si se omite, usa el periodo actual."),
    semestre: int | None = Query(None, ge=1, le=2, description="1 o 2. Si se omite junto con anio, usa el semestre actual; si solo se omite semestre, incluye ambos."),
    db: Session = Depends(get_db),
    _usuario=Depends(requiere_roles("director", "secretario")),
):
    periodo_ids = _resolver_periodo_ids(db, anio, semestre)
    docentes = listar_docentes(db)
    docente = next((d for d in docentes if d.id == docente_id), None)
    if docente is None:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    asign_periodo = [a for a in docente.asignaciones if a.periodo_id in periodo_ids]
    asignaciones = [
        AsignacionOut(
            id=a.id,
            asignatura=a.asignatura,
            grupo=a.grupo,
            programa=a.programa,
            informes=[_informe_out(i) for i in sorted(a.informes, key=lambda x: x.corte.numero)],
        )
        for a in asign_periodo
    ]
    return DocenteDetalleOut(
        id=docente.id,
        nombre_completo=docente.nombre_completo,
        cedula=docente.cedula,
        email=docente.email,
        asignaciones=asignaciones,
    )
