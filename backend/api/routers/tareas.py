"""Módulo de tareas académicas y administrativas -- Fase 1 (ver
docs/especificacionModuloTareas.md): catálogos (categorías, prioridades,
estados) y CRUD básico de tareas, con la visibilidad y las reglas de
creación/edición documentadas en el plan de Fase 1.

Roles: Director y Secretario Académico crean/asignan/editan tareas
institucionales; cualquier rol crea tareas personales; la Secretaria del
Programa solo crea en Borrador (lo publica Director/Secretario)."""
import io
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agente_notas.almacenamiento import (
    ArchivoInvalido,
    guardar_archivo_evidencia_tarea,
    nombre_seguro_para_header,
    ruta_absoluta_segura,
    tipo_y_disposicion,
)
from agente_notas.almacenamiento import eliminar_archivo as _eliminar_archivo_disco
from backend.api.deps import get_db, requiere_roles, verificar_pertenece_a_programa
from backend.schemas.tarea import (
    AsignarTareaIn,
    CancelarTareaIn,
    CategoriaTareaCreate,
    CategoriaTareaOut,
    DevolverTareaIn,
    EstadoTareaOut,
    EvidenciaTareaOut,
    IndicadoresTareasOut,
    PrioridadTareaOut,
    ReactivarTareaIn,
    ResponsableSecundarioOut,
    TareaCreate,
    TareaOut,
    TareaUpdate,
)
from backend.services.reporte_tareas_pdf import generar_informe_tareas
from db.models import Tarea, Usuario
from db.repository import (
    agregar_evidencia_tarea,
    asignar_tarea,
    actualizar_tarea,
    aprobar_tarea,
    cancelar_tarea,
    crear_categoria_tarea,
    crear_tarea,
    devolver_tarea,
    eliminar_evidencia_tarea,
    enviar_a_revision_tarea,
    evidencia_tarea_por_id,
    indicadores_tareas,
    iniciar_tarea,
    listar_categorias_tarea,
    listar_estados_tarea,
    listar_evidencias_tarea,
    listar_prioridades_tarea,
    listar_tareas,
    notificar_usuarios,
    publicar_tarea,
    reactivar_tarea,
    reasignar_tarea,
    tarea_por_id,
    terminar_tarea,
)

router = APIRouter(prefix="/api/tareas", tags=["tareas"])

ROLES_TODOS = ("director", "secretario", "docente", "secretaria_programa")
ROLES_ASIGNAN = ("director", "secretario")
# Todos los roles administrativos, sin el Docente -- ver pedido explicito
# del usuario: "esta funcion la deben hacer todo los roles, menos el
# docente" (reactivar una tarea Vencida).
ROLES_REACTIVAN = ("director", "secretario", "secretaria_programa")

ESTADOS_CERRADOS = ("TERMINADA", "CANCELADA")


def _out(t: Tarea) -> TareaOut:
    return TareaOut(
        id=t.id,
        codigo=f"TAR-{t.id:06d}",
        titulo=t.titulo,
        descripcion=t.descripcion,
        objetivo=t.objetivo,
        resultado_esperado=t.resultado_esperado,
        tipo=t.tipo,
        categoria_id=t.categoria_id,
        categoria_nombre=t.categoria.nombre if t.categoria else None,
        prioridad_id=t.prioridad_id,
        prioridad_nombre=t.prioridad.nombre,
        estado_id=t.estado_id,
        estado_nombre=t.estado.nombre,
        estado_icono=t.estado.icono,
        programa_id=t.programa_id,
        periodo_id=t.periodo_id,
        periodo_nombre=t.periodo.nombre if t.periodo else None,
        responsable_principal_id=t.responsable_principal_id,
        responsable_principal_nombre=t.responsable_principal.nombre_completo if t.responsable_principal else None,
        responsables_secundarios=[
            ResponsableSecundarioOut(usuario_id=r.usuario_id, nombre_completo=r.usuario.nombre_completo)
            for r in t.responsables_secundarios
        ],
        creado_por_id=t.creado_por_id,
        creado_por_nombre=t.creado_por.nombre_completo if t.creado_por else None,
        asignado_por_id=t.asignado_por_id,
        asignado_por_nombre=t.asignado_por.nombre_completo if t.asignado_por else None,
        fecha_inicio=t.fecha_inicio,
        fecha_limite=t.fecha_limite,
        hora_limite=t.hora_limite,
        fecha_fin_real=t.fecha_fin_real,
        porcentaje_avance=t.porcentaje_avance,
        confidencialidad=t.confidencialidad,
        requiere_evidencia=t.requiere_evidencia,
        requiere_aprobacion=t.requiere_aprobacion,
        permite_ampliacion=t.permite_ampliacion,
        motivo_cancelacion=t.motivo_cancelacion,
        justificacion_retraso=t.justificacion_retraso,
        creado_en=t.creado_en,
        actualizado_en=t.actualizado_en,
    )


