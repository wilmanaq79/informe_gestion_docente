"""Módulo de tareas académicas y administrativas (ver
docs/especificacionModuloTareas.md): KPIs, tablero Scrum/Kanban y lista
con filtro por estado, creación, asignación/publicación y transiciones
de estado (iniciar/terminar/cancelar). Paridad con
frontend/src/components/TareasModulo.tsx."""
import base64
import io
from datetime import date

import streamlit as st

from agente_notas.almacenamiento import ArchivoInvalido, guardar_archivo_evidencia_tarea, ruta_absoluta_segura
from agente_notas.almacenamiento import eliminar_archivo as _eliminar_archivo_disco
from backend.services.reporte_tareas_pdf import generar_informe_tareas
from db.database import get_session
from db.models import Usuario
from db.repository import (
    agregar_evidencia_tarea,
    asignar_tarea,
    aprobar_tarea,
    cancelar_tarea,
    crear_tarea,
    devolver_tarea,
    eliminar_evidencia_tarea,
    enviar_a_revision_tarea,
    indicadores_tareas,
    iniciar_tarea,
    listar_categorias_tarea,
    listar_estados_tarea,
    listar_evidencias_tarea,
    listar_prioridades_tarea,
    listar_tareas,
    listar_usuarios,
    notificar_usuarios,
    publicar_tarea,
    reactivar_tarea,
    terminar_tarea,
)

ROLES_ASIGNAN = ("director", "secretario")
# Todos los roles administrativos, sin el Docente -- pedido explicito
# del usuario para reactivar una tarea Vencida.
ROLES_REACTIVAN = ("director", "secretario", "secretaria_programa")
ESTADOS_CANCELABLES = ("BORRADOR", "SIN_COMENZAR", "EN_PROCESO", "DEVUELTA_OBSERVACIONES", "PENDIENTE_REVISION")
# Una tarea Terminada o Cancelada queda cerrada: ya no se puede asignar/
# reasignar (el backend valida lo mismo en db.repository.asignar_tarea).
ESTADOS_CERRADOS = ("TERMINADA", "CANCELADA")

# Mismo mapeo de columnas que frontend/src/components/TareasModulo.tsx --
# "Story" (fila del mockup Scrum original) se representa como la
# categoria de la tarea, mostrada en cada tarjeta.
COLUMNAS_KANBAN = [
    ("📝 Por hacer", ("BORRADOR", "PROGRAMADA", "SIN_COMENZAR")),
    ("🔄 En proceso", ("EN_PROCESO", "PENDIENTE_REVISION", "DEVUELTA_OBSERVACIONES", "SUSPENDIDA")),
    ("✅ Terminada", ("TERMINADA",)),
    ("⏰ Vencida / 🔴 Cancelada", ("VENCIDA", "CANCELADA")),
]


def _es_responsable(t, usuario_id: int) -> bool:
    if t.responsable_principal_id == usuario_id:
        return True
    return any(r.usuario_id == usuario_id for r in t.responsables_secundarios)


def _puede_iniciar(t, usuario_id: int, es_admin: bool) -> bool:
    return t.estado.nombre in ("SIN_COMENZAR", "DEVUELTA_OBSERVACIONES") and (
        _es_responsable(t, usuario_id) or es_admin
    )


def _puede_terminar(t, usuario_id: int, es_admin: bool) -> bool:
    """Todo responsable siempre tiene una manera de informar que
    termino -- lo que decide _acciones_tarea con requiere_aprobacion es
    si eso cierra la tarea directo o la deja Pendiente de revision."""
    if t.estado.nombre != "EN_PROCESO":
        return False
    return _es_responsable(t, usuario_id) or es_admin


def _puede_aprobar_o_devolver(t, es_admin: bool) -> bool:
    return es_admin and t.estado.nombre == "PENDIENTE_REVISION"


def _puede_subir_evidencia(t, usuario_id: int, es_admin: bool) -> bool:
    return t.requiere_evidencia and (_es_responsable(t, usuario_id) or es_admin)


def _puede_cancelar(t, usuario_id: int, es_admin: bool) -> bool:
    if t.estado.nombre not in ESTADOS_CANCELABLES:
        return False
    if es_admin:
        return True
    return t.tipo == "personal" and t.creado_por_id == usuario_id


