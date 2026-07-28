"""Repositorio de consulta de sílabos y programas de asignatura por
materia. Cualquier rol puede consultar, buscar por materia y descargar.
Director, Secretario Académico y Secretaria del Programa cargan el
sílabo, crean/renombran asignaturas, reasignan el docente y eliminan.
Cada docente actualiza (sube o quita) el programa de asignatura
únicamente de la materia que él mismo dicta. Se llama desde
vistas/docente.py, vistas/direccion.py y app.py (secretaria_programa)."""
import streamlit as st

from agente_notas.almacenamiento import guardar_archivo_repositorio, ruta_absoluta_segura
from db.database import get_session
from db.repository import (
    actualizar_repositorio_asignatura,
    adjuntar_programa,
    adjuntar_silabo,
    crear_repositorio_asignatura,
    eliminar_repositorio_asignatura,
    listar_repositorio_asignaturas,
    listar_usuarios,
    quitar_programa,
    quitar_silabo,
)

ROLES_ADMIN = ("director", "secretario", "secretaria_programa")


def _formatear_tamano(bytes_: int | None) -> str:
    if bytes_ is None:
        return "—"
    if bytes_ < 1024:
        return f"{bytes_} B"
    if bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    return f"{bytes_ / (1024 * 1024):.1f} MB"


def _formatear_fecha(dt) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")


def _bloque_archivo(session, entrada, tipo: str, puede_editar_este: bool, usuario_id: int):
    es_silabo = tipo == "silabo"
    nombre = entrada.silabo_nombre_archivo if es_silabo else entrada.programa_nombre_archivo
    tamano = entrada.silabo_tamano_bytes if es_silabo else entrada.programa_tamano_bytes
    ruta = entrada.silabo_ruta_archivo if es_silabo else entrada.programa_ruta_archivo
    etiqueta = "Sílabo" if es_silabo else "Programa de asignatura"

    st.markdown(f"**{etiqueta}**")
    if nombre:
        st.write(f"{nombre} ({_formatear_tamano(tamano)})")
        ruta_abs = ruta_absoluta_segura(ruta)
        col_desc, col_quitar = st.columns(2)
        if ruta_abs is not None:
            col_desc.download_button(
                f"⬇️ Descargar {etiqueta.lower()}",
                data=ruta_abs.read_bytes(),
                file_name=nombre,
                key=f"repo_descargar_{tipo}_{entrada.id}",
                use_container_width=True,
            )
        if puede_editar_este:
            if col_quitar.button(f"🗑️ Quitar {etiqueta.lower()}", key=f"repo_quitar_{tipo}_{entrada.id}", use_container_width=True):
                (quitar_silabo if es_silabo else quitar_programa)(session, entrada.id, usuario_id)
                st.success(f"{etiqueta} quitado.")
                st.rerun()
    else:
        st.caption(f"No hay {etiqueta.lower()} cargado.")

    if puede_editar_este:
        with st.form(f"repo_form_{tipo}_{entrada.id}", clear_on_submit=True):
            archivo = st.file_uploader(
                f"Subir/reemplazar {etiqueta.lower()}", type=["pdf", "doc", "docx"], key=f"repo_uploader_{tipo}_{entrada.id}"
            )
            enviar = st.form_submit_button(f"Subir {etiqueta.lower()}")
        if enviar:
            if archivo is None:
                st.error("Selecciona un archivo.")
            else:
                contenido = archivo.getvalue()
                ruta_relativa, tam = guardar_archivo_repositorio(entrada.id, tipo, archivo.name, contenido)
                (adjuntar_silabo if es_silabo else adjuntar_programa)(
                    session, entrada.id, archivo.name, ruta_relativa, tam, usuario_id
                )
                st.success(f"{etiqueta} actualizado.")
                st.rerun()