def _puede_ver(tarea: Tarea, usuario: Usuario) -> bool:
    if usuario.rol.nombre in ROLES_ASIGNAN:
        return True
    if tarea.creado_por_id == usuario.id or tarea.responsable_principal_id == usuario.id:
        return True
    return any(r.usuario_id == usuario.id for r in tarea.responsables_secundarios)


def _verificar_permiso_editar(tarea: Tarea, usuario: Usuario) -> None:
    """Solo quien asignó la tarea puede editarla, y solo antes de su
    fecha límite (pedido explícito del usuario). Para tareas personales
    (creadas directo por el Docente/Secretaria del Programa, nunca
    pasaron por /asignar) el creador cumple ese rol -- es quien se la
    "asignó" a sí mismo. El Director conserva su override total, igual
    que en el resto del módulo (cancelar, reactivar, etc.)."""
    if usuario.rol.nombre == "director":
        return
    if tarea.estado.nombre in ESTADOS_CERRADOS:
        raise HTTPException(status_code=403, detail="Esta tarea ya está cerrada y no se puede editar.")
    if tarea.fecha_limite is not None and date.today() > tarea.fecha_limite:
        raise HTTPException(status_code=403, detail="Esta tarea ya venció y no se puede editar.")
    asignador_efectivo = tarea.asignado_por_id if tarea.asignado_por_id is not None else tarea.creado_por_id
    if usuario.id != asignador_efectivo:
        raise HTTPException(status_code=403, detail="Solo quien asignó la tarea puede editarla.")


def _tarea_o_404(db: Session, id_: int, usuario: Usuario) -> Tarea:
    tarea = tarea_por_id(db, id_)
    if tarea is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    verificar_pertenece_a_programa(tarea.programa_id, usuario)
    return tarea


def _es_responsable(tarea: Tarea, usuario: Usuario) -> bool:
    if tarea.responsable_principal_id == usuario.id:
        return True
    return any(r.usuario_id == usuario.id for r in tarea.responsables_secundarios)


def _puede_subir_evidencia(tarea: Tarea, usuario: Usuario) -> bool:
    """Cualquier rol involucrado en la tarea (responsable, secundarios o
    quien puede asignar) puede subir evidencia -- pero SOLO si la tarea
    la requiere (tarea.requiere_evidencia); no es una funcionalidad
    abierta a cualquier tarea."""
    return tarea.requiere_evidencia and (_es_responsable(tarea, usuario) or usuario.rol.nombre in ROLES_ASIGNAN)


def _out_evidencia(e) -> EvidenciaTareaOut:
    return EvidenciaTareaOut(
        id=e.id,
        nombre_archivo=e.nombre_archivo,
        tamano_bytes=e.tamano_bytes,
        subido_por_id=e.subido_por_id,
        subido_por_nombre=e.subido_por.nombre_completo if e.subido_por else None,
        subido_en=e.subido_en,
    )