def _puede_asignar(t, es_admin: bool) -> bool:
    return es_admin and t.estado.nombre not in ESTADOS_CERRADOS


def _puede_reactivar(t, rol: str) -> bool:
    return t.estado.nombre == "VENCIDA" and rol in ROLES_REACTIVAN


# El boton de evidencias solo debe estar activo mientras la tarea este
# activa -- se desactiva en Terminada, Vencida o Cancelada.
ESTADOS_TAREA_INACTIVA = ("TERMINADA", "VENCIDA", "CANCELADA")


def _previsualizar_evidencia(ev):
    """Vista previa inline (👁️ Ver): PDF e imagenes se muestran
    directamente; otros tipos no tienen visor nativo en el navegador, asi
    que se ofrece la descarga. Mismo patron que
    vistas/entregas.py::_previsualizar_documento."""
    ruta = ruta_absoluta_segura(ev.ruta_archivo)
    if ruta is None:
        st.error("El archivo ya no existe en el servidor.")
        return

    contenido = ruta.read_bytes()
    extension = ruta.suffix.lower()
    if extension in (".jpg", ".jpeg", ".png"):
        st.image(contenido, caption=ev.nombre_archivo)
    elif extension == ".pdf":
        b64 = base64.b64encode(contenido).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600" '
            'style="border:1px solid #4a4a4a;"></iframe>',
            unsafe_allow_html=True,
        )
    else:
        st.info(f"No hay vista previa disponible para este tipo de archivo ({extension}). Descárgalo para verlo.")


def _notificar_cambio_estado(session, t, usuario, accion: str, detalle: str = "") -> None:
    """Espejo de backend/api/routers/tareas.py::_notificar_cambio_estado
    -- Streamlit llama a db.repository directo (no pasa por el router de
    la API), asi que sin esto ninguna transicion hecha desde Streamlit
    notificaba a nadie."""
    destinatarios = {
        t.asignado_por_id, t.creado_por_id, t.responsable_principal_id,
        *(r.usuario_id for r in t.responsables_secundarios),
    } - {None, usuario.id}
    if not destinatarios:
        return
    sufijo = f" {detalle}" if detalle else ""
    notificar_usuarios(
        session, list(destinatarios),
        f"{usuario.nombre_completo} {accion} la tarea 'TAR-{t.id:06d} — {t.titulo}'.{sufijo}",
        tarea_id=t.id,
    )


