"""Entregas documentales del docente (listas de asistencia, notas
firmadas, informe de gestión docente, etc.) por periodo y corte.

Cualquiera de los tres roles administrativos -- Director, Secretario
Académico o Secretaria del Programa -- puede revisar, aprobar o
rechazar una entrega. Al aprobarla se notifica por correo a los tres
roles y al docente."""
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agente_notas.agente_firmas import analizar_documento, resumen_entrega
from agente_notas.almacenamiento import (
    ArchivoInvalido,
    guardar_archivo_entrega,
    nombre_seguro_para_header,
    ruta_absoluta_segura,
    tipo_y_disposicion,
)
from agente_notas.notificaciones import notificar_entrega_aprobada
from backend.api.deps import get_db, requiere_roles
from backend.schemas.entrega import AprobarEntregaIn, EntregaOut, RechazarEntregaIn
from db.models import TIPOS_DOCUMENTO_ENTREGA, Entrega, Usuario
from db.repository import (
    agregar_documento_entrega,
    aprobar_entrega,
    confirmar_revision_documento,
    corte_por_numero,
    documento_entrega_por_id,
    eliminar_documento_entrega,
    emails_personal_revisor,
    entrega_con_detalle,
    ids_personal_revisor,
    listar_entregas,
    marcar_documento_visto,
    marcar_notificacion_entrega,
    notificar_usuarios,
    obtener_o_crear_entrega,
    rechazar_entrega,
)

router = APIRouter(prefix="/api/entregas", tags=["entregas"])

ROLES_REVISORES = ("director", "secretario", "secretaria_programa")


def _out(e: Entrega) -> EntregaOut:
    resumen = resumen_entrega(e.documentos)
    return EntregaOut(
        id=e.id,
        docente_id=e.docente_id,
        docente_nombre=e.docente.nombre_completo,
        periodo_id=e.periodo_id,
        periodo_nombre=e.periodo.nombre,
        corte_id=e.corte_id,
        corte_numero=e.corte.numero,
        corte_nombre=e.corte.nombre,
        estado=e.estado,
        documentos_firmados_confirmado=e.documentos_firmados_confirmado,
        comentario_revision=e.comentario_revision,
        revisado_por_nombre=e.revisado_por.nombre_completo if e.revisado_por else None,
        revisado_en=e.revisado_en,
        notificacion_enviada=e.notificacion_enviada,
        notificacion_error=e.notificacion_error,
        creado_en=e.creado_en,
        actualizado_en=e.actualizado_en,
        todos_firmados_agente=resumen["todos_firmados"],
        documentos=[
            {
                "id": d.id,
                "tipo_documento": d.tipo_documento,
                "descripcion_otro": d.descripcion_otro,
                "materia": d.materia,
                "nombre_archivo": d.nombre_archivo,
                "tamano_bytes": d.tamano_bytes,
                "subido_en": d.subido_en,
                "firma_detectada": d.firma_detectada,
                "firma_confianza": d.firma_confianza,
                "firma_detalle": d.firma_detalle,
                "visto_en": d.visto_en,
                "revisado_manualmente": d.revisado_manualmente,
                "revisado_por_nombre": d.revisado_por.nombre_completo if d.revisado_por else None,
                "revisado_en": d.revisado_en,
            }
            for d in e.documentos
        ],
    )


def _verificar_acceso_entrega(entrega: Entrega, usuario: Usuario) -> None:
    if usuario.rol.nombre == "docente" and entrega.docente_id != usuario.id:
        raise HTTPException(status_code=403, detail="No puedes ver la entrega de otro docente.")


@router.get("/tipos-documento")
def tipos_documento(_usuario: Usuario = Depends(requiere_roles("docente", *ROLES_REVISORES))):
    return TIPOS_DOCUMENTO_ENTREGA


@router.get("", response_model=list[EntregaOut])
def listar(
    periodo_id: int | None = None,
    corte_numero: int | None = None,
    estado: str | None = None,
    documento: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles("docente", *ROLES_REVISORES)),
):
    corte_id = None
    if corte_numero is not None:
        corte = corte_por_numero(db, corte_numero)
        corte_id = corte.id if corte else -1
    docente_id = usuario.id if usuario.rol.nombre == "docente" else None
    # 'documento' (cedula) solo tiene sentido para los roles revisores: un
    # docente solo ve las suyas de todas formas (docente_id ya lo fuerza).
    entregas = listar_entregas(
        db, periodo_id=periodo_id, corte_id=corte_id, estado=estado, docente_id=docente_id,
        documento_docente=documento if usuario.rol.nombre != "docente" else None,
    )
    return [_out(e) for e in entregas]


@router.get("/{entrega_id}", response_model=EntregaOut)
def detalle(entrega_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles("docente", *ROLES_REVISORES))):
    entrega = entrega_con_detalle(db, entrega_id)
    if entrega is None:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    _verificar_acceso_entrega(entrega, usuario)
    return _out(entrega)


