"""Entrega de documentos del docente (listas de asistencia, notas
firmadas, informe de gestión docente, etc.) por periodo y corte.

Cualquiera de los tres roles administrativos -- Director, Secretario
Académico o Secretaria del Programa -- puede revisar, aprobar o
rechazar una entrega. Al aprobarla se notifica por correo a los tres
roles y al docente. Se llama desde vistas/docente.py (modo docente) y
vistas/direccion.py / app.py (modo revisor)."""
import base64

import pandas as pd
import streamlit as st

from agente_notas.agente_firmas import analizar_documento, resumen_entrega
from agente_notas.almacenamiento import guardar_archivo_entrega, ruta_absoluta_segura
from agente_notas.notificaciones import notificar_entrega_aprobada
from db.database import get_session
from db.models import TIPOS_DOCUMENTO_ENTREGA
from db.repository import (
    agregar_documento_entrega,
    aprobar_entrega,
    buscar_entrega,
    confirmar_revision_documento,
    corte_por_numero,
    eliminar_documento_entrega,
    emails_personal_revisor,
    entrega_con_detalle,
    ids_personal_revisor,
    listar_entregas,
    listar_periodos,
    listar_usuarios,
    marcar_documento_visto,
    marcar_notificacion_entrega,
    materias_del_docente,
    notificar_usuarios,
    obtener_o_crear_entrega,
    rechazar_entrega,
)

ROLES_REVISORES = ("director", "secretario", "secretaria_programa")

CORTE_NOMBRE = {1: "Corte 1", 2: "Corte 2", 3: "Corte 3 / Final"}
ESTADO_LABEL = {
    "pendiente": "⏳ Pendiente de revisión",
    "aprobado": "✅ Aprobada",
    "rechazado": "❌ Rechazada — hay que volver a cargar",
}


def _formatear_tamano(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB"


def _etiqueta_firma(d) -> str:
    if d.firma_detectada is True:
        return "✅ Firmado"
    if d.firma_detectada is False:
        return "❌ No firmado"
    return "⚠️ Revisión manual"


def _recomendacion_firma(d) -> str:
    if d.firma_detectada is True:
        return "—"
    return "Se recomienda revisar este documento manualmente antes de aprobar."


def _necesita_revision_manual(d) -> bool:
    return d.firma_detectada is not True


def _etiqueta_revision(d) -> str:
    if not _necesita_revision_manual(d):
        return "—"
    if d.revisado_manualmente:
        nombre = d.revisado_por.nombre_completo if d.revisado_por else "revisor"
        return f"✔️ Revisado por {nombre}"
    if d.visto_en is not None:
        return "🔓 Abierto — falta confirmar"
    return "🔒 Sin abrir"


def _tabla_documentos(entrega, incluir_revision: bool = False) -> pd.DataFrame:
    filas = []
    for d in entrega.documentos:
        tipo = TIPOS_DOCUMENTO_ENTREGA.get(d.tipo_documento, d.tipo_documento)
        if d.tipo_documento == "otro" and d.descripcion_otro:
            tipo = f"{tipo} ({d.descripcion_otro})"
        fila = {
            "Tipo": tipo,
            "Materia": d.materia or "—",
            "Archivo": d.nombre_archivo,
            "Firma": _etiqueta_firma(d),
            "Recomendación": _recomendacion_firma(d),
            "Tamaño": _formatear_tamano(d.tamano_bytes),
            "Subido": d.subido_en.strftime("%d/%m/%Y %H:%M"),
        }
        if incluir_revision:
            fila["Revisión"] = _etiqueta_revision(d)
        filas.append(fila)
    return pd.DataFrame(filas)


def _banner_firmas(entrega) -> None:
    if not entrega.documentos:
        return
    resumen = resumen_entrega(entrega.documentos)
    if resumen["todos_firmados"]:
        return
    pendientes = resumen["documentos_pendientes"]
    nombres = ", ".join(d.nombre_archivo for d in pendientes)
    st.warning(
        f"⚠️ El agente marcó {len(pendientes)} documento(s) para revisar antes de aprobar: {nombres}."
    )


def _selector_anio_semestre_corte(session, key_prefix: str):
    """Selectbox de Año / Semestre / Corte (para poder consultar entregas
    de periodos anteriores, no solo el actual). Devuelve (periodo,
    corte_numero) o (None, None) si el Año/Semestre elegido no existe."""
    periodos = listar_periodos(session)
    if not periodos:
        st.warning("No hay periodos académicos registrados todavía.")
        return None, None

    anios = sorted({p.anio for p in periodos}, reverse=True)
    activo = next((p for p in periodos if p.activo), periodos[0])

    col1, col2, col3 = st.columns(3)
    anio_sel = col1.selectbox("Año", anios, index=anios.index(activo.anio), key=f"{key_prefix}_anio")
    semestre_sel = col2.selectbox("Semestre", [1, 2], index=activo.semestre - 1, key=f"{key_prefix}_semestre")
    corte_numero = col3.selectbox(
        "Corte", [1, 2, 3], format_func=lambda c: CORTE_NOMBRE[c], key=f"{key_prefix}_corte"
    )

    periodo = next((p for p in periodos if p.anio == anio_sel and p.semestre == semestre_sel), None)
    if periodo is None:
        st.info(f"No existe el periodo {anio_sel}-{semestre_sel}.")
        return None, None
    return periodo, corte_numero


def _previsualizar_documento(documento):
    """Vista previa inline (👁️ Ver) de un documento: PDF e imagenes se
    muestran directamente; otros tipos (Excel) no tienen visor nativo en
    el navegador, asi que se ofrece la descarga."""
    ruta = ruta_absoluta_segura(documento.ruta_archivo)
    if ruta is None:
        st.error("El archivo ya no existe en el servidor.")
        return

    contenido = ruta.read_bytes()
    extension = ruta.suffix.lower()
    if extension in (".jpg", ".jpeg", ".png"):
        st.image(contenido, caption=documento.nombre_archivo)
    elif extension == ".pdf":
        b64 = base64.b64encode(contenido).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600" '
            'style="border:1px solid #4a4a4a;"></iframe>',
            unsafe_allow_html=True,
        )
    else:
        st.info(f"No hay vista previa disponible para este tipo de archivo ({extension}). Descárgalo para verlo.")
        st.download_button(
            "⬇️ Descargar", data=contenido, file_name=documento.nombre_archivo, key=f"ver_descargar_{documento.id}"
        )


