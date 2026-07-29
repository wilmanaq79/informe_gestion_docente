"""Cambio de contrasena: gate obligatorio (cuenta con contrasena
temporal, ver Usuario.debe_cambiar_password) y accion libre disponible
en cualquier momento. Ambas comparten la misma implementacion interna
-- mismo formato que vistas/consentimiento.py (render(session,
usuario_id) -> bool para el gate)."""
import streamlit as st

from db.auth import hash_password, validar_longitud_password, verificar_password
from db.models import Usuario


def _formulario_cambio(session, usuario_id: int, key_sufijo: str) -> bool:
    """Devuelve True si la contrasena se cambio con exito en esta
    ejecucion (el caller decide si hace st.rerun())."""
    with st.form(f"cambiar_password_form_{key_sufijo}"):
        password_actual = st.text_input("Contraseña actual", type="password", key=f"pw_actual_{key_sufijo}")
        password_nueva = st.text_input("Contraseña nueva", type="password", key=f"pw_nueva_{key_sufijo}")
        confirmar = st.text_input("Confirmar contraseña nueva", type="password", key=f"pw_confirmar_{key_sufijo}")
        enviado = st.form_submit_button("Cambiar contraseña", use_container_width=True)

    if not enviado:
        return False

    usuario = session.get(Usuario, usuario_id)
    if not verificar_password(password_actual, usuario.password_hash):
        st.error("La contraseña actual no es correcta.")
        return False
    if password_nueva != confirmar:
        st.error("La confirmación no coincide con la contraseña nueva.")
        return False
    try:
        validar_longitud_password(password_nueva)
    except ValueError as exc:
        st.error(str(exc))
        return False

    usuario.password_hash = hash_password(password_nueva)
    usuario.debe_cambiar_password = False
    session.commit()
    return True


def render_forzado(session, usuario_id: int) -> bool:
    """Devuelve True si la cuenta ya tiene una contrasena definitiva (y
    por tanto puede continuar); False si se debe bloquear el resto de
    la app. Se llama ANTES que consentimiento.render() (ver app.py)."""
    usuario = session.get(Usuario, usuario_id)
    if not usuario.debe_cambiar_password:
        return True

    st.subheader("🔑 Debes cambiar tu contraseña")
    st.caption("Tu cuenta tiene una contraseña temporal. Elige una nueva para continuar.")
    if _formulario_cambio(session, usuario_id, "forzado"):
        st.session_state["usuario_debe_cambiar_password"] = False
        st.success("Contraseña actualizada.")
        st.rerun()
    return False


def render_opcional(session, usuario_id: int) -> None:
    """Accion libre disponible en cualquier momento, para cualquier rol
    -- no bloquea nada, a diferencia de render_forzado."""
    with st.expander("🔑 Cambiar mi contraseña"):
        if _formulario_cambio(session, usuario_id, "opcional"):
            st.success("Contraseña actualizada.")
