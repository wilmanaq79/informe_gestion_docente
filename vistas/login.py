"""Pantalla de inicio de sesion."""
import streamlit as st

from db.auth import autenticar
from db.database import get_session


def render():
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("### Iniciar sesión")
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            enviado = st.form_submit_button("Entrar", use_container_width=True)

        if enviado:
            session = get_session()
            try:
                usuario = autenticar(session, username, password)
                if usuario is not None:
                    # Extraer los datos mientras la sesion sigue abierta: el
                    # objeto queda "detached" apenas se cierra la sesion, y
                    # usuario.rol es una relacion de carga diferida (lazy).
                    datos = {
                        "usuario_id": usuario.id,
                        "usuario_nombre": usuario.nombre_completo,
                        "usuario_rol": usuario.rol.nombre,
                        "usuario_username": usuario.username,
                        "usuario_programa_id": usuario.programa_id,
                        "usuario_programa_nombre": usuario.programa.nombre if usuario.programa else None,
                    }
                else:
                    datos = None
            finally:
                session.close()

            if datos is None:
                st.error("Usuario o contraseña incorrectos, o la cuenta está inactiva.")
            else:
                st.session_state.update(datos)
                st.rerun()