def render(usuario_id: int, rol: str):
    """rol: 'docente' -> sube documentos y ve el estado de su propia
    entrega. 'director'/'secretario'/'secretaria_programa' -> revisa,
    aprueba o rechaza las entregas de todos los docentes."""
    es_docente = rol == "docente"

    st.subheader("📎 Entrega de documentos")
    st.caption(
        "Listas de asistencia, notas firmadas, informe de gestión docente y demás soportes de la entrega "
        "del corte."
        + ("" if es_docente else " Revisa cada archivo y confirma que el docente cumplió con la entrega. Los "
           "documentos con Firma = Revisión manual o No firmado exigen abrir el archivo y confirmar la "
           "revisión antes de poder aprobar.")
    )

    session = get_session()
    try:
        periodo, corte_numero = _selector_anio_semestre_corte(session, "entregas")
        if periodo is None:
            return
        corte = corte_por_numero(session, corte_numero)

        if es_docente:
            _render_docente(session, usuario_id, periodo, corte, corte_numero)
        else:
            _render_revisor(session, periodo.id, corte)
    finally:
        session.close()


def _render_docente(session, usuario_id, periodo, corte, corte_numero):
    """No crea la Entrega hasta que el docente realmente suba un
    documento -- solo la busca, para no ensuciar la base de datos con
    filas vacias por el simple hecho de abrir esta pantalla."""
    # Materias ya registradas del docente en este periodo (BD) -- no
    # depende de haber pasado antes por "Cargar notas" en la misma
    # sesion de navegador, a diferencia de una lista derivada solo del
    # Excel recien subido (que ademas no sobrevive a un refresco, ver
    # db.repository.materias_del_docente).
    materias_disponibles = materias_del_docente(session, usuario_id, periodo.id)
    entrega = buscar_entrega(session, usuario_id, periodo.id, corte.id)

    if entrega is not None and entrega.documentos:
        titulo = f"{ESTADO_LABEL.get(entrega.estado, entrega.estado)} — {CORTE_NOMBRE[corte_numero]} ({len(entrega.documentos)} documento(s))"
        with st.expander(titulo, expanded=True):
            if entrega.estado == "rechazado" and entrega.comentario_revision:
                st.error(f"Motivo: {entrega.comentario_revision}")
            if entrega.estado == "aprobado" and entrega.revisado_por:
                st.caption(f"Aprobada por {entrega.revisado_por.nombre_completo} el {entrega.revisado_en.strftime('%d/%m/%Y %H:%M')}")
            _banner_firmas(entrega)
            st.dataframe(_tabla_documentos(entrega), use_container_width=True, hide_index=True)

            with st.expander("👁️ Ver un documento"):
                opciones_ver = {f"{d.tipo_documento} — {d.nombre_archivo}": d for d in entrega.documentos}
                elegido_ver = st.selectbox("Documento", list(opciones_ver.keys()), key="entregas_ver_doc_docente")
                _previsualizar_documento(opciones_ver[elegido_ver])

            if entrega.estado != "aprobado":
                with st.expander("🗑️ Borrar un documento"):
                    opciones = {f"{d.tipo_documento} — {d.nombre_archivo}": d.id for d in entrega.documentos}
                    elegido = st.selectbox("Documento", list(opciones.keys()), key="entregas_borrar_doc")
                    if st.button("Borrar documento seleccionado"):
                        eliminar_documento_entrega(session, opciones[elegido])
                        st.success("Documento borrado.")
                        st.rerun()

    hay_documentos = entrega is not None and bool(entrega.documentos)
    with st.expander("➕ Subir documento", expanded=not hay_documentos):
        with st.form("entregas_subir_form", clear_on_submit=True):
            tipo_documento = st.selectbox(
                "Tipo de documento", list(TIPOS_DOCUMENTO_ENTREGA.keys()), format_func=lambda t: TIPOS_DOCUMENTO_ENTREGA[t]
            )
            if materias_disponibles:
                materia = st.selectbox("Materia (opcional)", ["— Ninguna en particular —"] + list(materias_disponibles))
                materia = "" if materia == "— Ninguna en particular —" else materia
            else:
                materia = st.text_input(
                    "Materia (opcional)", help="Sube una plantilla en la sección 2 para elegir de una lista."
                )
            descripcion_otro = st.text_input("Descripción (obligatoria si el tipo es 'Otro')")
            archivo = st.file_uploader("Archivo (PDF, Excel o imagen)", type=["pdf", "xlsx", "jpg", "jpeg", "png"])
            subir = st.form_submit_button("Subir documento", use_container_width=True)

        if subir:
            if archivo is None:
                st.error("Selecciona un archivo.")
            elif tipo_documento == "otro" and not descripcion_otro.strip():
                st.error("Indica una descripción para el tipo de documento 'Otro'.")
            else:
                entrega_actual = obtener_o_crear_entrega(session, usuario_id, periodo.id, corte.id)
                contenido = archivo.getvalue()
                nombre_docente = st.session_state["usuario_nombre"]
                veredicto = analizar_documento(archivo.name, contenido, nombre_docente)

                ruta_relativa, tamano = guardar_archivo_entrega(
                    periodo.nombre, usuario_id, corte_numero, tipo_documento, archivo.name, contenido
                )
                agregar_documento_entrega(
                    session, entrega_actual.id, tipo_documento, archivo.name, ruta_relativa, tamano,
                    materia=materia.strip() or None, descripcion_otro=descripcion_otro.strip() or None,
                    firma_detectada=veredicto["firma_detectada"],
                    firma_confianza=veredicto["confianza"],
                    firma_detalle=veredicto["detalle"],
                )

                if veredicto["firma_detectada"] is not True:
                    tipo_label = TIPOS_DOCUMENTO_ENTREGA.get(tipo_documento, tipo_documento)
                    accion = "no detectó firma" if veredicto["firma_detectada"] is False else "no pudo confirmar la firma"
                    mensaje = (
                        f"⚠️ {nombre_docente} subió '{archivo.name}' ({tipo_label}) para el {corte.nombre} — "
                        f"el agente {accion} ({veredicto['detalle']}). Revísalo antes de aprobar la entrega."
                    )
                    notificar_usuarios(
                        session, ids_personal_revisor(session, st.session_state.get("usuario_programa_id")),
                        mensaje, entrega_id=entrega_actual.id,
                    )

                st.success("Documento subido correctamente.")
                st.rerun()


