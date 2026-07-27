"""Funciones de acceso a datos (capa de repositorio) sobre los modelos de
db/models.py. Mantiene las consultas SQLAlchemy fuera de las vistas de
Streamlit."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from agente_notas.almacenamiento import eliminar_archivo
from db.models import (
    AsignacionAcademica,
    Corte,
    DocumentoEntrega,
    Entrega,
    EventoCalendario,
    InformeCorte,
    NotaEstudiante,
    Notificacion,
    PeriodoAcademico,
    Rol,
    Usuario,
)


def corte_por_numero(session, numero: int) -> Corte | None:
    return session.scalar(select(Corte).where(Corte.numero == numero))


def parsear_periodo(nombre: str) -> tuple[int, int]:
    """'2026-1' -> (2026, 1). Cada año academico tiene 2 semestres."""
    try:
        anio_txt, semestre_txt = nombre.split("-")
        anio, semestre = int(anio_txt), int(semestre_txt)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Nombre de periodo invalido: {nombre!r}. Formato esperado 'AAAA-S'.") from exc
    if semestre not in (1, 2):
        raise ValueError(f"Semestre invalido en {nombre!r}: debe ser 1 o 2.")
    return anio, semestre


def obtener_o_crear_periodo(session, nombre: str) -> PeriodoAcademico:
    periodo = session.scalar(select(PeriodoAcademico).where(PeriodoAcademico.nombre == nombre))
    if periodo is None:
        anio, semestre = parsear_periodo(nombre)
        periodo = PeriodoAcademico(nombre=nombre, anio=anio, semestre=semestre)
        session.add(periodo)
        session.commit()
    return periodo


def periodo_mas_reciente(session) -> PeriodoAcademico | None:
    return session.scalar(select(PeriodoAcademico).order_by(PeriodoAcademico.id.desc()))


def listar_periodos(session) -> list[PeriodoAcademico]:
    """Todos los periodos academicos registrados, del mas reciente al mas
    antiguo -- para poblar los selectores de Año/Semestre del Director y
    el Secretario Academico."""
    return list(
        session.scalars(
            select(PeriodoAcademico).order_by(PeriodoAcademico.anio.desc(), PeriodoAcademico.semestre.desc())
        )
    )


def resolver_periodo_ids(session, anio: int, semestre: int | None = None) -> list[int]:
    """IDs de PeriodoAcademico para un Año (ambos semestres) o para un
    Semestre especifico dentro de ese Año."""
    stmt = select(PeriodoAcademico.id).where(PeriodoAcademico.anio == anio)
    if semestre is not None:
        stmt = stmt.where(PeriodoAcademico.semestre == semestre)
    return list(session.scalars(stmt))


def crear_o_obtener_periodo(session, anio: int, semestre: int) -> PeriodoAcademico:
    """Crea (o devuelve si ya existe) el periodo de un Año/Semestre.
    Usado por el Director/Secretario para dar de alta el siguiente
    semestre (p.ej. '2026-2') antes de activarlo."""
    if semestre not in (1, 2):
        raise ValueError("El semestre debe ser 1 o 2.")
    nombre = f"{anio}-{semestre}"
    return obtener_o_crear_periodo(session, nombre)


def periodo_activo(session) -> PeriodoAcademico | None:
    """El periodo marcado como 'actual' -- donde se guardan los informes
    que los docentes cargan hoy. Puede no haber ninguno (recien sembrada
    la base de datos, antes de que el Director/Secretario active uno)."""
    return session.scalar(select(PeriodoAcademico).where(PeriodoAcademico.activo.is_(True)))


def activar_periodo(session, periodo_id: int) -> PeriodoAcademico:
    """Marca este periodo como el 'actual' (donde caen las nuevas cargas
    de notas de los docentes) y desactiva cualquier otro. Solo puede
    haber un periodo activo a la vez."""
    periodo = session.get(PeriodoAcademico, periodo_id)
    if periodo is None:
        raise ValueError(f"Periodo {periodo_id} no existe.")
    session.query(PeriodoAcademico).update({PeriodoAcademico.activo: False})
    periodo.activo = True
    session.commit()
    session.refresh(periodo)
    return periodo


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


def resumen_dashboard_institucional(
    session, anio: int, semestre: int | None = None, corte: int | None = None
) -> dict:
    """Agrega los datos de TODAS las asignaciones del alcance elegido (todos
    los docentes, todas las materias) para el dashboard y los informes
    consolidados del Director y el Secretario Academico:
      - anio: obligatorio. Si semestre es None, agrega los DOS semestres
        de ese año; si se indica, se limita a ese semestre.
      - corte: si es None, usa el corte mas reciente cargado de cada
        asignacion (comportamiento historico). Si se indica (1, 2 o 3),
        usa exclusivamente el informe de ese corte -- las asignaturas que
        aun no tengan ese corte cargado no aparecen en 'por_materia'.

      - kpis institucionales
      - promedio/aprobacion por materia (segun el corte elegido)
      - evolucion por corte (1, 2, 3) sumando todas las materias que ya
        tengan informe en ese corte (no se ve afectada por 'corte', para
        poder ver siempre la evolucion completa del alcance)
      - comparacion por docente
      - distribucion de riesgo (estado de cada estudiante, segun el
        corte elegido)
    """
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
        "generado_en": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    periodo_ids = resolver_periodo_ids(session, anio, semestre)
    if not periodo_ids:
        return vacio

    asignaciones = list(
        session.scalars(
            select(AsignacionAcademica)
            .where(AsignacionAcademica.periodo_id.in_(periodo_ids))
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
        if corte is not None:
            elegido = next((i for i in a.informes if i.corte.numero == corte), None)
            if elegido is None:
                continue
        else:
            elegido = max(a.informes, key=lambda i: i.corte.numero)
        ultimo = elegido
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
        "generado_en": datetime.now().strftime("%d/%m/%Y %H:%M"),
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


# --- Calendario academico ----------------------------------------------------

def listar_eventos_calendario(session, periodo_id: int) -> list[EventoCalendario]:
    """Eventos del calendario oficial de un periodo, en el orden en que
    aparecen en el calendario institucional (no alfabetico)."""
    stmt = (
        select(EventoCalendario)
        .where(EventoCalendario.periodo_id == periodo_id)
        .order_by(EventoCalendario.orden, EventoCalendario.fecha_inicio)
    )
    return list(session.scalars(stmt))


def crear_evento_calendario(
    session, periodo_id: int, actividad: str, fecha_inicio, fecha_fin=None, orden: int = 0
) -> EventoCalendario:
    evento = EventoCalendario(
        periodo_id=periodo_id, actividad=actividad, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, orden=orden
    )
    session.add(evento)
    session.commit()
    session.refresh(evento)
    return evento


def actualizar_evento_calendario(session, evento_id: int, **campos) -> EventoCalendario | None:
    """campos admitidos: actividad, fecha_inicio, fecha_fin, orden (solo
    se actualizan los que se pasen)."""
    evento = session.get(EventoCalendario, evento_id)
    if evento is None:
        return None
    for campo, valor in campos.items():
        setattr(evento, campo, valor)
    session.commit()
    session.refresh(evento)
    return evento


def eliminar_evento_calendario(session, evento_id: int) -> bool:
    evento = session.get(EventoCalendario, evento_id)
    if evento is None:
        return False
    session.delete(evento)
    session.commit()
    return True


# --- Entrega de documentos del docente ---------------------------------------

def buscar_entrega(session, docente_id: int, periodo_id: int, corte_id: int) -> Entrega | None:
    """Busqueda de solo lectura -- a diferencia de obtener_o_crear_entrega,
    NO crea una fila si no existe. Usar para simplemente mostrar el
    estado actual (p.ej. al renderizar la pantalla del docente) sin
    ensuciar la base de datos con entregas vacias que nadie ha empezado."""
    return session.scalar(
        select(Entrega).where(
            Entrega.docente_id == docente_id, Entrega.periodo_id == periodo_id, Entrega.corte_id == corte_id
        )
    )


def obtener_o_crear_entrega(session, docente_id: int, periodo_id: int, corte_id: int) -> Entrega:
    entrega = buscar_entrega(session, docente_id, periodo_id, corte_id)
    if entrega is None:
        entrega = Entrega(docente_id=docente_id, periodo_id=periodo_id, corte_id=corte_id)
        session.add(entrega)
        session.commit()
        session.refresh(entrega)
    return entrega


def _volver_a_pendiente(entrega: Entrega) -> None:
    """Cualquier cambio en los archivos de una entrega invalida una
    revision anterior: hay que revisarla de nuevo antes de aprobarla."""
    entrega.estado = "pendiente"
    entrega.documentos_firmados_confirmado = False
    entrega.comentario_revision = None
    entrega.revisado_por_id = None
    entrega.revisado_en = None
    entrega.notificacion_enviada = False
    entrega.notificacion_error = None


def agregar_documento_entrega(
    session,
    entrega_id: int,
    tipo_documento: str,
    nombre_archivo: str,
    ruta_archivo: str,
    tamano_bytes: int,
    materia: str | None = None,
    descripcion_otro: str | None = None,
) -> DocumentoEntrega:
    entrega = session.get(Entrega, entrega_id)
    if entrega is None:
        raise ValueError(f"Entrega {entrega_id} no existe.")

    documento = DocumentoEntrega(
        entrega_id=entrega_id,
        tipo_documento=tipo_documento,
        materia=materia,
        descripcion_otro=descripcion_otro,
        nombre_archivo=nombre_archivo,
        ruta_archivo=ruta_archivo,
        tamano_bytes=tamano_bytes,
    )
    session.add(documento)
    _volver_a_pendiente(entrega)
    session.commit()
    session.refresh(documento)
    return documento


def documento_entrega_por_id(session, documento_id: int) -> DocumentoEntrega | None:
    return session.get(DocumentoEntrega, documento_id)


def eliminar_documento_entrega(session, documento_id: int) -> bool:
    """Borra el documento (fila + archivo en disco) y vuelve la entrega a
    'pendiente' -- ya no representa lo que se revisó/aprobó antes. Si esa
    entrega se queda sin ningún documento, tambien se elimina (no dejar
    una entrega 'fantasma' con 0 archivos en la cola de revisión)."""
    documento = session.get(DocumentoEntrega, documento_id)
    if documento is None:
        return False
    entrega = session.get(Entrega, documento.entrega_id)
    ruta = documento.ruta_archivo
    session.delete(documento)
    if entrega is not None:
        _volver_a_pendiente(entrega)
    session.commit()
    eliminar_archivo(ruta)

    if entrega is not None:
        quedan = session.scalar(
            select(func.count()).select_from(DocumentoEntrega).where(DocumentoEntrega.entrega_id == entrega.id)
        )
        if quedan == 0:
            session.delete(entrega)
            session.commit()
    return True


def listar_entregas(
    session,
    periodo_id: int | None = None,
    corte_id: int | None = None,
    estado: str | None = None,
    docente_id: int | None = None,
    documento_docente: str | None = None,
) -> list[Entrega]:
    """documento_docente: busca por la cedula del docente (coincidencia
    parcial), para que Director/Secretario/Secretaria puedan consultar
    las entregas de un docente especifico entre todo el historico."""
    stmt = select(Entrega).options(
        selectinload(Entrega.documentos),
        selectinload(Entrega.docente),
        selectinload(Entrega.periodo),
        selectinload(Entrega.corte),
        selectinload(Entrega.revisado_por),
    )
    if periodo_id is not None:
        stmt = stmt.where(Entrega.periodo_id == periodo_id)
    if corte_id is not None:
        stmt = stmt.where(Entrega.corte_id == corte_id)
    if estado is not None:
        stmt = stmt.where(Entrega.estado == estado)
    if docente_id is not None:
        stmt = stmt.where(Entrega.docente_id == docente_id)
    if documento_docente:
        stmt = stmt.join(Usuario, Entrega.docente_id == Usuario.id).where(
            Usuario.cedula.ilike(f"%{documento_docente.strip()}%")
        )
    stmt = stmt.order_by(Entrega.actualizado_en.desc())
    return list(session.scalars(stmt).unique())


def entrega_con_detalle(session, entrega_id: int) -> Entrega | None:
    stmt = (
        select(Entrega)
        .where(Entrega.id == entrega_id)
        .options(
            selectinload(Entrega.documentos),
            selectinload(Entrega.docente),
            selectinload(Entrega.periodo),
            selectinload(Entrega.corte),
            selectinload(Entrega.revisado_por),
        )
    )
    return session.scalar(stmt)


def aprobar_entrega(session, entrega_id: int, revisor_id: int, comentario: str | None = None) -> Entrega:
    entrega = entrega_con_detalle(session, entrega_id)
    if entrega is None:
        raise ValueError(f"Entrega {entrega_id} no existe.")
    if not entrega.documentos:
        raise ValueError("No se puede aprobar una entrega sin documentos cargados.")

    entrega.estado = "aprobado"
    entrega.documentos_firmados_confirmado = True
    entrega.comentario_revision = comentario
    entrega.revisado_por_id = revisor_id
    entrega.revisado_en = datetime.utcnow()
    session.commit()
    session.refresh(entrega)
    return entrega


def rechazar_entrega(session, entrega_id: int, revisor_id: int, comentario: str) -> Entrega:
    if not comentario or not comentario.strip():
        raise ValueError("Debes indicar el motivo del rechazo.")
    entrega = session.get(Entrega, entrega_id)
    if entrega is None:
        raise ValueError(f"Entrega {entrega_id} no existe.")

    entrega.estado = "rechazado"
    entrega.documentos_firmados_confirmado = False
    entrega.comentario_revision = comentario
    entrega.revisado_por_id = revisor_id
    entrega.revisado_en = datetime.utcnow()
    session.commit()
    session.refresh(entrega)
    return entrega


def marcar_notificacion_entrega(session, entrega_id: int, enviada: bool, error: str | None) -> None:
    entrega = session.get(Entrega, entrega_id)
    if entrega is not None:
        entrega.notificacion_enviada = enviada
        entrega.notificacion_error = error
        session.commit()


def emails_personal_revisor(session) -> list[str]:
    """Correos de todos los Directores, Secretarios Academicos y
    Secretarias del Programa activos -- los tres roles que pueden
    revisar/aprobar una entrega, y a quienes se notifica junto con el
    docente cuando una entrega queda aprobada."""
    stmt = (
        select(Usuario.email)
        .join(Rol, Usuario.rol_id == Rol.id)
        .where(
            Rol.nombre.in_(("director", "secretario", "secretaria_programa")),
            Usuario.activo.is_(True),
            Usuario.email.is_not(None),
        )
    )
    return [e for e in session.scalars(stmt) if e]


def ids_personal_revisor(session) -> list[int]:
    """Ids de todos los Directores, Secretarios Academicos y Secretarias
    del Programa activos -- para crear sus notificaciones dentro de la
    app (independiente de si tienen correo o no)."""
    stmt = (
        select(Usuario.id)
        .join(Rol, Usuario.rol_id == Rol.id)
        .where(Rol.nombre.in_(("director", "secretario", "secretaria_programa")), Usuario.activo.is_(True))
    )
    return list(session.scalars(stmt))


# --- Notificaciones dentro de la aplicacion -----------------------------------

def crear_notificacion(session, usuario_id: int, mensaje: str, entrega_id: int | None = None) -> Notificacion:
    notificacion = Notificacion(usuario_id=usuario_id, mensaje=mensaje, entrega_id=entrega_id)
    session.add(notificacion)
    session.commit()
    session.refresh(notificacion)
    return notificacion


def notificar_usuarios(session, usuario_ids: list[int], mensaje: str, entrega_id: int | None = None) -> None:
    """Crea una notificacion identica para cada usuario de la lista
    (p.ej. Director + Secretario + Secretaria + el docente, cuando se
    aprueba/rechaza una entrega)."""
    for usuario_id in set(usuario_ids):
        session.add(Notificacion(usuario_id=usuario_id, mensaje=mensaje, entrega_id=entrega_id))
    session.commit()


def listar_notificaciones(session, usuario_id: int, solo_no_leidas: bool = False, limite: int = 50) -> list[Notificacion]:
    stmt = select(Notificacion).where(Notificacion.usuario_id == usuario_id)
    if solo_no_leidas:
        stmt = stmt.where(Notificacion.leida.is_(False))
    stmt = stmt.order_by(Notificacion.creado_en.desc()).limit(limite)
    return list(session.scalars(stmt))


def contar_notificaciones_no_leidas(session, usuario_id: int) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Notificacion)
        .where(Notificacion.usuario_id == usuario_id, Notificacion.leida.is_(False))
    )


def marcar_notificacion_leida(session, notificacion_id: int, usuario_id: int) -> bool:
    """usuario_id se exige para que nadie marque como leida una
    notificacion ajena."""
    notificacion = session.get(Notificacion, notificacion_id)
    if notificacion is None or notificacion.usuario_id != usuario_id:
        return False
    notificacion.leida = True
    session.commit()
    return True


def marcar_todas_notificaciones_leidas(session, usuario_id: int) -> None:
    session.query(Notificacion).filter(
        Notificacion.usuario_id == usuario_id, Notificacion.leida.is_(False)
    ).update({Notificacion.leida: True})
    session.commit()
