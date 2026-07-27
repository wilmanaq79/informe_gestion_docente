"""
Sistema de Gestión y Autoevaluación Docente -- Programa de Ingeniería de
Sistemas, Universidad del Pacífico.

Punto de entrada de la aplicacion Streamlit: header institucional, control
de acceso (login) y enrutamiento por rol (docente / director / secretario).

Ejecutar:
    streamlit run app.py
"""
from pathlib import Path

import streamlit as st

from vistas import calendario, direccion, docente, entregas, login

RAIZ = Path(__file__).resolve().parent
ESCUDO_UNPA = RAIZ / "assets" / "escudo_unpa.jpg"
LOGO_PROGRAMA = RAIZ / "assets" / "logo_programa.png"

st.set_page_config(page_title="Gestión Docente — Ing. de Sistemas UNPA", page_icon="📋", layout="wide")


def mostrar_encabezado():
    col_izq, col_centro, col_der = st.columns([1, 4, 1])
    with col_izq:
        if ESCUDO_UNPA.exists():
            st.image(str(ESCUDO_UNPA), width=90)
    with col_centro:
        st.markdown(
            "<div style='text-align:center'>"
            "<div style='font-size:1.05rem; opacity:0.75;'>Universidad del Pacífico</div>"
            "<div style='font-size:1.6rem; font-weight:700; line-height:1.2;'>"
            "Programa de Ingeniería de Sistemas</div>"
            "<div style='font-size:1.05rem; opacity:0.85;'>"
            "📋 Sistema de Gestión y Autoevaluación Docente</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with col_der:
        if LOGO_PROGRAMA.exists():
            st.image(str(LOGO_PROGRAMA), width=140)
    st.divider()


def mostrar_barra_usuario():
    col_info, col_salir = st.columns([5, 1])
    with col_info:
        st.markdown(
            f"👋 **{st.session_state['usuario_nombre']}**  ·  "
            f"rol: *{st.session_state['usuario_rol']}*"
        )
    with col_salir:
        if st.button("Cerrar sesión", use_container_width=True):
            for clave in ["usuario_id", "usuario_nombre", "usuario_rol", "usuario_username"]:
                st.session_state.pop(clave, None)
            st.rerun()


mostrar_encabezado()

if "usuario_id" not in st.session_state:
    login.render()
else:
    mostrar_barra_usuario()
    rol = st.session_state["usuario_rol"]

    if rol == "docente":
        docente.render(st.session_state["usuario_id"])
    elif rol in ("director", "secretario"):
        direccion.render()
    elif rol == "secretaria_programa":
        st.caption(
            "Revisa las entregas documentales de los docentes (listas de asistencia, notas firmadas, "
            "informe de gestión docente) y aprueba o rechaza cada una. Al aprobar, se notifica por correo "
            "al Director, al Secretario Académico, a la Secretaria del Programa y al docente."
        )
        calendario.render(puede_editar=False)
        st.divider()
        entregas.render(st.session_state["usuario_id"], rol)
    else:
        st.error(f"Rol desconocido: {rol}")
