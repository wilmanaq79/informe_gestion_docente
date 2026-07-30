"""Repositorio de consulta de sílabos y programas de asignatura por
materia, más los formatos institucionales del programa académico
completo (gestión y autoevaluación docente, acuerdo pedagógico, plan de
actividades). Cualquier rol puede consultar, buscar por materia y
descargar. Director, Secretario Académico y Secretaria del Programa
cargan el sílabo y los formatos institucionales, crean/renombran
asignaturas, reasignan el docente y eliminan. Cada docente actualiza
(sube o quita) el programa de asignatura únicamente de la materia que
él mismo dicta. Se llama desde vistas/docente.py, vistas/direccion.py y
app.py (secretaria_programa)."""
import streamlit as st

from agente_notas.almacenamiento import (
    guardar_archivo_institucional,
    guardar_archivo_repositorio,
    ruta_absoluta_segura,
)
from db.database import get_session
from db.repository import (
    actualizar_repositorio_asignatura,
    adjuntar_archivo_repositorio,
    adjuntar_formato_institucional,
    crear_repositorio_asignatura,
    eliminar_repositorio_asignatura,
    listar_repositorio_asignaturas,
    listar_usuarios,
    materias_del_programa,
    quitar_archivo_repositorio,
    quitar_formato_institucional,
)
from db.models import Programa

ROLES_ADMIN = ("director", "secretario", "secretaria_programa")

ETIQUETA_TIPO_ARCHIVO = {
    "silabo": "Sílabo",
    "programa": "Programa de asignatura",
}
EXTENSIONES_TIPO_ARCHIVO = {
    "silabo": ["pdf", "doc", "docx"],
    "programa": ["pdf", "doc", "docx"],
}

# Los 4 formatos institucionales son un unico juego de archivos por
# PROGRAMA ACADEMICO completo (no por materia): mismo permiso que el
# silabo (solo ROLES_ADMIN suben/quitan; cualquier rol consulta/
# descarga).
ETIQUETA_TIPO_INSTITUCIONAL = {
    "gestion_docente": "Formato de gestión y autoevaluación docente",
    "acuerdo_pedagogico": "Acuerdo pedagógico",
    "plan_actividades": "Plan de actividades",
    "lista_asistencia": "Lista de asistencia",
}
EXTENSIONES_TIPO_INSTITUCIONAL = {
    "gestion_docente": ["xlsx"],
    "acuerdo_pedagogico": ["doc", "docx"],
    "plan_actividades": ["doc", "docx"],
    "lista_asistencia": ["xlsx"],
}


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
    nombre = getattr(entrada, f"{tipo}_nombre_archivo")
    tamano = getattr(entrada, f"{tipo}_tamano_bytes")
    ruta = getattr(entrada, f"{tipo}_ruta_archivo")
    etiqueta = ETIQUETA_TIPO_ARCHIVO[tipo]

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
                quitar_archivo_repositorio(session, entrada.id, tipo, usuario_id)
                st.success(f"{etiqueta} quitado.")
                st.rerun()
    else:
        st.caption(f"No hay {etiqueta.lower()} cargado.")

    if puede_editar_este:
        with st.form(f"repo_form_{tipo}_{entrada.id}", clear_on_submit=True):
            archivo = st.file_uploader(
                f"Subir/reemplazar {etiqueta.lower()}",
                type=EXTENSIONES_TIPO_ARCHIVO[tipo],
                key=f"repo_uploader_{tipo}_{entrada.id}",
            )
            enviar = st.form_submit_button(f"Subir {etiqueta.lower()}")
        if enviar:
            if archivo is None:
                st.error("Selecciona un archivo.")
            else:
                contenido = archivo.getvalue()
                try:
                    ruta_relativa, tam = guardar_archivo_repositorio(entrada.id, tipo, archivo.name, contenido)
                except Exception as exc:
                    st.error(f"No se pudo subir el archivo: {exc}")
                    return
                adjuntar_archivo_repositorio(session, entrada.id, tipo, archivo.name, ruta_relativa, tam, usuario_id)
                st.success(f"{etiqueta} actualizado.")
                st.rerun()