def _notificar_cambio_estado(db: Session, tarea: Tarea, usuario: Usuario, accion: str, detalle: str = "") -> None:
    """Notifica a todos los involucrados en la tarea EXCEPTO a quien
    hizo el cambio: creador, asignador, responsable principal y
    responsables secundarios. Sin esto, cuando un Director/Secretario
    inicia o termina una tarea EN NOMBRE del responsable (el caso mas
    comun), nadie se enteraba -- el actor y el asignador/creador
    coinciden y quedaban excluidos entre si, dejando al responsable
    (el principal interesado) sin avisar.

    detalle: texto libre opcional (p.ej. las observaciones de una
    devolucion) que se agrega DESPUES de nombrar la tarea, para no
    partir la oracion a la mitad ('... devolvió la tarea X con
    observaciones: Y', no '... devolvió con observaciones: Y la tarea X')."""
    destinatarios = {
        tarea.asignado_por_id,
        tarea.creado_por_id,
        tarea.responsable_principal_id,
        *(r.usuario_id for r in tarea.responsables_secundarios),
    } - {None, usuario.id}
    if not destinatarios:
        return
    sufijo = f" {detalle}" if detalle else ""
    notificar_usuarios(
        db,
        list(destinatarios),
        f"{usuario.nombre_completo} {accion} la tarea 'TAR-{tarea.id:06d} — {tarea.titulo}'.{sufijo}",
        tarea_id=tarea.id,
    )


@router.get("", response_model=list[TareaOut])
def listar(
    estado: str | None = None,
    prioridad: str | None = None,
    categoria_id: int | None = None,
    responsable_id: int | None = None,
    tipo: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    tareas = listar_tareas(
        db, usuario, estado=estado, prioridad=prioridad, categoria_id=categoria_id,
        responsable_id=responsable_id, tipo=tipo,
    )
    return [_out(t) for t in tareas]


# Catalogos registrados ANTES de la ruta dinamica '/{id_}' (mismo criterio ya
# usado en repositorio_asignaturas.py) -- aunque en este caso no colisionan
# (2 segmentos vs 1), se mantiene el orden por consistencia y para no dejar
# una trampa si alguna vez se agrega una ruta de 1 solo segmento.
@router.get("/catalogos/prioridades", response_model=list[PrioridadTareaOut])
def prioridades(db: Session = Depends(get_db), _usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))):
    return [PrioridadTareaOut(id=p.id, nombre=p.nombre, icono=p.icono, color=p.color, orden=p.orden, nivel=p.nivel)
            for p in listar_prioridades_tarea(db)]


@router.get("/catalogos/estados", response_model=list[EstadoTareaOut])
def estados(db: Session = Depends(get_db), _usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))):
    return [
        EstadoTareaOut(id=e.id, nombre=e.nombre, icono=e.icono, color=e.color, orden=e.orden)
        for e in listar_estados_tarea(db)
    ]


@router.get("/catalogos/categorias", response_model=list[CategoriaTareaOut])
def categorias(db: Session = Depends(get_db), _usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))):
    return [CategoriaTareaOut(id=c.id, nombre=c.nombre, activa=c.activa) for c in listar_categorias_tarea(db)]


@router.post("/catalogos/categorias", response_model=CategoriaTareaOut, status_code=201)
def crear_categoria(
    datos: CategoriaTareaCreate,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(requiere_roles("director")),
):
    try:
        categoria = crear_categoria_tarea(db, datos.nombre)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"No se pudo crear (¿ya existe esa categoría?): {exc}")
    return CategoriaTareaOut(id=categoria.id, nombre=categoria.nombre, activa=categoria.activa)


@router.get("/indicadores", response_model=IndicadoresTareasOut)
def indicadores(db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))):
    return IndicadoresTareasOut(**indicadores_tareas(db, usuario))


