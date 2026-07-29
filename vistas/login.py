"""Pantalla de inicio de sesion, mas el flujo de 'olvide mi contrasena'
(solicitud y restablecimiento via un enlace con token, leido de
st.query_params -- Streamlit no tiene rutas como React, asi que el
enlace enviado por correo apunta de vuelta a esta misma pantalla con
?token=...)."""
import hashlib
import os

import streamlit as st
from sqlalchemy import select

from agente_notas.notificaciones import notificar_recuperacion_password
from backend.core.rate_limit import bloqueado, registrar_intento_fallido
from db.auth import autenticar, hash_password, validar_longitud_password
from db.database import get_session
from db.models import Usuario
from db.repository import consumir_token_recuperacion, crear_token_recuperacion


def _clave_rate_limit_recuperacion(username: str) -> str:
    normalizado = username.strip().lower()
    return f"reset:{hashlib.sha256(normalizado.encode('utf-8')).hexdigest()[:16]}"


def _url_base_streamlit() -> str:
    return os.environ.get("STREAMLIT_URL", "http://localhost:8501")


def render():
    token = st.query_params.get("token")
    if token:
        _mostrar_restablecer_password(token)
        return

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
                        "usuario_debe_cambiar_password": usuario.debe_cambiar_password,
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

        with st.expander("🔑 ¿Olvidaste tu contraseña?"):
            _mostrar_solicitar_recuperacion()


def _mostrar_solicitar_recuperacion():
    with st.form("recuperacion_form"):
        username_recuperacion = st.text_input("Usuario", key="recuperacion_username")
        solicitar = st.form_submit_button("Enviar enlace de recuperación", use_container_width=True)

    if solicitar:
        session = get_session()
        try:
            clave = _clave_rate_limit_recuperacion(username_recuperacion)
            if bloqueado(session, clave):
                st.error("Demasiadas solicitudes de recuperación para este usuario. Intenta de nuevo en unos minutos.")
                return
            registrar_intento_fallido(session, clave)

            usuario = session.scalar(select(Usuario).where(Usuario.username == username_recuperacion.strip().lower()))
            if usuario is not None and usuario.activo and usuario.email:
                token = crear_token_recuperacion(session, usuario.id)
                enlace = f"{_url_base_streamlit()}/?token={token}"
                # Streamlit no tiene BackgroundTasks: el envio SMTP corre
                # sincrono dentro de este mismo callback (igual que ya es
                # sincrona la generacion de PDF en vistas/direccion.py).
                notificar_recuperacion_password(usuario.email, usuario.nombre_completo, enlace)
        finally:
            session.close()

        # Mensaje SIEMPRE generico, exista o no el usuario -- anti-enumeracion,
        # igual que POST /api/auth/solicitar-recuperacion.
        st.success("Si el usuario existe, se enviará un correo con instrucciones para recuperar la contraseña.")


def _mostrar_restablecer_password(token: str):
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("### Restablecer contraseña")
        with st.form("restablecer_password_form"):
            password_nueva = st.text_input("Contraseña nueva", type="password")
            confirmar = st.text_input("Confirmar contraseña nueva", type="password")
            enviado = st.form_submit_button("Restablecer contraseña", use_container_width=True)

        if enviado:
            if password_nueva != confirmar:
                st.error("La confirmación no coincide con la contraseña nueva.")
                return
            try:
                validar_longitud_password(password_nueva)
            except ValueError as exc:
                st.error(str(exc))
                return

            session = get_session()
            try:
                usuario = consumir_token_recuperacion(session, token)
                if usuario is None:
                    st.error("El enlace no es válido o ya expiró.")
                    return
                usuario.password_hash = hash_password(password_nueva)
                usuario.debe_cambiar_password = False
                session.commit()
            finally:
                session.close()

            st.success("Contraseña restablecida. Ya puedes iniciar sesión con tu nueva contraseña.")
            st.query_params.clear()