def _bloque_formato_institucional(session, programa: Programa, tipo: str, es_admin: bool):
    nombre = getattr(programa, f"{tipo}_nombre_archivo")
    tamano = getattr(programa, f"{tipo}_tamano_bytes")
    ruta = getattr(programa, f"{tipo}_ruta_archivo")
    etiqueta = ETIQUETA_TIPO_INSTITUCIONAL[tipo]

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
                key=f"institucional_descargar_{tipo}",
                use_container_width=True,
            )
        if es_admin:
            if col_quitar.button(f"🗑️ Quitar {etiqueta.lower()}", key=f"institucional_quitar_{tipo}", use_container_width=True):
                quitar_formato_institucional(session, programa.id, tipo)
                st.success(f"{etiqueta} quitado.")
                st.rerun()
    else:
        st.caption(f"No hay {etiqueta.lower()} cargado.")

    if es_admin:
        with st.form(f"institucional_form_{tipo}", clear_on_submit=True):
            archivo = st.file_uploader(
                f"Subir/reemplazar {etiqueta.lower()}",
                type=EXTENSIONES_TIPO_INSTITUCIONAL[tipo],
                key=f"institucional_uploader_{tipo}",
            )
            enviar = st.form_submit_button(f"Subir {etiqueta.lower()}")
        if enviar:
            if archivo is None:
                st.error("Selecciona un archivo.")
            else:
                contenido = archivo.getvalue()
                try:
                    ruta_relativa, tam = guardar_archivo_institucional(programa.id, tipo, archivo.name, contenido)
                except Exception as exc:
                    st.error(f"No se pudo subir el archivo: {exc}")
                    return
                adjuntar_formato_institucional(session, programa.id, tipo, archivo.name, ruta_relativa, tam)
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
            else " Puedes ver y descargar el sílabo, y actualizar el programa de asignatura únicamente de la "
            "materia que tú dictas."
            if rol == "docente"
            else ""
        )
    )

    programa_id = st.session_state.get("usuario_programa_id")
    session = get_session()
    try:
        with st.expander("🏛️ Formatos institucionales del programa", expanded=False):
            st.caption(
                "Gestión y autoevaluación docente, acuerdo pedagógico y plan de actividades: un único archivo "
                "por formato para todo el programa académico (no por materia)."
                + (" Tú los cargas y actualizas; cualquier docente puede verlos y descargarlos." if es_admin else " Puedes verlos y descargarlos.")
            )
            programa = session.get(Programa, programa_id)
            if programa is None:
                st.info("Programa académico no encontrado.")
            else:
                _bloque_formato_institucional(session, programa, "gestion_docente", es_admin)
                _bloque_formato_institucional(session, programa, "acuerdo_pedagogico", es_admin)
                _bloque_formato_institucional(session, programa, "plan_actividades", es_admin)
                _bloque_formato_institucional(session, programa, "lista_asistencia", es_admin)

        busqueda = st.text_input("Buscar por asignatura o docente", key="repo_busqueda", placeholder="Ej: Sistemas Operativos")
        entradas = listar_repositorio_asignaturas(session, programa_id, busqueda=busqueda.strip() or None)

        docentes = []
        if es_admin:
            docentes = [u for u in listar_usuarios(session, programa_id) if u.rol.nombre == "docente"]

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

                # Sugerencias desde las materias YA registradas en la BD
                # (asignaciones_academicas de este programa) que aun no
                # estan en el repositorio -- evita depender solo de que
                # el Director recuerde y escriba el nombre exacto. La
                # comparacion se hace en minusculas: la misma materia
                # puede estar guardada con distinta mayuscula/minuscula
                # en el repositorio ("Electiva Profesional II") y en las
                # asignaciones academicas ("ELECTIVA PROFESIONAL II").
                nombres_en_repo_normalizados = {e.asignatura.strip().lower() for e in entradas}
                materias_sugeridas = [
                    m for m in materias_del_programa(session, programa_id)
                    if m.strip().lower() not in nombres_en_repo_normalizados
                ]
                SIN_SUGERENCIA = "— Escribir el nombre manualmente —"
                sugerencia = (
                    st.selectbox(
                        "Elegir una materia ya registrada por algún docente (opcional)",
                        [SIN_SUGERENCIA] + materias_sugeridas,
                        key="repo_crear_sugerencia",
                    )
                    if materias_sugeridas
                    else SIN_SUGERENCIA
                )

                with st.form("repo_crear_form", clear_on_submit=True):
                    nombre = st.text_input(
                        "Nombre de la asignatura",
                        value="" if sugerencia == SIN_SUGERENCIA else sugerencia,
                    )
                    elegido = st.selectbox("Docente que la dicta (opcional)", list(opciones_doc.keys()))
                    crear = st.form_submit_button("Agregar")
                if crear:
                    if not nombre.strip():
                        st.error("El nombre de la asignatura es obligatorio.")
                    else:
                        try:
                            crear_repositorio_asignatura(session, nombre, opciones_doc[elegido], usuario_id, programa_id)
                            st.success(f"Asignatura '{nombre.strip()}' agregada al repositorio.")
                            st.rerun()
                        except Exception as exc:
                            session.rollback()
                            st.error(f"No se pudo crear (¿ya existe esa asignatura?): {exc}")
    finally:
        session.close()
