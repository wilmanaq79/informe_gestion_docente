"""Calendario académico oficial de un periodo (Inicio de clases,
parciales, límites de reporte de notas por corte, etc.). Los docentes
solo lo consultan; el Director y el Secretario Académico lo
crean/editan/borran. Se llama desde vistas/docente.py (solo lectura) y
vistas/direccion.py (lectura y escritura)."""
import pandas as pd
import streamlit as st

from db.database import get_session
from db.repository import (
    actualizar_evento_calendario,
    crear_evento_calendario,
    eliminar_evento_calendario,
    listar_eventos_calendario,
    listar_periodos,
)


def _formatear_fecha(d) -> str:
    return d.strftime("%d/%m/%Y")


def _formatear_rango(inicio, fin) -> str:
    if fin is None or fin == inicio:
        return _formatear_fecha(inicio)
    return f"Del {_formatear_fecha(inicio)} al {_formatear_fecha(fin)}"


def render(puede_editar: bool):
    session = get_session()
    try:
        periodos = listar_periodos(session)
        if not periodos:
            st.warning("No hay periodos académicos registrados todavía.")
            return

        st.subheader("🗓️ Calendario académico")
        st.caption(
            "Fechas oficiales del semestre: inicio y fin de clases, parciales y límites de reporte de "
            "notas por corte."
            + ("" if puede_editar else " Solo el Director y el Secretario Académico pueden editar este calendario.")
        )

        opciones_periodo = {f"{p.nombre}{' (activo)' if p.activo else ''}": p.id for p in periodos}
        claves = list(opciones_periodo.keys())
        indice_activo = next((i for i, p in enumerate(periodos) if p.activo), 0)
        periodo_txt = st.selectbox("Periodo", claves, index=indice_activo, key="calendario_periodo_sel")
        periodo_id = opciones_periodo[periodo_txt]

        eventos = listar_eventos_calendario(session, periodo_id)
        if not eventos:
            st.info("Todavía no hay eventos cargados para este periodo.")
        else:
            filas = [{"Actividad": e.actividad, "Fechas": _formatear_rango(e.fecha_inicio, e.fecha_fin)} for e in eventos]
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

        if not puede_editar:
            return

        with st.expander("➕ Agregar evento al calendario"):
            with st.form("calendario_crear_form", clear_on_submit=True):
                actividad = st.text_input("Actividad")
                col1, col2, col3 = st.columns(3)
                fecha_inicio = col1.date_input("Fecha inicio")
                es_rango = col2.checkbox("Es un rango de fechas", key="calendario_crear_rango")
                fecha_fin = col3.date_input("Fecha fin", key="calendario_crear_fin") if es_rango else None
                orden = st.number_input("Orden en el calendario", min_value=0, value=len(eventos), step=1)
                crear = st.form_submit_button("Agregar", use_container_width=True)

            if crear:
                if not actividad:
                    st.error("La actividad es obligatoria.")
                else:
                    crear_evento_calendario(session, periodo_id, actividad, fecha_inicio, fecha_fin, int(orden))
                    st.success(f"Evento '{actividad}' agregado.")
                    st.rerun()

        if eventos:
            with st.expander("✏️ Editar o borrar un evento"):
                opciones_evento = {
                    f"{e.actividad} ({_formatear_rango(e.fecha_inicio, e.fecha_fin)})": e.id for e in eventos
                }
                evento_txt = st.selectbox("Evento", list(opciones_evento.keys()), key="calendario_evento_sel")
                evento_id = opciones_evento[evento_txt]
                evento_sel = next(e for e in eventos if e.id == evento_id)

                with st.form("calendario_editar_form"):
                    nueva_actividad = st.text_input("Actividad", value=evento_sel.actividad)
                    col1, col2, col3 = st.columns(3)
                    nueva_fecha_inicio = col1.date_input("Fecha inicio", value=evento_sel.fecha_inicio)
                    usar_rango = col2.checkbox(
                        "Es un rango de fechas", value=evento_sel.fecha_fin is not None, key="calendario_editar_rango"
                    )
                    nueva_fecha_fin = (
                        col3.date_input(
                            "Fecha fin", value=evento_sel.fecha_fin or evento_sel.fecha_inicio, key="calendario_editar_fin"
                        )
                        if usar_rango
                        else None
                    )
                    nuevo_orden = st.number_input("Orden", min_value=0, value=evento_sel.orden, step=1)
                    col_g, col_b = st.columns(2)
                    guardar = col_g.form_submit_button("Guardar cambios", use_container_width=True)
                    borrar = col_b.form_submit_button("🗑️ Borrar evento", use_container_width=True)

                if guardar:
                    actualizar_evento_calendario(
                        session, evento_id,
                        actividad=nueva_actividad, fecha_inicio=nueva_fecha_inicio,
                        fecha_fin=nueva_fecha_fin, orden=int(nuevo_orden),
                    )
                    st.success("Evento actualizado.")
                    st.rerun()
                if borrar:
                    eliminar_evento_calendario(session, evento_id)
                    st.success("Evento borrado.")
                    st.rerun()
    finally:
        session.close()
