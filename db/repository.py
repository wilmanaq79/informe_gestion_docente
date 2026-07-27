"""Funciones de acceso a datos (capa de repositorio) sobre los modelos de
db/models.py. Mantiene las consultas SQLAlchemy fuera de las vistas de
Streamlit."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from db.models import (
    AsignacionAcademica,
    Corte,
    InformeCorte,
    NotaEstudiante,
    PeriodoAcademico,
    Rol,
    Usuario,
)


def obtener_o_crear_periodo(session, nombre: str) -> PeriodoAcademico:
    periodo = session.scalar(select(PeriodoAcademico).where(PeriodoAcademico.nombre == nombre))
    if periodo is None:
        periodo = PeriodoAcademico(nombre=nombre)
        session.add(periodo)
        session.commit()
    return periodo


def periodo_mas_reciente(session) -> PeriodoAcademico | None:
    return session.scalar(select(PeriodoAcademico).order_by(PeriodoAcademico.id.desc()))


def obtener_o_crear_asignacion(
    session, docente_id: int, periodo_id: int, asignatura: str, programa: str | None, grupo: str | None
) -> AsignacionAcademica:
    stmt = select(AsignacionAcademica).where(
        AsignacionAcademica.docente_id == docente_id,
        AsignacionAcademica.periodo_id == periodo_id,
        AsignacionAcademica.asignatura == asignatura,
        AsignacionAcademica.grupo == grupo,
    )
    asignacion = session.scalar(stmt)
    if asignacion is None:
        asignacion = AsignacionAcademica(
            docente_id=docente_id,
            periodo_id=periodo_id,
            asignatura=asignatura,
            programa=programa,
            grupo=grupo,
        )
        session.add(asignacion)
        session.commit()
    return asignacion


def guardar_informe_corte(
    session,
    asignacion_id: int,
    corte_numero: int,
    resumen: dict,
    promedio: float,
    mediana: float,
    desviacion: float,
    filas_notas: list[dict],
) -> InformeCorte:
    """Crea o actualiza (upsert) el informe de un corte para una asignacion,
    y reemplaza el detalle de notas_estudiantes asociado."""
    corte = session.scalar(select(Corte).where(Corte.numero == corte_numero))
    if corte is None:
        raise ValueError(f"Corte {corte_numero} no existe en el catalogo. Ejecuta db/seed.py")

    informe = session.scalar(
        select(InformeCorte).where(
            InformeCorte.asignacion_id == asignacion_id, InformeCorte.corte_id == corte.id
        )
    )
    if informe is None:
        informe = InformeCorte(asignacion_id=asignacion_id, corte_id=corte.id)
        session.add(informe)

    informe.matriculados = resumen["matriculados"]
    informe.asistencia_regular = resumen["asistencia_regular"]
    informe.evaluados = resumen["evaluados"]
    informe.aprobaron = resumen["aprobaron"]
    informe.es_estimado = resumen["es_estimado"]
    informe.promedio = promedio
    informe.mediana = mediana
    informe.desviacion = desviacion
    informe.generado_en = datetime.utcnow()
    session.flush()

    session.query(NotaEstudiante).filter(NotaEstudiante.informe_corte_id == informe.id).delete()
    for fila in filas_notas:
        session.add(NotaEstudiante(informe_corte_id=informe.id, **fila))

    session.commit()
    session.refresh(informe)
    return informe


def listar_docentes(session) -> list[Usuario]:
    rol_docente = session.scalar(select(Rol).where(Rol.nombre == "docente"))
    if rol_docente is None:
        return []
    stmt = (
        select(Usuario)
        .where(Usuario.rol_id == rol_docente.id, Usuario.activo.is_(True))
        .options(
            selectinload(Usuario.asignaciones)
            .selectinload(AsignacionAcademica.informes)
            .selectinload(InformeCorte.corte)
        )
        .order_by(Usuario.nombre_completo)
    )
    return list(session.scalars(stmt).unique())


def listar_usuarios(session) -> list[Usuario]:
    return list(session.scalars(select(Usuario).options(selectinload(Usuario.rol)).order_by(Usuario.nombre_completo)))


def listar_roles(session) -> list[Rol]:
    return list(session.scalars(select(Rol).order_by(Rol.nombre)))


def crear_usuario(session, nombre_completo, cedula, email, username, password_hash, rol_id) -> Usuario:
    usuario = Usuario(
        nombre_completo=nombre_completo,
        cedula=cedula or None,
        email=email or None,
        username=username.strip().lower(),
        password_hash=password_hash,
        rol_id=rol_id,
        activo=True,
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


def eliminar_informe_corte(session, informe_id: int) -> bool:
    """Borra un informe de corte (y en cascada sus notas_estudiantes). Si la
    asignacion se queda sin ningun informe, tambien se elimina para no dejar
    una materia 'fantasma' con 0 datos en el listado del docente."""
    informe = session.get(InformeCorte, informe_id)
    if informe is None:
        return False

    asignacion_id = informe.asignacion_id
    session.delete(informe)
    session.commit()

    quedan = session.scalar(
        select(func.count()).select_from(InformeCorte).where(InformeCorte.asignacion_id == asignacion_id)
    )
    if quedan == 0:
        asignacion = session.get(AsignacionAcademica, asignacion_id)
        if asignacion is not None:
            session.delete(asignacion)
            session.commit()

    return True


def resumen_dashboard_institucional(session, periodo_nombre: str) -> dict:
    """Agrega los datos de TODAS las asignaciones del periodo (todos los
    docentes, todas las materias) para el dashboard del Director y el
    Secretario Academico:
      - kpis institucionales
      - promedio/aprobacion por materia (con el corte mas reciente de cada una)
      - evolucion por corte (1, 2, 3) sumando todas las materias que ya
        tengan informe en ese corte
      - comparacion por docente
      - distribucion de riesgo (estado de cada estudiante, corte mas
        reciente de cada materia)
    """
    periodo = session.scalar(select(PeriodoAcademico).where(PeriodoAcademico.nombre == periodo_nombre))
    vacio = {
        "kpis": {
            "total_docentes": 0,
            "total_materias": 0,
            "total_matriculados": 0,
            "total_evaluados": 0,
            "total_aprobaron": 0,
            "promedio_general": 0.0,
            "pct_aprobacion_general": 0.0,
        },
        "por_materia": [],
        "por_corte": [],
        "por_docente": [],
        "conteo_estado_actual": {},
    }
    if periodo is None:
        return vacio

    asignaciones = list(
        session.scalars(
            select(AsignacionAcademica)
            .where(AsignacionAcademica.periodo_id == periodo.id)
            .options(
                selectinload(AsignacionAcademica.informes).selectinload(InformeCorte.corte),
                selectinload(AsignacionAcademica.informes).selectinload(InformeCorte.notas),
                selectinload(AsignacionAcademica.docente),
            )
        ).unique()
    )
    asignaciones = [a for a in asignaciones if a.informes]
    if not asignaciones:
        return vacio

    por_materia = []
    por_corte_acc: dict[int, dict] = {}
    conteo_estado_actual: dict[str, int] = {}
    docentes_acc: dict[int, dict] = {}

    for a in asignaciones:
        ultimo = max(a.informes, key=lambda i: i.corte.numero)
        por_materia.append(
            {
                "materia": a.asignatura,
                "docente": a.docente.nombre_completo,
                "grupo": a.grupo,
                "corte_numero": ultimo.corte.numero,
                "corte_nombre": ultimo.corte.nombre,
                "matriculados": ultimo.matriculados,
                "evaluados": ultimo.evaluados,
                "aprobaron": ultimo.aprobaron,
                "promedio": float(ultimo.promedio) if ultimo.promedio is not None else 0.0,
                "desviacion": float(ultimo.desviacion) if ultimo.desviacion is not None else 0.0,
            }
        )

        for nota in ultimo.notas:
            conteo_estado_actual[nota.estado] = conteo_estado_actual.get(nota.estado, 0) + 1

        docente_id = a.docente.id
        acc_docente = docentes_acc.setdefault(
            docente_id, {"docente": a.docente.nombre_completo, "matriculados": 0, "evaluados": 0, "aprobaron": 0, "promedios": []}
        )
        acc_docente["matriculados"] += ultimo.matriculados
        acc_docente["evaluados"] += ultimo.evaluados
        acc_docente["aprobaron"] += ultimo.aprobaron
        if ultimo.promedio is not None:
            acc_docente["promedios"].append(float(ultimo.promedio))

        for informe in a.informes:
            numero = informe.corte.numero
            acc_corte = por_corte_acc.setdefault(
                numero, {"matriculados": 0, "evaluados": 0, "aprobaron": 0, "promedios": []}
            )
            acc_corte["matriculados"] += informe.matriculados
            acc_corte["evaluados"] += informe.evaluados
            acc_corte["aprobaron"] += informe.aprobaron
            if informe.promedio is not None:
                acc_corte["promedios"].append(float(informe.promedio))

    total_matriculados = sum(m["matriculados"] for m in por_materia)
    total_evaluados = sum(m["evaluados"] for m in por_materia)
    total_aprobaron = sum(m["aprobaron"] for m in por_materia)
    promedios_validos = [m["promedio"] for m in por_materia if m["promedio"]]

    por_corte = [
        {
            "corte_numero": numero,
            "matriculados": acc["matriculados"],
            "evaluados": acc["evaluados"],
            "aprobaron": acc["aprobaron"],
            "promedio": round(sum(acc["promedios"]) / len(acc["promedios"]), 1) if acc["promedios"] else 0.0,
            "pct_aprobacion": round(acc["aprobaron"] / acc["evaluados"] * 100, 1) if acc["evaluados"] else 0.0,
        }
        for numero, acc in sorted(por_corte_acc.items())
    ]

    por_docente = [
        {
            "docente": d["docente"],
            "matriculados": d["matriculados"],
            "evaluados": d["evaluados"],
            "aprobaron": d["aprobaron"],
            "promedio": round(sum(d["promedios"]) / len(d["promedios"]), 1) if d["promedios"] else 0.0,
            "pct_aprobacion": round(d["aprobaron"] / d["evaluados"] * 100, 1) if d["evaluados"] else 0.0,
        }
        for d in sorted(docentes_acc.values(), key=lambda x: x["docente"])
    ]

    return {
        "kpis": {
            "total_docentes": len(docentes_acc),
            "total_materias": len(por_materia),
            "total_matriculados": total_matriculados,
            "total_evaluados": total_evaluados,
            "total_aprobaron": total_aprobaron,
            "promedio_general": round(sum(promedios_validos) / len(promedios_validos), 1) if promedios_validos else 0.0,
            "pct_aprobacion_general": round(total_aprobaron / total_evaluados * 100, 1) if total_evaluados else 0.0,
        },
        "por_materia": sorted(por_materia, key=lambda m: m["promedio"], reverse=True),
        "por_corte": por_corte,
        "por_docente": por_docente,
        "conteo_estado_actual": conteo_estado_actual,
    }


def asignacion_con_detalle(session, asignacion_id: int) -> AsignacionAcademica | None:
    stmt = (
        select(AsignacionAcademica)
        .where(AsignacionAcademica.id == asignacion_id)
        .options(
            selectinload(AsignacionAcademica.informes)
            .selectinload(InformeCorte.corte),
            selectinload(AsignacionAcademica.informes)
            .selectinload(InformeCorte.notas),
        )
    )
    return session.scalar(stmt)