@router.get("/informe")
def informe(
    estado: str | None = None,
    prioridad: str | None = None,
    categoria_id: int | None = None,
    responsable_id: int | None = None,
    tipo: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    """PDF con exactamente lo que este usuario puede ver en '/api/tareas'
    con los mismos filtros (listar_tareas aplica la misma regla de
    visibilidad por rol -- no existe una ruta de reporte que muestre mas
    de lo que el rol ya puede consultar) + los indicadores de
    '/api/tareas/indicadores'."""
    tareas = listar_tareas(
        db, usuario, estado=estado, prioridad=prioridad, categoria_id=categoria_id,
        responsable_id=responsable_id, tipo=tipo, limite=100000,
    )
    indicadores_datos = indicadores_tareas(db, usuario)

    filtros = []
    if estado:
        filtros.append(f"Estado: {estado}")
    if prioridad:
        filtros.append(f"Prioridad: {prioridad}")
    if categoria_id:
        filtros.append(f"Categoría #{categoria_id}")
    if responsable_id:
        filtros.append(f"Responsable #{responsable_id}")
    if tipo:
        filtros.append(f"Tipo: {tipo}")
    filtros_texto = " · ".join(filtros) if filtros else "Todas las tareas visibles para tu rol"

    programa_nombre = usuario.programa.nombre if usuario.programa else "Gestión Docente"
    logo_ruta = (
        Path(usuario.programa.logo_ruta_archivo)
        if usuario.programa and usuario.programa.logo_ruta_archivo
        else None
    )

    buffer = io.BytesIO()
    generar_informe_tareas(
        tareas, indicadores_datos, buffer, programa_nombre, usuario.nombre_completo,
        filtros_texto=filtros_texto, logo_ruta=logo_ruta,
    )
    buffer.seek(0)

    filename = f"Informe_tareas_{date.today().isoformat()}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{id_}", response_model=TareaOut)
def detalle(id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))):
    tarea = _tarea_o_404(db, id_, usuario)
    if not _puede_ver(tarea, usuario):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea.")
    return _out(tarea)


@router.post("", response_model=TareaOut, status_code=201)
def crear(
    datos: TareaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    if usuario.programa_id is None:
        raise HTTPException(status_code=400, detail="Tu cuenta no pertenece a ningún programa académico.")
    rol = usuario.rol.nombre
    if datos.tipo == "institucional" and rol not in (*ROLES_ASIGNAN, "secretaria_programa"):
        raise HTTPException(status_code=403, detail="Solo puedes crear tareas personales.")
    tarea = crear_tarea(
        db,
        titulo=datos.titulo,
        descripcion=datos.descripcion,
        objetivo=datos.objetivo,
        resultado_esperado=datos.resultado_esperado,
        tipo=datos.tipo,
        categoria_id=datos.categoria_id,
        prioridad_id=datos.prioridad_id,
        programa_id=usuario.programa_id,
        periodo_id=datos.periodo_id,
        fecha_inicio=datos.fecha_inicio,
        fecha_limite=datos.fecha_limite,
        hora_limite=datos.hora_limite,
        confidencialidad=datos.confidencialidad,
        requiere_evidencia=datos.requiere_evidencia,
        requiere_aprobacion=datos.requiere_aprobacion,
        permite_ampliacion=datos.permite_ampliacion,
        creado_por_id=usuario.id,
        creador_rol=rol,
    )
    return _out(tarea)


@router.patch("/{id_}", response_model=TareaOut)
def actualizar(
    id_: int,
    datos: TareaUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    tarea = _tarea_o_404(db, id_, usuario)
    _verificar_permiso_editar(tarea, usuario)
    campos = datos.model_dump(exclude_unset=True)
    actualizada = actualizar_tarea(db, id_, usuario.id, **campos)
    if campos:
        _notificar_cambio_estado(db, actualizada, usuario, "actualizó")
    return _out(actualizada)


@router.post("/{id_}/asignar", response_model=TareaOut)
def asignar(
    id_: int,
    datos: AsignarTareaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_ASIGNAN)),
):
    _tarea_o_404(db, id_, usuario)
    try:
        tarea = asignar_tarea(
            db, id_, datos.responsable_principal_id, usuario.id, datos.responsables_secundarios_ids
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _out(tarea)


@router.post("/{id_}/reasignar", response_model=TareaOut)
def reasignar(
    id_: int,
    datos: AsignarTareaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_ASIGNAN)),
):
    _tarea_o_404(db, id_, usuario)
    try:
        tarea = reasignar_tarea(db, id_, datos.responsable_principal_id, usuario.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _out(tarea)


@router.post("/{id_}/publicar", response_model=TareaOut)
def publicar(
    id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_ASIGNAN))
):
    _tarea_o_404(db, id_, usuario)
    try:
        tarea = publicar_tarea(db, id_, usuario.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _out(tarea)


@router.post("/{id_}/iniciar", response_model=TareaOut)
def iniciar(
    id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))
):
    tarea = _tarea_o_404(db, id_, usuario)
    if not (_es_responsable(tarea, usuario) or usuario.rol.nombre in ROLES_ASIGNAN):
        raise HTTPException(status_code=403, detail="Solo el responsable de la tarea puede iniciarla.")
    try:
        actualizada = iniciar_tarea(db, id_)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _notificar_cambio_estado(db, actualizada, usuario, "inició")
    return _out(actualizada)


