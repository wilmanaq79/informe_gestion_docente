"""Vista del Director del Programa y del Secretario Academico: resumen de
los docentes, detalle por materia/corte, generacion del informe PDF por
docente, y administracion de usuarios (altas de las cuentas de los 27
docentes, el director y el secretario).

Filtrable por Año, Semestre (cada Año tiene 2 semestres) y Corte (cada
semestre tiene 3 cortes) -- igual que en el frontend React."""
from pathlib import Path

import pandas as pd
import streamlit as st

from agente_notas.reporte_pdf import describir_alcance, generar_reporte_docente
from db.auth import hash_password
from db.database import get_session
from db.repository import (
    activar_periodo,
    crear_o_obtener_periodo,
    crear_usuario,
    listar_docentes,
    listar_periodos,
    listar_roles,
    listar_usuarios,
    resolver_periodo_ids,
)
from vistas import calendario, entregas, repositorio_asignaturas


def _seccion_periodo_actual(session):
    """Periodo 'actual' del sistema: donde caen las notas que los
    docentes cargan hoy. Solo Director/Secretario pueden crearlo/activarlo."""
    st.subheader("🟢 Periodo actual del sistema")
    st.caption(
        "Es el periodo donde caen las notas que los docentes cargan hoy. Al iniciar un semestre nuevo, "
        "créalo (si no existe) y actívalo aquí."
    )
    periodos = listar_periodos(session)
    filas = [{"Periodo": p.nombre, "Estado": "🟢 Activo" if p.activo else "—", "id": p.id} for p in periodos]
    for fila in filas:
        col1, col2, col3 = st.columns([2, 2, 3])
        col1.write(fila["Periodo"])
        col2.write(fila["Estado"])
        if fila["Estado"] == "—":
            if col3.button("Activar como periodo actual", key=f"activar_periodo_{fila['id']}"):
                activar_periodo(session, fila["id"])
                st.rerun()

    with st.expander("➕ Crear un nuevo periodo (p. ej. el próximo semestre)"):
        with st.form("crear_periodo_form"):
            col1, col2 = st.columns(2)
            anio_nuevo = col1.number_input("Año", min_value=2000, max_value=2100, value=2026, step=1)
            semestre_nuevo = col2.selectbox("Semestre", [1, 2])
            crear = st.form_submit_button("Crear periodo", use_container_width=True)
        if crear:
            crear_o_obtener_periodo(session, int(anio_nuevo), int(semestre_nuevo))
            st.success(f"Periodo {int(anio_nuevo)}-{semestre_nuevo} creado (o ya existía).")
            st.rerun()


def _selector_alcance(session):
    """Selectbox de Año / Semestre / Corte. Devuelve (anio, semestre,
    corte, periodo_ids, etiqueta) -- semestre y corte son None si el
    usuario elige 'ambos'/'más reciente'."""
    periodos = listar_periodos(session)
    if not periodos:
        st.warning("No hay periodos académicos registrados todavía. Ejecuta 'python -m db.seed'.")
        return None, None, None, [], ""

    anios = sorted({p.anio for p in periodos}, reverse=True)
    col1, col2, col3 = st.columns(3)
    anio_sel = col1.selectbox("Año", anios, key="direccion_anio_sel")

    # Cada Año académico tiene siempre 2 semestres (así no haya informes
    # cargados todavía para uno de ellos, p.ej. el semestre que aún no arranca).
    opciones_semestre = ["Todo el año (ambos semestres)", "Semestre 1", "Semestre 2"]
    semestre_txt = col2.selectbox("Semestre", opciones_semestre, key="direccion_semestre_sel")
    semestre_sel = None if semestre_txt.startswith("Todo el año") else int(semestre_txt.split()[-1])

    opciones_corte = ["Más reciente cargado", "Corte 1", "Corte 2", "Corte 3 / Final"]
    corte_txt = col3.selectbox("Corte", opciones_corte, key="direccion_corte_sel")
    corte_sel = {"Más reciente cargado": None, "Corte 1": 1, "Corte 2": 2, "Corte 3 / Final": 3}[corte_txt]

    periodo_ids = resolver_periodo_ids(session, anio_sel, semestre_sel)
    etiqueta = describir_alcance(anio_sel, semestre_sel, corte_sel)
    return anio_sel, semestre_sel, corte_sel, periodo_ids, etiqueta