def _render_revisor(session, periodo_id, corte):
    programa_id = st.session_state.get("usuario_programa_id")
    col_estado, col_docente = st.columns(2)
    estado_txt = col_estado.selectbox(
        "Estado", ["Todos", "Pendientes", "Aprobadas", "Rechazadas"], key="entregas_estado_filtro"
    )
    estado = {"Todos": None, "Pendientes": "pendiente", "Aprobadas": "aprobado", "Rechazadas": "rechazado"}[estado_txt]

    # Filtro por nombre de docente -- se prefiere sobre buscar por
    # cédula, mas rapido de usar al revisar entregas.
    docentes = [u for u in listar_usuarios(session, programa_id) if u.rol.nombre == "docente"]
    opciones_docente = {"— Todos los docentes —": None}
    for d in docentes:
        opciones_docente[d.nombre_completo] = d.id
    docente_txt = col_docente.selectbox(
        "Filtrar por docente", list(opciones_docente.keys()), key="entregas_docente_filtro"
    )
    docente_id_filtro = opciones_docente[docente_txt]

    entregas = listar_entregas(
        session, programa_id,
        periodo_id=periodo_id, corte_id=corte.id, estado=estado,
        docente_id=docente_id_filtro,
    )
    if not entregas:
        st.info("No hay entregas para este Periodo/Corte con el filtro elegido.")
        return

    for entrega in entregas:
        titulo = f"{entrega.docente.nombre_completo} — {ESTADO_LABEL.get(entrega.estado, entrega.estado)} ({len(entrega.documentos)} documento(s))"
        with st.expander(titulo):
            if not entrega.documentos:
                st.write("Todavía no ha subido ningún documento.")
            else:
                _banner_firmas(entrega)
                st.dataframe(_tabla_documentos(entrega, incluir_revision=True), use_container_width=True, hide_index=True)
                with st.expander("👁️ Ver un documento", expanded=False):
                    opciones_ver = {f"{d.tipo_documento} — {d.nombre_archivo}": d for d in entrega.documentos}
                    elegido_ver = st.selectbox(
                        "Documento", list(opciones_ver.keys()), key=f"entregas_ver_doc_{entrega.id}"
                    )
                    doc_ver = opciones_ver[elegido_ver]
                    if st.button("👁️ Abrir / ver este documento", key=f"entregas_abrir_{entrega.id}_{doc_ver.id}"):
                        marcar_documento_visto(session, doc_ver.id)
                        st.session_state[f"entregas_previa_mostrada_{doc_ver.id}"] = True
                        st.rerun()
                    if st.session_state.get(f"entregas_previa_mostrada_{doc_ver.id}"):
                        _previsualizar_documento(doc_ver)

                pendientes_revision = [d for d in entrega.documentos if _necesita_revision_manual(d) and not d.revisado_manualmente]
                if pendientes_revision:
                    st.markdown("**Confirma la revisión manual antes de aprobar (Firma = Revisión manual o No firmado):**")
                    for d in pendientes_revision:
                        abierto = d.visto_en is not None
                        col_doc, col_btn = st.columns([3, 1])
                        col_doc.write(f"{'👁️' if abierto else '🔒'} {d.nombre_archivo}")
                        if col_btn.button(
                            "✔️ Confirmar revisión",
                            key=f"entregas_confirmar_{d.id}",
                            disabled=not abierto,
                            use_container_width=True,
                            help=None if abierto else "Primero ábrelo con '👁️ Abrir / ver este documento'.",
                        ):
                            try:
                                confirmar_revision_documento(session, d.id, st.session_state["usuario_id"])
                                st.success(f"Revisión confirmada para {d.nombre_archivo}.")
                                st.rerun()
                            except ValueError as exc:
                                st.error(str(exc))

            if entrega.comentario_revision:
                aviso = st.error if entrega.estado == "rechazado" else st.info
                aviso(f"Comentario de {entrega.revisado_por.nombre_completo if entrega.revisado_por else 'revisión'}: {entrega.comentario_revision}")
            if entrega.notificacion_error:
                st.warning(f"No se pudo enviar el correo de notificación: {entrega.notificacion_error}")

            pendientes_revision = [d for d in entrega.documentos if _necesita_revision_manual(d) and not d.revisado_manualmente]
            if pendientes_revision:
                nombres = ", ".join(d.nombre_archivo for d in pendientes_revision)
                st.warning(f"🔒 Para aprobar, abre y confirma la revisión manual de: {nombres}.")

            comentario = st.text_area(
                "Comentario (obligatorio para rechazar, opcional para aprobar)", key=f"entregas_comentario_{entrega.id}"
            )
            col_aprobar, col_rechazar = st.columns(2)
            if col_aprobar.button(
                "✅ Aprobar entrega",
                key=f"entregas_aprobar_{entrega.id}",
                disabled=not entrega.documentos or bool(pendientes_revision),
                use_container_width=True,
            ):
                _aprobar(session, entrega.id, comentario)
            if col_rechazar.button("❌ Rechazar", key=f"entregas_rechazar_{entrega.id}", use_container_width=True):
                _rechazar(session, entrega.id, comentario)