@router.post("/{id_}/reactivar", response_model=TareaOut)
def reactivar(
    id_: int,
    datos: ReactivarTareaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_REACTIVAN)),
):
    """Reactiva una tarea Vencida (todos los roles administrativos EXCEPTO
    Docente, a pedido explicito del usuario). Exige una nueva fecha
    límite porque la actual ya paso -- ver db.repository.reactivar_tarea."""
    _tarea_o_404(db, id_, usuario)
    try:
        actualizada = reactivar_tarea(db, id_, datos.nueva_fecha_limite)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _notificar_cambio_estado(db, actualizada, usuario, "reactivó")
    return _out(actualizada)


@router.post("/{id_}/terminar", response_model=TareaOut)
def terminar(
    id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))
):
    """Todo rol involucrado en la tarea tiene SIEMPRE una manera de
    informar que la terminó -- lo que cambia segun requiere_aprobacion
    es si eso cierra la tarea de una vez (Director/Secretario, o el
    responsable cuando no se exige aprobacion) o si solo la deja
    Pendiente de revision a la espera de que Director/Secretario la
    apruebe o la devuelva (endpoints /aprobar y /devolver)."""
    tarea = _tarea_o_404(db, id_, usuario)
    if not (_es_responsable(tarea, usuario) or usuario.rol.nombre in ROLES_ASIGNAN):
        raise HTTPException(status_code=403, detail="Solo el responsable de la tarea puede terminarla.")

    cierra_directo = usuario.rol.nombre in ROLES_ASIGNAN or not tarea.requiere_aprobacion
    try:
        if cierra_directo:
            actualizada = terminar_tarea(db, id_)
            accion = "terminó"
        else:
            actualizada = enviar_a_revision_tarea(db, id_)
            accion = "envió a revisión"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _notificar_cambio_estado(db, actualizada, usuario, accion)
    return _out(actualizada)


@router.post("/{id_}/aprobar", response_model=TareaOut)
def aprobar(
    id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_ASIGNAN))
):
    _tarea_o_404(db, id_, usuario)
    try:
        actualizada = aprobar_tarea(db, id_)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _notificar_cambio_estado(db, actualizada, usuario, "aprobó y cerró")
    return _out(actualizada)


@router.post("/{id_}/devolver", response_model=TareaOut)
def devolver(
    id_: int,
    datos: DevolverTareaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_ASIGNAN)),
):
    _tarea_o_404(db, id_, usuario)
    try:
        actualizada = devolver_tarea(db, id_)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _notificar_cambio_estado(db, actualizada, usuario, "devolvió", detalle=f"Observaciones: {datos.motivo}")
    return _out(actualizada)