def render():
    st.caption(
        "Resumen de todos los docentes del Programa de Ingeniería de Sistemas, con acceso al detalle e "
        "informe PDF de cada uno."
    )

    session = get_session()
    try:
        st.subheader("🗓️ Año · Semestre · Corte")
        st.caption(
            "Elige el alcance de los informes. Cada Año tiene 2 semestres y cada semestre tiene 3 cortes."
        )
        anio_sel, semestre_sel, corte_sel, periodo_ids, etiqueta_alcance = _selector_alcance(session)

        _seccion_periodo_actual(session)
        st.divider()
        calendario.render(puede_editar=True)
        st.divider()

        docentes = listar_docentes(session)

        if not docentes:
            st.info(
                "Todavía no hay docentes registrados. Usa 'Administración de usuarios' "
                "más abajo para crear sus cuentas."
            )
        elif not periodo_ids:
            pass
        else:
            filas_resumen = []
            for d in docentes:
                asignaciones_periodo = [a for a in d.asignaciones if a.periodo_id in periodo_ids]
                total_informes = sum(len(a.informes) for a in asignaciones_periodo)
                if corte_sel is not None:
                    ultimo_corte = corte_sel if any(
                        i.corte.numero == corte_sel for a in asignaciones_periodo for i in a.informes
                    ) else None
                else:
                    ultimo_corte = max(
                        (informe.corte.numero for a in asignaciones_periodo for informe in a.informes),
                        default=None,
                    )
                filas_resumen.append(
                    {
                        "Docente": d.nombre_completo,
                        "Materias este alcance": len(asignaciones_periodo),
                        "Informes cargados": total_informes,
                        "Último corte reportado": "—" if ultimo_corte is None else f"Corte {ultimo_corte}" if ultimo_corte < 3 else "Corte 3 / Final",
                    }
                )
            st.dataframe(pd.DataFrame(filas_resumen), use_container_width=True, hide_index=True)

            st.subheader("Detalle e informe PDF por docente")
            docente_sel_nombre = st.selectbox(
                "Selecciona un docente", [d.nombre_completo for d in docentes], key="direccion_docente_sel"
            )
            docente_sel = next(d for d in docentes if d.nombre_completo == docente_sel_nombre)
            asignaciones_periodo = [a for a in docente_sel.asignaciones if a.periodo_id in periodo_ids]

            if not asignaciones_periodo:
                st.warning(f"{docente_sel.nombre_completo} no tiene materias cargadas para {etiqueta_alcance}.")
            else:
                for a in asignaciones_periodo:
                    with st.expander(f"{a.asignatura}" + (f" — Grupo {a.grupo}" if a.grupo else ""), expanded=False):
                        informes = sorted(a.informes, key=lambda i: i.corte.numero)
                        if corte_sel is not None:
                            informes = [i for i in informes if i.corte.numero == corte_sel]
                        if not informes:
                            st.write(
                                f"Sin informe cargado para el Corte {corte_sel}."
                                if corte_sel is not None
                                else "Sin informes cargados todavía."
                            )
                            continue
                        filas = []
                        for informe in informes:
                            filas.append(
                                {
                                    "Corte": informe.corte.nombre,
                                    "Matriculados": informe.matriculados,
                                    "Asist. regular": informe.asistencia_regular if informe.asistencia_regular is not None else "—",
                                    "Evaluados": informe.evaluados,
                                    "Aprobaron": informe.aprobaron,
                                    "Promedio": None if informe.promedio is None else round(float(informe.promedio), 1),
                                    "Desv. estándar": None if informe.desviacion is None else round(float(informe.desviacion), 1),
                                }
                            )
                        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

                if st.button("📄 Generar informe PDF de este docente", use_container_width=True):
                    out_path = Path.cwd() / f"__informe_temp_docente_{docente_sel.id}.pdf"
                    try:
                        generar_reporte_docente(
                            docente_sel, out_path, etiqueta_alcance, periodo_ids=periodo_ids, corte_filtro=corte_sel
                        )
                        with open(out_path, "rb") as f:
                            st.download_button(
                                "⬇️ Descargar informe PDF",
                                data=f.read(),
                                file_name=f"Informe_{docente_sel.nombre_completo.replace(' ', '_')}_{anio_sel}"
                                + (f"-{semestre_sel}" if semestre_sel else "")
                                + ".pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )
                    finally:
                        out_path.unlink(missing_ok=True)
    finally:
        session.close()

    st.divider()
    entregas.render(st.session_state["usuario_id"], st.session_state["usuario_rol"])

    st.divider()
    st.subheader("👤 Administración de usuarios")
    st.caption("Crea aquí las cuentas de los 27 docentes, el Director y el Secretario Académico.")

    with st.expander("➕ Crear nuevo usuario"):
        with st.form("crear_usuario_form", clear_on_submit=True):
            nombre = st.text_input("Nombre completo")
            col1, col2 = st.columns(2)
            cedula = col1.text_input("Cédula (opcional)")
            email = col2.text_input("Correo (opcional)")
            col3, col4 = st.columns(2)
            username = col3.text_input("Usuario (para iniciar sesión)")
            password = col4.text_input("Contraseña temporal", type="password")
            rol_sel = st.selectbox("Rol", ["docente", "director", "secretario", "secretaria_programa"])
            crear = st.form_submit_button("Crear usuario", use_container_width=True)

        if crear:
            if not (nombre and username and password):
                st.error("Nombre, usuario y contraseña son obligatorios.")
            else:
                session = get_session()
                try:
                    roles = {r.nombre: r.id for r in listar_roles(session)}
                    crear_usuario(session, nombre, cedula, email, username, hash_password(password), roles[rol_sel])
                    st.success(f"Usuario '{username}' creado con rol '{rol_sel}'.")
                except Exception as exc:
                    session.rollback()
                    st.error(f"No se pudo crear el usuario (¿usuario o cédula repetidos?): {exc}")
                finally:
                    session.close()

    with st.expander("Ver usuarios registrados"):
        session = get_session()
        try:
            usuarios = listar_usuarios(session)
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Nombre": u.nombre_completo,
                            "Usuario": u.username,
                            "Rol": u.rol.nombre,
                            "Activo": "Sí" if u.activo else "No",
                        }
                        for u in usuarios
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        finally:
            session.close()

    st.divider()
    repositorio_asignaturas.render(st.session_state["usuario_id"], st.session_state["usuario_rol"])