def _acciones_tarea(session, t, usuario, rol: str, es_admin: bool, docentes, sufijo: str):
    """Botones de transicion/asignacion, compartidos entre la vista
    Tablero y la vista Lista. sufijo hace unicas las keys de los widgets
    de Streamlit entre ambas vistas."""
    usuario_id = usuario.id
    if es_admin and t.estado.nombre == "BORRADOR":
        if st.button("Publicar", key=f"tarea_publicar_{sufijo}_{t.id}"):
            publicar_tarea(session, t.id, usuario_id)
            st.success("Tarea publicada.")
            st.rerun()

    if _puede_iniciar(t, usuario_id, es_admin):
        if st.button("▶️ Iniciar", key=f"tarea_iniciar_{sufijo}_{t.id}"):
            actualizada = iniciar_tarea(session, t.id)
            _notificar_cambio_estado(session, actualizada, usuario, "inició")
            st.success("Tarea iniciada.")
            st.rerun()

    if _puede_terminar(t, usuario_id, es_admin):
        cierra_directo = es_admin or not t.requiere_aprobacion
        etiqueta = "✅ Terminar" if cierra_directo else "📤 Enviar a revisión"
        if st.button(etiqueta, key=f"tarea_terminar_{sufijo}_{t.id}"):
            if cierra_directo:
                actualizada = terminar_tarea(session, t.id)
                _notificar_cambio_estado(session, actualizada, usuario, "terminó")
                st.success("Tarea terminada.")
            else:
                actualizada = enviar_a_revision_tarea(session, t.id)
                _notificar_cambio_estado(session, actualizada, usuario, "envió a revisión")
                st.success("Tarea enviada a revisión.")
            st.rerun()

    if _puede_aprobar_o_devolver(t, es_admin):
        if st.button("✔️ Aprobar", key=f"tarea_aprobar_{sufijo}_{t.id}"):
            actualizada = aprobar_tarea(session, t.id)
            _notificar_cambio_estado(session, actualizada, usuario, "aprobó y cerró")
            st.success("Tarea aprobada y cerrada.")
            st.rerun()
        motivo_devolucion = st.text_input(
            "Observaciones para el responsable", key=f"tarea_devolver_motivo_{sufijo}_{t.id}"
        )
        if st.button("↩️ Devolver", key=f"tarea_devolver_btn_{sufijo}_{t.id}"):
            if not motivo_devolucion.strip():
                st.error("Indica las observaciones de la devolución.")
            else:
                actualizada = devolver_tarea(session, t.id)
                _notificar_cambio_estado(
                    session, actualizada, usuario, "devolvió", detalle=f"Observaciones: {motivo_devolucion.strip()}"
                )
                st.success("Tarea devuelta con observaciones.")
                st.rerun()

    if _puede_asignar(t, es_admin):
        opciones_doc = {"— Elegir docente —": None}
        for d in docentes:
            opciones_doc[d.nombre_completo] = d.id
        elegido = st.selectbox("Asignar a", list(opciones_doc.keys()), key=f"tarea_asignar_sel_{sufijo}_{t.id}")
        if st.button("Confirmar asignación", key=f"tarea_asignar_btn_{sufijo}_{t.id}"):
            if opciones_doc[elegido] is None:
                st.error("Selecciona un docente.")
            else:
                asignar_tarea(session, t.id, opciones_doc[elegido], usuario_id)
                st.success("Tarea asignada.")
                st.rerun()

    if _puede_cancelar(t, usuario_id, es_admin):
        motivo = st.text_input("Motivo de cancelación", key=f"tarea_cancelar_motivo_{sufijo}_{t.id}")
        if st.button("Cancelar tarea", key=f"tarea_cancelar_btn_{sufijo}_{t.id}"):
            if not motivo.strip():
                st.error("Indica un motivo de cancelación.")
            else:
                actualizada = cancelar_tarea(session, t.id, motivo.strip())
                _notificar_cambio_estado(session, actualizada, usuario, "canceló")
                st.success("Tarea cancelada.")
                st.rerun()

    if _puede_reactivar(t, rol):
        nueva_fecha = st.date_input(
            "Nueva fecha límite", value=None, key=f"tarea_reactivar_fecha_{sufijo}_{t.id}"
        )
        if st.button("🔄 Reactivar", key=f"tarea_reactivar_btn_{sufijo}_{t.id}"):
            if not nueva_fecha:
                st.error("Indica una nueva fecha límite.")
            else:
                try:
                    actualizada = reactivar_tarea(session, t.id, nueva_fecha)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    _notificar_cambio_estado(session, actualizada, usuario, "reactivó")
                    st.success("Tarea reactivada.")
                    st.rerun()

    if t.requiere_evidencia and t.estado.nombre in ESTADOS_TAREA_INACTIVA:
        st.button(
            "📎 Evidencias", key=f"tarea_evidencia_disabled_{sufijo}_{t.id}", disabled=True,
            help="Esta tarea ya no está activa; las evidencias quedaron guardadas pero no se pueden gestionar aquí.",
        )
    elif t.requiere_evidencia:
        with st.expander("📎 Evidencias", expanded=False):
            evidencias = listar_evidencias_tarea(session, t.id)
            if not evidencias:
                st.caption("Sin evidencias adjuntas todavía.")
            for ev in evidencias:
                col_nombre, col_ver, col_descargar, col_borrar = st.columns([3, 1, 1, 1])
                col_nombre.write(f"📄 {ev.nombre_archivo} ({ev.tamano_bytes / 1024:.0f} KB)")
                if col_ver.button("👁️ Ver", key=f"tarea_evidencia_ver_{sufijo}_{t.id}_{ev.id}"):
                    st.session_state[f"tarea_evidencia_previa_{ev.id}"] = True
                    st.rerun()
                ruta_ev = ruta_absoluta_segura(ev.ruta_archivo)
                col_descargar.download_button(
                    "⬇️ Descargar", data=ruta_ev.read_bytes() if ruta_ev else b"",
                    file_name=ev.nombre_archivo, disabled=ruta_ev is None,
                    key=f"tarea_evidencia_descargar_{sufijo}_{t.id}_{ev.id}",
                )
                if (es_admin or ev.subido_por_id == usuario_id) and col_borrar.button(
                    "✕", key=f"tarea_evidencia_borrar_{sufijo}_{t.id}_{ev.id}"
                ):
                    ruta = eliminar_evidencia_tarea(session, ev.id)
                    if ruta:
                        _eliminar_archivo_disco(ruta)
                    st.rerun()
                if st.session_state.get(f"tarea_evidencia_previa_{ev.id}"):
                    _previsualizar_evidencia(ev)

            if _puede_subir_evidencia(t, usuario_id, es_admin):
                archivo = st.file_uploader(
                    "Subir evidencia", key=f"tarea_evidencia_subir_{sufijo}_{t.id}",
                    type=["pdf", "xlsx", "jpg", "jpeg", "png", "doc", "docx"],
                )
                if archivo is not None:
                    contenido = archivo.read()
                    try:
                        ruta_relativa, tamano = guardar_archivo_evidencia_tarea(t.id, archivo.name, contenido)
                    except ArchivoInvalido as exc:
                        st.error(str(exc))
                    else:
                        agregar_evidencia_tarea(session, t.id, archivo.name, ruta_relativa, tamano, usuario_id)
                        _notificar_cambio_estado(session, t, usuario, f"adjuntó la evidencia '{archivo.name}' en")
                        st.success("Evidencia subida.")
                        st.rerun()