def render(usuario_id: int, rol: str):
    es_admin = rol in ROLES_ADMIN

    st.subheader("📚 Repositorio de sílabos y programas de asignatura")
    st.caption(
        "Consulta y descarga el sílabo y el programa de asignatura de cada materia."
        + (
            " Tú cargas y actualizas el sílabo; cada docente actualiza el programa de la asignatura que dicta."
            if es_admin
            else " Puedes actualizar el programa de asignatura únicamente de la materia que tú dictas."
            if rol == "docente"
            else ""
        )
    )

    session = get_session()
    try:
        busqueda = st.text_input("Buscar por asignatura o docente", key="repo_busqueda", placeholder="Ej: Sistemas Operativos")
        entradas = listar_repositorio_asignaturas(session, busqueda=busqueda.strip() or None)

        docentes = []
        if es_admin:
            docentes = [u for u in listar_usuarios(session) if u.rol.nombre == "docente"]

        if not entradas:
            st.info("No hay asignaturas registradas en el repositorio todavía.")
        else:
            for entrada in entradas:
                puede_editar_programa = es_admin or (rol == "docente" and entrada.docente_id == usuario_id)
                titulo = f"{entrada.asignatura} — {entrada.docente.nombre_completo if entrada.docente else 'sin docente asignado'}"
                with st.expander(titulo):
                    if es_admin:
                        opciones_doc = {"— Sin asignar —": None}
                        for d in docentes:
                            opciones_doc[d.nombre_completo] = d.id
                        actual = entrada.docente.nombre_completo if entrada.docente else "— Sin asignar —"
                        claves = list(opciones_doc.keys())
                        indice = claves.index(actual) if actual in claves else 0
                        elegido = st.selectbox(
                            "Docente que la dicta", claves, index=indice, key=f"repo_docente_{entrada.id}"
                        )
                        if opciones_doc[elegido] != entrada.docente_id:
                            actualizar_repositorio_asignatura(
                                session, entrada.id, usuario_id, docente_id=opciones_doc[elegido]
                            )
                            st.rerun()
                    else:
                        st.caption(f"Docente: {entrada.docente.nombre_completo if entrada.docente else 'sin asignar'}")

                    _bloque_archivo(session, entrada, "silabo", es_admin, usuario_id)
                    _bloque_archivo(session, entrada, "programa", puede_editar_programa, usuario_id)

                    st.caption(
                        f"Cargado: {_formatear_fecha(entrada.creado_en)} por "
                        f"{entrada.creado_por.nombre_completo if entrada.creado_por else '—'} · "
                        f"Última actualización: {_formatear_fecha(entrada.actualizado_en)} por "
                        f"{entrada.actualizado_por.nombre_completo if entrada.actualizado_por else '—'}"
                    )

                    if es_admin:
                        if st.button(
                            "🗑️ Eliminar asignatura del repositorio", key=f"repo_eliminar_{entrada.id}"
                        ):
                            eliminar_repositorio_asignatura(session, entrada.id)
                            st.success("Asignatura eliminada del repositorio.")
                            st.rerun()

        if es_admin:
            with st.expander("➕ Agregar asignatura al repositorio"):
                opciones_doc = {"— Sin asignar —": None}
                for d in docentes:
                    opciones_doc[d.nombre_completo] = d.id
                with st.form("repo_crear_form", clear_on_submit=True):
                    nombre = st.text_input("Nombre de la asignatura")
                    elegido = st.selectbox("Docente que la dicta (opcional)", list(opciones_doc.keys()))
                    crear = st.form_submit_button("Agregar")
                if crear:
                    if not nombre.strip():
                        st.error("El nombre de la asignatura es obligatorio.")
                    else:
                        try:
                            crear_repositorio_asignatura(session, nombre, opciones_doc[elegido], usuario_id)
                            st.success(f"Asignatura '{nombre.strip()}' agregada al repositorio.")
                            st.rerun()
                        except Exception as exc:
                            session.rollback()
                            st.error(f"No se pudo crear (¿ya existe esa asignatura?): {exc}")
    finally:
        session.close()
