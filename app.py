"""
Sistema de Gestión y Autoevaluación Docente -- Universidad del Pacífico
(multi-programa: cada Director/Secretario/Secretaria/Docente pertenece a
un unico programa academico, ver db.models.Programa).

Punto de entrada de la aplicacion Streamlit: header institucional, control
de acceso (login) y enrutamiento por rol (docente / director / secretario).

Ejecutar:
    streamlit run app.py
"""
from pathlib import Path

import streamlit as st

from db.database import get_session
from vistas import (
    calendario,
    cambiar_password,
    consentimiento,
    direccion,
    docente,
    entregas,
    login,
    notificaciones,
    repositorio_asignaturas,
)

# Una pagina por sesion (st.navigation dibuja su propio sidebar nativo,
# sin necesidad de CSS/componentes propios) -- mismo criterio de
# agrupacion que en el frontend React (ver docs/planRediseñoNavegacion.md):
# el flujo de carga de notas del docente y el bloque
# Alcance+Dashboard+Docentes de Direccion se mantienen en una sola
# pagina cada uno porque comparten estado, el resto son paginas propias.


def _paginas_docente(usuario_id: int) -> list:
    return [
        st.Page(lambda: calendario.render(puede_editar=False), title="Calendario académico", icon="🗓️", url_path="calendario"),
        st.Page(lambda: docente.render_cargar_notas(usuario_id), title="Cargar notas (MI-DO-FO16)", icon="📥", url_path="notas", default=True),
        st.Page(lambda: entregas.render(usuario_id, "docente"), title="Entrega de documentos", icon="📎", url_path="entregas"),
        st.Page(lambda: repositorio_asignaturas.render(usuario_id, "docente"), title="Repositorio", icon="📚", url_path="repositorio"),
    ]


def _paginas_direccion(usuario_id: int, rol: str) -> list:
    return [
        st.Page(lambda: calendario.render(puede_editar=True), title="Calendario académico", icon="🗓️", url_path="calendario", default=True),
        st.Page(direccion.render_periodo, title="Periodo actual", icon="🟢", url_path="periodo"),
        st.Page(direccion.render_informes, title="Informes y seguimiento docente", icon="📊", url_path="informes"),
        st.Page(lambda: entregas.render(usuario_id, rol), title="Entregas", icon="📎", url_path="entregas"),
        st.Page(direccion.render_administracion_usuarios, title="Usuarios", icon="👤", url_path="usuarios"),
        st.Page(lambda: repositorio_asignaturas.render(usuario_id, rol), title="Repositorio", icon="📚", url_path="repositorio"),
    ]


def _paginas_secretaria(usuario_id: int, rol: str) -> list:
    return [
        st.Page(lambda: calendario.render(puede_editar=False), title="Calendario académico", icon="🗓️", url_path="calendario", default=True),
        st.Page(lambda: entregas.render(usuario_id, rol), title="Entregas", icon="📎", url_path="entregas"),
        st.Page(lambda: repositorio_asignaturas.render(usuario_id, rol), title="Repositorio", icon="📚", url_path="repositorio"),
    ]


RAIZ = Path(__file__).resolve().parent
ESCUDO_UNPA = RAIZ / "assets" / "escudo_unpa.jpg"
LOGO_PROGRAMA = RAIZ / "assets" / "logo_programa.png"

st.set_page_config(page_title="Gestión Docente — UNPA", page_icon="📋", layout="wide")


def mostrar_encabezado(programa_nombre: str | None = None):
    # Antes de iniciar sesion no se conoce el programa del usuario -- se
    # muestra un nombre generico hasta que haya sesion (ver la llamada al
    # final del archivo, que pasa el programa de session_state si existe).
    titulo_programa = f"Programa de {programa_nombre}" if programa_nombre else "Gestión Docente"
    col_izq, col_centro, col_der = st.columns([1, 4, 1])
    with col_izq:
        if ESCUDO_UNPA.exists():
            st.image(str(ESCUDO_UNPA), width=90)
    with col_centro:
        st.markdown(
            "<div style='text-align:center'>"
            "<div style='font-size:1.05rem; opacity:0.75;'>Universidad del Pacífico</div>"
            "<div style='font-size:1.6rem; font-weight:700; line-height:1.2;'>"
            f"{titulo_programa}</div>"
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
            for clave in [
                "usuario_id", "usuario_nombre", "usuario_rol", "usuario_username",
                "usuario_programa_id", "usuario_programa_nombre", "usuario_debe_cambiar_password",
            ]:
                st.session_state.pop(clave, None)
            st.rerun()


mostrar_encabezado(st.session_state.get("usuario_programa_nombre"))

if "usuario_id" not in st.session_state:
    login.render()
else:
    mostrar_barra_usuario()

    session = get_session()
    try:
        # Orden: primero la contrasena temporal (credencial sin rotar),
        # despues el aviso de privacidad -- igual que en el gate del
        # backend (ver backend/main.py, _gate).
        password_actualizada = cambiar_password.render_forzado(session, st.session_state["usuario_id"])
    finally:
        session.close()
    if not password_actualizada:
        st.stop()

    session = get_session()
    try:
        acepto_politica = consentimiento.render(session, st.session_state["usuario_id"])
    finally:
        session.close()
    if not acepto_politica:
        st.stop()

    rol = st.session_state["usuario_rol"]
    usuario_id = st.session_state["usuario_id"]
    session = get_session()
    try:
        cambiar_password.render_opcional(session, usuario_id)
    finally:
        session.close()
    notificaciones.render(usuario_id)
    st.divider()

    if rol == "docente":
        st.navigation(_paginas_docente(usuario_id)).run()
    elif rol in ("director", "secretario"):
        st.navigation(_paginas_direccion(usuario_id, rol)).run()
    elif rol == "secretaria_programa":
        st.caption(
            "Revisa las entregas documentales de los docentes (listas de asistencia, notas firmadas, "
            "informe de gestión docente) y aprueba o rechaza cada una. Al aprobar, se notifica por correo "
            "al Director, al Secretario Académico, a la Secretaria del Programa y al docente."
        )
        st.navigation(_paginas_secretaria(usuario_id, rol)).run()
    else:
        st.error(f"Rol desconocido: {rol}")