def _aprobar(session, entrega_id, comentario):
    # Segunda barrera de defensa en profundidad: no depender solo de que
    # app.py haya enrutado a esta pantalla para un rol revisor -- si esta
    # funcion llegara a invocarse desde cualquier otro punto, el chequeo
    # de rol sigue aplicando aqui mismo (igual que requiere_roles() en el
    # backend FastAPI para el endpoint equivalente).
    if st.session_state.get("usuario_rol") not in ROLES_REVISORES:
        st.error("No tienes permiso para aprobar entregas.")
        return
    entrega_previa = entrega_con_detalle(session, entrega_id)
    if entrega_previa is None or entrega_previa.programa_id != st.session_state.get("usuario_programa_id"):
        st.error("No puedes acceder a datos de otro programa académico.")
        return
    usuario_actual_id = st.session_state["usuario_id"]
    try:
        entrega = aprobar_entrega(session, entrega_id, usuario_actual_id, comentario or None)
    except ValueError as exc:
        st.error(str(exc))
        return

    destinatarios = emails_personal_revisor(session, entrega.programa_id)
    revisor_nombre = st.session_state["usuario_nombre"]
    enviado, error = notificar_entrega_aprobada(
        entrega.docente.nombre_completo, entrega.docente.email, entrega.periodo.nombre, entrega.corte.nombre,
        revisor_nombre, destinatarios,
    )
    marcar_notificacion_entrega(session, entrega_id, enviado, error)

    mensaje = (
        f"La entrega de {entrega.docente.nombre_completo} ({entrega.periodo.nombre}, {entrega.corte.nombre}) "
        f"fue APROBADA por {revisor_nombre}."
    )
    notificar_usuarios(
        session, ids_personal_revisor(session, entrega.programa_id) + [entrega.docente_id],
        mensaje, entrega_id=entrega.id,
    )

    st.success("Entrega aprobada. Se notificó por correo al Director, al Secretario Académico, a la Secretaria del Programa y al docente.")
    st.rerun()


def _rechazar(session, entrega_id, comentario):
    if st.session_state.get("usuario_rol") not in ROLES_REVISORES:
        st.error("No tienes permiso para rechazar entregas.")
        return
    entrega_previa = entrega_con_detalle(session, entrega_id)
    if entrega_previa is None or entrega_previa.programa_id != st.session_state.get("usuario_programa_id"):
        st.error("No puedes acceder a datos de otro programa académico.")
        return
    usuario_actual_id = st.session_state["usuario_id"]
    try:
        entrega = rechazar_entrega(session, entrega_id, usuario_actual_id, comentario)
    except ValueError as exc:
        st.error(str(exc))
        return

    mensaje = (
        f"La entrega de {entrega.docente.nombre_completo} ({entrega.periodo.nombre}, {entrega.corte.nombre}) "
        f"fue RECHAZADA por {st.session_state['usuario_nombre']}: {comentario}"
    )
    notificar_usuarios(
        session, ids_personal_revisor(session, entrega.programa_id) + [entrega.docente_id],
        mensaje, entrega_id=entrega.id,
    )

    st.success("Entrega rechazada. El docente verá el motivo y podrá volver a cargar los documentos.")
    st.rerun()
