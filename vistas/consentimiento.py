"""Aviso de Privacidad y Autorizacion para el Tratamiento de Datos
Personales: los 4 roles deben aceptarlo antes de usar el resto del
sistema (Ley 1581 de 2012)."""
import streamlit as st

from agente_notas.aviso_privacidad import (
    TEXTO_POLITICA,
    TITULO_POLITICA,
    VERSION_POLITICA,
    acepto_politica_vigente,
)
from db.models import Usuario
from db.repository import registrar_aceptacion_tratamiento_datos


def render(session, usuario_id: int) -> bool:
    """Devuelve True si el usuario ya acepto la version VIGENTE de la
    politica (y por tanto puede continuar); False si se debe bloquear
    el resto de la app."""
    usuario = session.get(Usuario, usuario_id)
    if acepto_politica_vigente(usuario):
        return True

    st.subheader(f"🔒 {TITULO_POLITICA}")
    st.caption(
        "Debes leer y aceptar esta política antes de continuar. Aplica a los 4 roles del sistema "
        "(Docente, Director, Secretario Académico y Secretaria del Programa)."
    )

    with st.container(height=400, border=True):
        st.markdown(TEXTO_POLITICA)

    acepto = st.checkbox("He leído y acepto el tratamiento de mis datos personales conforme a lo descrito arriba.")

    col1, col2 = st.columns(2)
    if col1.button("Aceptar y continuar", disabled=not acepto, use_container_width=True, type="primary"):
        registrar_aceptacion_tratamiento_datos(session, usuario_id, VERSION_POLITICA)
        st.rerun()
    if col2.button("Cerrar sesión", use_container_width=True, key="consentimiento_cerrar_sesion"):
        for clave in ["usuario_id", "usuario_nombre", "usuario_rol", "usuario_username"]:
            st.session_state.pop(clave, None)
        st.rerun()

    return False
