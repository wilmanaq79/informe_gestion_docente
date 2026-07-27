"""Vista del Director del Programa y del Secretario Academico: resumen de
los docentes, detalle por materia/corte, generacion del informe PDF por
docente, y administracion de usuarios (altas de las cuentas de los 27
docentes, el director y el secretario)."""
from pathlib import Path

import pandas as pd
import streamlit as st

from agente_notas.reporte_pdf import generar_reporte_docente
from db.auth import hash_password
from db.database import get_session
from db.repository import crear_usuario, listar_docentes, listar_roles, listar_usuarios

PERIODO_ACTUAL = "2026-1"


def render():
    st.caption(
        "Resumen de todos los docentes del Programa de Ingeniería de Sistemas para el "
        f"periodo **{PERIODO_ACTUAL}**, con acceso al detalle e informe PDF de cada uno."
    )

    session = get_session()
    try:
        docentes = listar_docentes(session)

        if not docentes:
            st.info(
                "Todavía no hay docentes registrados. Usa 'Administración de usuarios' "
                "más abajo para crear sus cuentas."
            )
        else:
            filas_resumen = []
            for d in docentes:
                asignaciones_periodo = [a for a in d.asignaciones if a.periodo.nombre == PERIODO_ACTUAL]
                total_informes = sum(len(a.informes) for a in asignaciones_periodo)
                ultimo_corte = max(
                    (informe.corte.numero for a in asignaciones_periodo for informe in a.informes),
                    default=None,
                )
                filas_resumen.append(
                    {
                        "Docente": d.nombre_completo,
                        "Materias este periodo": len(asignaciones_periodo),
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
            asignaciones_periodo = [a for a in docente_sel.asignaciones if a.periodo.nombre == PERIODO_ACTUAL]

            if not asignaciones_periodo:
                st.warning(f"{docente_sel.nombre_completo} no tiene materias cargadas en {PERIODO_ACTUAL}.")
            else:
                for a in asignaciones_periodo:
                    with st.expander(f"{a.asignatura}" + (f" — Grupo {a.grupo}" if a.grupo else ""), expanded=False):
                        if not a.informes:
                            st.write("Sin informes cargados todavía.")
                            continue
                        filas = []
                        for informe in sorted(a.informes, key=lambda i: i.corte.numero):
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
                        generar_reporte_docente(docente_sel, out_path, PERIODO_ACTUAL)
                        with open(out_path, "rb") as f:
                            st.download_button(
                                "⬇️ Descargar informe PDF",
                                data=f.read(),
                                file_name=f"Informe_{docente_sel.nombre_completo.replace(' ', '_')}_{PERIODO_ACTUAL}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )
                    finally:
                        out_path.unlink(missing_ok=True)
    finally:
        session.close()

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
            rol_sel = st.selectbox("Rol", ["docente", "director", "secretario"])
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
