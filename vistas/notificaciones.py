"""Notificaciones dentro de la aplicación (independientes del correo):
avisos de entregas aprobadas/rechazadas, visibles para los 4 roles
(docente, director, secretario, secretaria del programa)."""
import streamlit as st

from db.database import get_session
from db.repository import (
    contar_notificaciones_no_leidas,
    listar_notificaciones,
    marcar_todas_notificaciones_leidas,
)


def render(usuario_id: int):
    session = get_session()
    try:
        no_leidas = contar_notificaciones_no_leidas(session, usuario_id)
        etiqueta = f"🔔 Notificaciones ({no_leidas} sin leer)" if no_leidas else "🔔 Notificaciones"
        with st.expander(etiqueta, expanded=no_leidas > 0):
            notificaciones = listar_notificaciones(session, usuario_id)
            if not notificaciones:
                st.caption("No tienes notificaciones todavía.")
                return

            if no_leidas > 0 and st.button("Marcar todas como leídas", key="notif_marcar_todas"):
                marcar_todas_notificaciones_leidas(session, usuario_id)
                st.rerun()

            for n in notificaciones:
                prefijo = "🔵" if not n.leida else "⚪"
                st.markdown(f"{prefijo} {n.mensaje}")
                st.caption(n.creado_en.strftime("%d/%m/%Y %H:%M"))
                st.divider()
    finally:
        session.close()