def render(usuario_id: int, rol: str):
    es_admin = rol in ROLES_ASIGNAN
    es_secretaria_programa = rol == "secretaria_programa"

    st.subheader("📋 Tareas académicas y administrativas")
    if es_admin:
        st.caption("Crea, asigna, publica y da seguimiento a tareas institucionales o personales.")
    elif es_secretaria_programa:
        st.caption("Crea borradores de tareas; un Director o Secretario Académico los publica.")
    else:
        st.caption("Consulta tus tareas asignadas, inícialas, termínalas y crea tareas personales.")

    session = get_session()
    try:
        usuario = session.get(Usuario, usuario_id)
        categorias = listar_categorias_tarea(session)
        prioridades = listar_prioridades_tarea(session)
        estados = listar_estados_tarea(session)

        indicadores = indicadores_tareas(session, usuario)
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Total", indicadores["total"])
        k2.metric("Cumplimiento", f"{indicadores['cumplimiento_pct']}%")
        with k3:
            st.metric("Próximas a vencer", indicadores["proximas_a_vencer"])
            detalle_proximas = indicadores["proximas_a_vencer_detalle"]
            if detalle_proximas:
                with st.popover("Ver tareas", use_container_width=True):
                    for t in detalle_proximas:
                        etiqueta_dias = "vence hoy" if t["dias_restantes"] == 0 else f"vence en {t['dias_restantes']} día(s)"
                        st.write(f"**{t['codigo']}** — {t['titulo']}")
                        st.caption(
                            etiqueta_dias
                            + (f" · {t['responsable_principal_nombre']}" if t["responsable_principal_nombre"] else "")
                        )
        k4.metric("Vencidas", indicadores["vencidas"])
        k5.metric("En proceso", indicadores["por_estado"].get("EN_PROCESO", 0))
        k6.metric("Terminadas", indicadores["por_estado"].get("TERMINADA", 0))

        vista = st.radio("Vista", ["Tablero", "Lista"], horizontal=True, key="tareas_vista")

        opciones_estado = {"— Todos —": None}
        for e in estados:
            opciones_estado[f"{e.icono} {e.nombre}"] = e.nombre
        estado_sel_txt = st.selectbox("Filtrar por estado", list(opciones_estado.keys()), key="tareas_filtro_estado")
        estado_sel = opciones_estado[estado_sel_txt]

        tareas = listar_tareas(session, usuario, estado=estado_sel)

        if st.button("📄 Generar informe PDF", key="tareas_generar_informe"):
            filtros_texto = f"Estado: {estado_sel}" if estado_sel else "Todas las tareas visibles para tu rol"
            buffer = io.BytesIO()
            generar_informe_tareas(
                tareas, indicadores, buffer, usuario.programa.nombre if usuario.programa else "Gestión Docente",
                usuario.nombre_completo, filtros_texto=filtros_texto,
            )
            st.download_button(
                "⬇️ Descargar informe PDF",
                data=buffer.getvalue(),
                file_name=f"Informe_tareas_{date.today().isoformat()}.pdf",
                mime="application/pdf",
                key="tareas_descargar_informe",
            )

        docentes = []
        if es_admin:
            docentes = [u for u in listar_usuarios(session, usuario.programa_id) if u.rol.nombre == "docente"]

        if not tareas:
            st.info("No hay tareas para mostrar todavía.")
        elif vista == "Tablero":
            columnas_widgets = st.columns(len(COLUMNAS_KANBAN))
            for (titulo_columna, estados_columna), col in zip(COLUMNAS_KANBAN, columnas_widgets):
                with col:
                    tareas_columna = [t for t in tareas if t.estado.nombre in estados_columna]
                    st.markdown(f"**{titulo_columna}** ({len(tareas_columna)})")
                    for t in tareas_columna:
                        with st.container(border=True):
                            st.markdown(f"**{t.id:06d}** — {t.titulo}")
                            st.caption(
                                f"{t.categoria.nombre if t.categoria else 'Sin categoría'} · "
                                f"{t.estado.icono} {t.estado.nombre}"
                            )
                            st.caption(
                                f"{t.responsable_principal.nombre_completo if t.responsable_principal else '— Sin asignar —'}"
                                + (f" · inicia {t.fecha_inicio}" if t.fecha_inicio else "")
                                + (f" · vence {t.fecha_limite}" if t.fecha_limite else "")
                            )
                            _acciones_tarea(session, t, usuario, rol, es_admin, docentes, sufijo="tab")
        else:
            for t in tareas:
                titulo = f"TAR-{t.id:06d} — {t.titulo} [{t.estado.icono} {t.estado.nombre}]"
                with st.expander(titulo):
                    st.write(f"**Tipo:** {t.tipo} · **Categoría:** {t.categoria.nombre if t.categoria else '—'} · "
                              f"**Prioridad:** {t.prioridad.icono} {t.prioridad.nombre}")
                    st.write(
                        f"**Responsable:** {t.responsable_principal.nombre_completo if t.responsable_principal else '— Sin asignar —'} · "
                        f"**Fecha inicio:** {t.fecha_inicio or '—'} · **Fecha límite:** {t.fecha_limite or '—'}"
                    )
                    if t.descripcion:
                        st.write(t.descripcion)

                    _acciones_tarea(session, t, usuario, rol, es_admin, docentes, sufijo="lista")

        with st.expander("➕ Crear tarea"):
            with st.form("tareas_crear_form", clear_on_submit=True):
                titulo = st.text_input("Título")
                descripcion = st.text_area("Descripción")
                col1, col2 = st.columns(2)
                objetivo = col1.text_input("Objetivo")
                resultado_esperado = col2.text_input("Resultado esperado")

                if es_admin or es_secretaria_programa:
                    tipo = st.selectbox("Tipo", ["institucional", "personal"])
                else:
                    tipo = "personal"

                opciones_cat = {"— Sin categoría —": None}
                for c in categorias:
                    opciones_cat[c.nombre] = c.id
                categoria_txt = st.selectbox("Categoría", list(opciones_cat.keys()))

                opciones_prio = {f"{p.icono} {p.nombre}": p.id for p in prioridades}
                prioridad_txt = st.selectbox("Prioridad", list(opciones_prio.keys()))

                fecha_inicio = st.date_input("Fecha de inicio", value=None)
                fecha_limite = st.date_input("Fecha límite", value=None)
                requiere_evidencia = st.checkbox("Requiere evidencia")

                crear = st.form_submit_button("Crear tarea")

            if crear:
                if not titulo.strip():
                    st.error("El título es obligatorio.")
                else:
                    crear_tarea(
                        session,
                        titulo=titulo,
                        descripcion=descripcion or None,
                        objetivo=objetivo or None,
                        resultado_esperado=resultado_esperado or None,
                        tipo=tipo,
                        categoria_id=opciones_cat[categoria_txt],
                        prioridad_id=opciones_prio[prioridad_txt],
                        programa_id=usuario.programa_id,
                        fecha_inicio=fecha_inicio,
                        fecha_limite=fecha_limite,
                        requiere_evidencia=requiere_evidencia,
                        creado_por_id=usuario_id,
                        creador_rol=rol,
                    )
                    st.success(
                        "Borrador creado. Un Director o Secretario debe publicarlo."
                        if rol == "secretaria_programa"
                        else "Tarea creada."
                    )
                    st.rerun()
    finally:
        session.close()