@router.post("/documentos", response_model=EntregaOut)
def subir_documento(
    periodo_id: int = Form(...),
    corte_numero: int = Form(...),
    tipo_documento: str = Form(...),
    materia: str = Form(""),
    descripcion_otro: str = Form(""),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles("docente")),
):
    if tipo_documento not in TIPOS_DOCUMENTO_ENTREGA:
        raise HTTPException(status_code=400, detail=f"Tipo de documento inválido: {tipo_documento}")
    if tipo_documento == "otro" and not descripcion_otro.strip():
        raise HTTPException(status_code=400, detail="Indica una descripción para el tipo de documento 'Otro'.")

    corte = corte_por_numero(db, corte_numero)
    if corte is None:
        raise HTTPException(status_code=404, detail=f"Corte {corte_numero} no existe.")

    entrega = obtener_o_crear_entrega(db, usuario.id, periodo_id, corte.id)

    contenido = archivo.file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    periodo_nombre = entrega.periodo.nombre
    nombre_archivo = archivo.filename or "archivo"
    veredicto = analizar_documento(nombre_archivo, contenido, usuario.nombre_completo)

    try:
        ruta_relativa, tamano = guardar_archivo_entrega(
            periodo_nombre, usuario.id, corte_numero, tipo_documento, nombre_archivo, contenido
        )
    except ArchivoInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    agregar_documento_entrega(
        db,
        entrega.id,
        tipo_documento,
        nombre_archivo,
        ruta_relativa,
        tamano,
        materia=materia.strip() or None,
        descripcion_otro=descripcion_otro.strip() or None,
        firma_detectada=veredicto["firma_detectada"],
        firma_confianza=veredicto["confianza"],
        firma_detalle=veredicto["detalle"],
    )

    if veredicto["firma_detectada"] is not True:
        tipo_label = TIPOS_DOCUMENTO_ENTREGA.get(tipo_documento, tipo_documento)
        accion = "no detectó firma" if veredicto["firma_detectada"] is False else "no pudo confirmar la firma"
        mensaje = (
            f"⚠️ {usuario.nombre_completo} subió '{nombre_archivo}' ({tipo_label}) para el {corte.nombre} — "
            f"el agente {accion} ({veredicto['detalle']}). Revísalo antes de aprobar la entrega."
        )
        notificar_usuarios(db, ids_personal_revisor(db), mensaje, entrega_id=entrega.id)

    return _out(entrega_con_detalle(db, entrega.id))


@router.delete("/documentos/{documento_id}")
def borrar_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles("docente", *ROLES_REVISORES)),
):
    documento = documento_entrega_por_id(db, documento_id)
    if documento is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    entrega = entrega_con_detalle(db, documento.entrega_id)
    _verificar_acceso_entrega(entrega, usuario)

    eliminar_documento_entrega(db, documento_id)
    return {"ok": True}


@router.get("/documentos/{documento_id}/descargar")
def descargar_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles("docente", *ROLES_REVISORES)),
):
    documento = documento_entrega_por_id(db, documento_id)
    if documento is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    entrega = entrega_con_detalle(db, documento.entrega_id)
    _verificar_acceso_entrega(entrega, usuario)

    if usuario.rol.nombre in ROLES_REVISORES:
        marcar_documento_visto(db, documento_id)

    ruta = ruta_absoluta_segura(documento.ruta_archivo)
    if ruta is None:
        raise HTTPException(status_code=404, detail="El archivo ya no existe en el servidor.")

    # Solo pdf/jpg/jpeg/png se muestran inline (botón "👁️ Ver"); cualquier
    # otra extensión se fuerza a descarga binaria -- nunca se confía en
    # mimetypes.guess_type() sobre un nombre que escribió el usuario.
    media_type, disposicion = tipo_y_disposicion(documento.nombre_archivo)
    nombre_header = nombre_seguro_para_header(documento.nombre_archivo)
    buffer = io.BytesIO(ruta.read_bytes())
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'{disposicion}; filename="{nombre_header}"'},
    )


@router.post("/documentos/{documento_id}/confirmar-revision", response_model=EntregaOut)
def confirmar_revision(
    documento_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_REVISORES)),
):
    documento = documento_entrega_por_id(db, documento_id)
    if documento is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    entrega = entrega_con_detalle(db, documento.entrega_id)
    _verificar_acceso_entrega(entrega, usuario)

    try:
        confirmar_revision_documento(db, documento_id, usuario.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return _out(entrega_con_detalle(db, documento.entrega_id))


@router.post("/{entrega_id}/aprobar", response_model=EntregaOut)
def aprobar(
    entrega_id: int,
    datos: AprobarEntregaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_REVISORES)),
):
    try:
        entrega = aprobar_entrega(db, entrega_id, usuario.id, datos.comentario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    destinatarios = emails_personal_revisor(db)
    enviado, error = notificar_entrega_aprobada(
        entrega.docente.nombre_completo,
        entrega.docente.email,
        entrega.periodo.nombre,
        entrega.corte.nombre,
        usuario.nombre_completo,
        destinatarios,
    )
    marcar_notificacion_entrega(db, entrega_id, enviado, error)

    mensaje = (
        f"La entrega de {entrega.docente.nombre_completo} ({entrega.periodo.nombre}, {entrega.corte.nombre}) "
        f"fue APROBADA por {usuario.nombre_completo}."
    )
    destinatarios_ids = ids_personal_revisor(db) + [entrega.docente_id]
    notificar_usuarios(db, destinatarios_ids, mensaje, entrega_id=entrega.id)

    return _out(entrega_con_detalle(db, entrega_id))


@router.post("/{entrega_id}/rechazar", response_model=EntregaOut)
def rechazar(
    entrega_id: int,
    datos: RechazarEntregaIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_REVISORES)),
):
    try:
        entrega = rechazar_entrega(db, entrega_id, usuario.id, datos.comentario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    mensaje = (
        f"La entrega de {entrega.docente.nombre_completo} ({entrega.periodo.nombre}, {entrega.corte.nombre}) "
        f"fue RECHAZADA por {usuario.nombre_completo}: {datos.comentario}"
    )
    destinatarios_ids = ids_personal_revisor(db) + [entrega.docente_id]
    notificar_usuarios(db, destinatarios_ids, mensaje, entrega_id=entrega.id)

    return _out(entrega_con_detalle(db, entrega_id))