@router.post("/{id_}/cancelar", response_model=TareaOut)
def cancelar(
    id_: int,
    datos: CancelarTareaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    """No existe DELETE fisico (ver docs/especificacionModuloTareas.md,
    seccion 6): 'eliminar' una tarea es cancelarla, quedando visible para
    auditoria con su motivo."""
    tarea = _tarea_o_404(db, id_, usuario)
    if usuario.rol.nombre not in ROLES_ASIGNAN:
        if tarea.tipo != "personal" or tarea.creado_por_id != usuario.id:
            raise HTTPException(status_code=403, detail="Solo puedes cancelar tus propias tareas personales.")
    try:
        actualizada = cancelar_tarea(db, id_, datos.motivo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _notificar_cambio_estado(db, actualizada, usuario, "canceló")
    return _out(actualizada)


@router.get("/{id_}/evidencias", response_model=list[EvidenciaTareaOut])
def listar_evidencias(
    id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))
):
    tarea = _tarea_o_404(db, id_, usuario)
    if not _puede_ver(tarea, usuario):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea.")
    return [_out_evidencia(e) for e in listar_evidencias_tarea(db, id_)]


@router.post("/{id_}/evidencias", response_model=EvidenciaTareaOut, status_code=201)
def subir_evidencia(
    id_: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    tarea = _tarea_o_404(db, id_, usuario)
    if not _puede_subir_evidencia(tarea, usuario):
        if not tarea.requiere_evidencia:
            raise HTTPException(status_code=400, detail="Esta tarea no requiere evidencia.")
        raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea.")

    contenido = archivo.file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    nombre_archivo = archivo.filename or "archivo"
    try:
        ruta_relativa, tamano = guardar_archivo_evidencia_tarea(id_, nombre_archivo, contenido)
    except ArchivoInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    evidencia = agregar_evidencia_tarea(db, id_, nombre_archivo, ruta_relativa, tamano, usuario.id)
    _notificar_cambio_estado(db, tarea, usuario, f"adjuntó la evidencia '{nombre_archivo}' en")
    return _out_evidencia(evidencia)


@router.get("/{id_}/evidencias/{evidencia_id}/descargar")
def descargar_evidencia(
    id_: int,
    evidencia_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    tarea = _tarea_o_404(db, id_, usuario)
    if not _puede_ver(tarea, usuario):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea.")
    evidencia = evidencia_tarea_por_id(db, evidencia_id)
    if evidencia is None or evidencia.tarea_id != id_:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")

    ruta = ruta_absoluta_segura(evidencia.ruta_archivo)
    if ruta is None:
        raise HTTPException(status_code=404, detail="El archivo ya no existe en el servidor.")
    media_type, disposicion = tipo_y_disposicion(evidencia.nombre_archivo)
    nombre_header = nombre_seguro_para_header(evidencia.nombre_archivo)
    return StreamingResponse(
        io.BytesIO(ruta.read_bytes()),
        media_type=media_type,
        headers={"Content-Disposition": f'{disposicion}; filename="{nombre_header}"'},
    )


@router.delete("/{id_}/evidencias/{evidencia_id}")
def borrar_evidencia(
    id_: int,
    evidencia_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    tarea = _tarea_o_404(db, id_, usuario)
    evidencia = evidencia_tarea_por_id(db, evidencia_id)
    if evidencia is None or evidencia.tarea_id != id_:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    if usuario.rol.nombre not in ROLES_ASIGNAN and evidencia.subido_por_id != usuario.id:
        raise HTTPException(status_code=403, detail="Solo quien subió la evidencia (o un administrador) puede borrarla.")

    ruta_relativa = eliminar_evidencia_tarea(db, evidencia_id)
    if ruta_relativa:
        _eliminar_archivo_disco(ruta_relativa)
    return {"ok": True}
