"""Endpoints de consulta para el Director del Programa y el Secretario
Academico: resumen y detalle de cada docente."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db, requiere_roles
from backend.core.config import settings
from backend.schemas.docente import (
    AsignacionOut,
    DocenteDetalleOut,
    DocenteResumenOut,
    InformeCorteOut,
)
from db.repository import listar_docentes

router = APIRouter(prefix="/api/docentes", tags=["docentes"])


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
def listar(db: Session = Depends(get_db), _usuario=Depends(requiere_roles("director", "secretario"))):
    docentes = listar_docentes(db)
    salida = []
    for d in docentes:
        asign_periodo = [a for a in d.asignaciones if a.periodo.nombre == settings.PERIODO_ACTUAL]
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
def detalle(docente_id: int, db: Session = Depends(get_db), _usuario=Depends(requiere_roles("director", "secretario"))):
    docentes = listar_docentes(db)
    docente = next((d for d in docentes if d.id == docente_id), None)
    if docente is None:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    asign_periodo = [a for a in docente.asignaciones if a.periodo.nombre == settings.PERIODO_ACTUAL]
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
