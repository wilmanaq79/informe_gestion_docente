"""Vista del docente: cargar PDF de notas por materia, generar el Excel de
gestion docente y ver el dashboard de rendimiento. Ademas de escribir el
Excel, cada procesamiento se guarda en la base de datos (informes_corte +
notas_estudiantes) para que el Director y el Secretario Academico puedan
consultarlo despues."""
import uuid
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from agente_notas.core import (
    abrir_plantilla,
    analizar_progreso,
    calcular_resumen,
    escribir_bloque,
    guardar,
    leer_asistencia_excel,
    leer_pdf_notas,
    listar_materias,
)
from agente_notas.estadisticas import (
    estadisticas_materia,
    interpretar_general,
    interpretar_materia,
    resumen_general,
)
from db.database import get_session
from db.repository import (
    guardar_informe_corte,
    materias_del_docente,
    obtener_o_crear_asignacion,
    periodo_activo,
)
from vistas import calendario, entregas, repositorio_asignaturas

PALETA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
MUTED = "#898781"
GRIDLINE = "rgba(137, 135, 129, 0.35)"

CORTE_LABELS = {1: "Corte 1", 2: "Corte 2", 3: "Corte 3 / Final"}

ETIQUETA_ESTADO = {
    "asegurado": "✅ Aprobó asegurado",
    "en_riesgo": "⚠️ En riesgo",
    "matematicamente_reprobado": "❌ Ya no puede aprobar",
    "aprobado": "✅ Aprobó",
    "reprobado": "❌ Reprobó",
}


def tema_grafico(fig, **layout_kwargs):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=MUTED,
        legend_font_color=MUTED,
        **layout_kwargs,
    )
    fig.update_xaxes(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, color=MUTED)
    fig.update_yaxes(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, color=MUTED)
    return fig


def _filas_notas_para_bd(estudiantes, corte):
    """Construye las filas de notas_estudiantes (documento, notas por
    corte, Def. Pond, nota necesaria, estado) para persistir."""
    filas = []
    for e in estudiantes:
        prog = analizar_progreso(e, corte)
        filas.append(
            {
                "documento": e.get("documento"),
                "nombre_estudiante": e["nombre"],
                "corte1": e["corte1"],
                "corte2": e["corte2"] if corte >= 2 else None,
                "corte3": e["corte3"] if corte >= 3 else None,
                "def_pond": round(prog["pond"], 2),
                "nota_necesaria": None if prog["necesaria"] is None else round(prog["necesaria"], 2),
                "estado": prog["estado"],
            }
        )
    return filas


def _render_dashboard_rendimiento(subject_rows, corte):
    stats_por_materia = [
        estadisticas_materia(r["materia"], r["grupo"], r["estudiantes"], corte)
        for r in subject_rows
    ]
    general = resumen_general(stats_por_materia)

    st.caption(
        "Calculado sobre la nota definitiva de cada estudiante en los PDF cargados — "
        + ("cálculo exacto (Corte 3)." if corte == 3 else "ESTIMACIÓN proyectada (aún falta corte por calificar).")
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Promedio general (todos los estudiantes)", f"{general['promedio_general']:.1f}")
    k2.metric("Dispersión general (desv. estándar)", f"±{general['desviacion_general']:.1f}")
    if general["mejor_materia"] is not None:
        k3.metric("Mejor promedio por asignatura", f"{general['mejor_materia'].promedio:.1f} pts")
        k3.caption(general["mejor_materia"].materia)
    if general["materia_mayor_dispersion"] is not None:
        k4.metric("Asignatura con mayor dispersión", f"±{general['materia_mayor_dispersion'].desviacion:.1f}")
        k4.caption(general["materia_mayor_dispersion"].materia)

    materias_nombres = [e.materia for e in stats_por_materia]
    promedios = [round(e.promedio, 1) for e in stats_por_materia]
    mejores = [round(e.mejor_nota, 1) for e in stats_por_materia]
    desviaciones = [round(e.desviacion, 1) for e in stats_por_materia]

    col_a, col_b = st.columns(2)

    with col_a:
        fig_prom = go.Figure()
        fig_prom.add_bar(name="Promedio general", x=materias_nombres, y=promedios,
                          marker_color=PALETA[0], text=promedios, textposition="outside",
                          textfont_color=MUTED)
        fig_prom.add_bar(name="Mejor promedio", x=materias_nombres, y=mejores,
                          marker_color=PALETA[1], text=mejores, textposition="outside",
                          textfont_color=MUTED)
        tema_grafico(
            fig_prom,
            barmode="group",
            title="Promedio general vs. mejor nota por asignatura",
            yaxis_title="Nota (0-100)", yaxis_range=[0, 110],
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=70),
        )
        st.plotly_chart(fig_prom, use_container_width=True)

    with col_b:
        fig_disp = go.Figure()
        fig_disp.add_bar(x=materias_nombres, y=desviaciones, marker_color=PALETA[2],
                          text=desviaciones, textposition="outside", textfont_color=MUTED)
        tema_grafico(
            fig_disp,
            title="Dispersión (desviación estándar) por asignatura",
            yaxis_title="Desviación estándar",
            margin=dict(t=70),
        )
        st.plotly_chart(fig_disp, use_container_width=True)

    fig_box = go.Figure()
    for i, est in enumerate(stats_por_materia):
        fig_box.add_box(
            y=[n["nota"] for n in est.notas],
            name=est.materia,
            marker_color=PALETA[i % len(PALETA)],
            boxmean=True,
        )
    tema_grafico(
        fig_box,
        title="Distribución de notas por asignatura (rendimiento y dispersión de los estudiantes)",
        yaxis_title="Nota (0-100)", showlegend=False,
        margin=dict(t=70),
    )
    st.plotly_chart(fig_box, use_container_width=True)

    st.markdown("**Rendimiento por estudiante**")
    materia_foco = st.selectbox("Ver ranking de estudiantes de:", materias_nombres, key="dash_materia_foco")
    est_foco = next(e for e in stats_por_materia if e.materia == materia_foco)
    notas_ordenadas = sorted(est_foco.notas, key=lambda n: n["nota"], reverse=True)
    colores_barra = ["#0ca30c" if n["nota"] >= 60 else "#d03b3b" for n in notas_ordenadas]

    fig_rank = go.Figure()
    fig_rank.add_bar(
        x=[n["nota"] for n in notas_ordenadas],
        y=[n["nombre"] for n in notas_ordenadas],
        orientation="h",
        marker_color=colores_barra,
    )
    tema_grafico(
        fig_rank,
        title=f"Ranking de estudiantes — {materia_foco}",
        xaxis_title="Nota (0-100)", xaxis_range=[0, 105],
        height=max(320, 26 * len(notas_ordenadas)),
        yaxis=dict(autorange="reversed"),
        margin=dict(t=60, l=200),
    )
    st.plotly_chart(fig_rank, use_container_width=True)
    st.caption("🟢 Nota ≥ 60 (aprueba)  ·  🔴 Nota < 60 (reprueba)")

    with st.expander("Ver tabla completa: rendimiento por estudiante y materia"):
        filas = [
            {"Materia": e.materia, "Estudiante": n["nombre"], "Nota definitiva": n["nota"]}
            for e in stats_por_materia
            for n in e.notas
        ]
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### 🧠 Interpretación del rendimiento")
    st.caption(
        "Lectura automática de las medidas de tendencia central (promedio, mediana) y de dispersión "
        "(desviación estándar, coeficiente de variación, rango) para apoyar el análisis del docente."
    )

    st.info(interpretar_general(general, stats_por_materia))

    st.markdown("**Lectura por asignatura**")
    for est in stats_por_materia:
        with st.expander(f"{est.materia} — promedio {est.promedio:.1f}, dispersión ±{est.desviacion:.1f}"):
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Promedio", f"{est.promedio:.1f}")
            t2.metric("Mediana", f"{est.mediana:.1f}")
            t3.metric("Desv. estándar", f"±{est.desviacion:.1f}")
            t4.metric("Coef. de variación", f"{est.coef_variacion:.0f}%")
            st.write(interpretar_materia(est))


def render(usuario_id: int):
    st.caption(
        "Carga los PDF de notas de todas tus materias para un corte, confirma a qué "
        "bloque de la plantilla corresponde cada uno, y el agente genera un solo "
        "Excel con Matriculados, Asistencia regular, Evaluados y Aprobaron de todas "
        "ellas. Inasistencia y los dos porcentajes ya son fórmulas del formato: no se tocan. "
        "Cada materia procesada queda guardada en la base de datos para el Director y el "
        "Secretario Académico."
    )

    calendario.render(puede_editar=False)
    st.divider()

    st.subheader("1. Corte y plantilla")
    corte = st.radio(
        "¿A qué corte corresponden los PDF que vas a cargar?",
        options=[1, 2, 3],
        format_func=lambda c: CORTE_LABELS[c],
        horizontal=True,
        help=(
            "Corte 1 y Corte 2: Aprobados se ESTIMA (aún faltan cortes por calificar). "
            "Corte 3 / Final: cálculo exacto con los 3 cortes."
        ),
    )

    excel_file = st.file_uploader(
        "Plantilla Excel del formato de gestión docente (MI-DO-FO16)", type=["xlsx"]
    )

    materias_disponibles = []
    if excel_file is not None:
        try:
            materias_disponibles = listar_materias(excel_file)
            excel_file.seek(0)
        except Exception as exc:
            st.warning(f"No se pudo leer la lista de materias de la plantilla: {exc}")

    # Se completa con las materias YA guardadas en la base de datos para
    # este periodo -- esa parte de la lista sobrevive a un refresco de
    # pagina (que borra la plantilla Excel recien subida, porque los
    # file_uploader de Streamlit no persisten entre refrescos) y tambien
    # sobrevive a cerrar sesion, porque viene de datos ya confirmados,
    # no de un archivo en memoria de esta ejecucion.
    session_materias = get_session()
    try:
        periodo_para_materias = periodo_activo(session_materias)
        if periodo_para_materias is not None:
            materias_bd = materias_del_docente(session_materias, usuario_id, periodo_para_materias.id)
            materias_disponibles = list(materias_disponibles) + [
                m for m in materias_bd if m not in materias_disponibles
            ]
    finally:
        session_materias.close()

    st.subheader("2. PDF de notas por materia")
    st.write("Sube uno o varios PDF (uno por cada materia que dictas este corte).")
    pdf_files = st.file_uploader(
        "PDF de notas (reporte 'Ver Calificaciones' de Academusoft)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    subject_rows = []
    if pdf_files:
        if not materias_disponibles:
            st.warning("Carga primero la plantilla Excel para poder mapear cada PDF a su materia.")
        st.subheader("3. Confirma la materia y la asistencia de cada PDF")
        for i, pdf_file in enumerate(pdf_files):
            pdf_file.seek(0)
            try:
                materia_detectada, grupo, estudiantes = leer_pdf_notas(pdf_file)
            except Exception as exc:
                st.error(f"No se pudo leer '{pdf_file.name}': {exc}")
                continue

            indice_defecto = 0
            if materia_detectada and materias_disponibles:
                for idx, m in enumerate(materias_disponibles):
                    if materia_detectada.strip().lower() in m.strip().lower():
                        indice_defecto = idx
                        break

            with st.expander(
                f"📄 {pdf_file.name} → detectado: {materia_detectada or '¿?'}  ({grupo or 'grupo N/D'})  · {len(estudiantes)} estudiantes",
                expanded=True,
            ):
                if materias_disponibles:
                    materia_sel = st.selectbox(
                        "Materia en la plantilla",
                        materias_disponibles,
                        index=indice_defecto,
                        key=f"materia_{i}",
                    )
                else:
                    materia_sel = st.text_input(
                        "Materia en la plantilla", value=materia_detectada or "", key=f"materia_{i}"
                    )

                asistencia_file = st.file_uploader(
                    f"Planilla de asistencia de {CORTE_LABELS[corte]} para esta materia (opcional)",
                    type=["xlsx"],
                    key=f"asist_{i}",
                )

                st.markdown("**Evolución por corte y proyección de aprobación (Def. Pond)**")
                st.caption(
                    "Ponderación real del acuerdo pedagógico: Corte 1 = 30%, Corte 2 = 30%, "
                    "Corte 3 = 40%. 'Def. Pond' es lo que el estudiante ya tiene acumulado sobre "
                    "100; 'Nota necesaria' es lo que le falta sacar en lo que queda del curso para "
                    "llegar a 60."
                )

                try:
                    filas_progreso = []
                    conteo_estado = {}
                    for e in estudiantes:
                        prog = analizar_progreso(e, corte)
                        conteo_estado[prog["estado"]] = conteo_estado.get(prog["estado"], 0) + 1
                        filas_progreso.append(
                            {
                                "Estudiante": e["nombre"],
                                "Corte 1": e["corte1"],
                                "Corte 2": e["corte2"] if corte >= 2 else None,
                                "Corte 3": e["corte3"] if corte >= 3 else None,
                                "Def. Pond": round(prog["pond"], 1),
                                "Nota necesaria": "—" if prog["necesaria"] is None else round(prog["necesaria"], 1),
                                "Estado": ETIQUETA_ESTADO[prog["estado"]],
                            }
                        )

                    if corte == 3:
                        resumen_txt = (
                            f"✅ {conteo_estado.get('aprobado', 0)} aprobaron  ·  "
                            f"❌ {conteo_estado.get('reprobado', 0)} reprobaron"
                        )
                    else:
                        resumen_txt = (
                            f"✅ {conteo_estado.get('asegurado', 0)} ya aseguraron ganar la materia  ·  "
                            f"⚠️ {conteo_estado.get('en_riesgo', 0)} en riesgo (aún pueden ganar o perder)  ·  "
                            f"❌ {conteo_estado.get('matematicamente_reprobado', 0)} ya no pueden aprobar aunque saquen 100 en lo que falta"
                        )
                    st.write(resumen_txt)

                    st.dataframe(
                        pd.DataFrame(filas_progreso).sort_values("Def. Pond", ascending=False),
                        use_container_width=True,
                        hide_index=True,
                    )
                except ValueError as exc:
                    st.warning(f"No se pudo calcular el progreso para el corte seleccionado: {exc}")

            subject_rows.append(
                {
                    "pdf_name": pdf_file.name,
                    "materia": materia_sel,
                    "grupo": grupo,
                    "estudiantes": estudiantes,
                    "asistencia_file": asistencia_file,
                }
            )

    st.subheader("4. Procesar")
    procesar = st.button(
        "🚀 Procesar todas las materias y generar un solo Excel",
        use_container_width=True,
        disabled=not (excel_file and subject_rows),
    )

    if procesar:
        materias_usadas = [r["materia"] for r in subject_rows]
        duplicadas = {m for m in materias_usadas if materias_usadas.count(m) > 1}
        if duplicadas:
            st.error(f"Hay más de un PDF apuntando a la misma materia: {', '.join(duplicadas)}. Corrige el mapeo arriba.")
            st.stop()

        resultados = []
        error_fatal = False
        db_session = get_session()
        try:
            # Se valida el periodo ANTES de tocar el disco -- si no hay
            # periodo activo, st.stop() no debe dejar huerfano ningun
            # archivo temporal.
            periodo = periodo_activo(db_session)
            if periodo is None:
                st.error(
                    "No hay ningún periodo académico activo. El Director o el Secretario Académico debe "
                    "activarlo primero (sección 'Año · Semestre · Corte')."
                )
                st.stop()

            # Nombre unico por invocacion (usuario + uuid): si dos
            # docentes generan su informe al mismo tiempo, cada uno
            # escribe su propio archivo -- nunca comparten ruta ni
            # pueden pisarse o filtrarse datos entre si.
            out_path = Path.cwd() / f"__salida_temp_informe_gestion_docente_{usuario_id}_{uuid.uuid4().hex}.xlsx"
            try:
                excel_file.seek(0)
                wb = abrir_plantilla(excel_file, str(out_path))
            except Exception as exc:
                st.error(f"No se pudo abrir la plantilla: {exc}")
                st.stop()

            for r in subject_rows:
                asistencia_regular = None
                aviso_asistencia = None
                if r["asistencia_file"] is not None:
                    r["asistencia_file"].seek(0)
                    try:
                        datos_asistencia = leer_asistencia_excel(r["asistencia_file"])
                        asistencia_regular = datos_asistencia["asistencia_regular"]
                        if datos_asistencia["matriculados_asistencia"] != len(r["estudiantes"]):
                            aviso_asistencia = (
                                f"La planilla de asistencia de '{r['materia']}' tiene "
                                f"{datos_asistencia['matriculados_asistencia']} estudiantes y el PDF "
                                f"tiene {len(r['estudiantes'])}. Verifica que sean el mismo grupo/corte."
                            )
                    except Exception as exc:
                        st.error(f"Error leyendo la planilla de asistencia de '{r['materia']}': {exc}")
                        error_fatal = True
                        break

                try:
                    resumen = calcular_resumen(r["estudiantes"], corte, asistencia_regular)
                    escribir_bloque(wb, r["materia"], resumen)

                    stats = estadisticas_materia(r["materia"], r["grupo"], r["estudiantes"], corte)
                    asignacion = obtener_o_crear_asignacion(
                        db_session, usuario_id, periodo.id, r["materia"], r["grupo"],
                        commit=False,
                    )
                    guardar_informe_corte(
                        db_session,
                        asignacion.id,
                        corte,
                        resumen,
                        stats.promedio,
                        stats.mediana,
                        stats.desviacion,
                        _filas_notas_para_bd(r["estudiantes"], corte),
                        commit=False,
                    )
                except Exception as exc:
                    st.error(f"Error procesando '{r['materia']}' ({r['pdf_name']}): {exc}")
                    error_fatal = True
                    break

                resultados.append((r["materia"], r["grupo"], resumen, aviso_asistencia))

            # Ninguna materia de este lote se confirma si alguna fallo a
            # mitad de camino -- todas o ninguna (ver commit=False arriba).
            # Recien si se recorrieron todas sin error se confirma junto.
            if error_fatal:
                db_session.rollback()
            else:
                db_session.commit()
        finally:
            db_session.close()

        if error_fatal:
            wb.close()
            out_path.unlink(missing_ok=True)
            st.stop()

        guardar(wb, str(out_path))

        st.success(f"Se actualizaron {len(resultados)} materias en un solo archivo y quedaron guardadas en la base de datos.")

        for materia, grupo, resumen, aviso_asistencia in resultados:
            st.markdown(f"**{materia}**" + (f"  ·  grupo {grupo}" if grupo else ""))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Matriculados", resumen["matriculados"])
            c2.metric("Asistencia regular", resumen["asistencia_regular"] if resumen["asistencia_regular"] is not None else "—")
            c3.metric("Evaluados", resumen["evaluados"])
            c4.metric("Aprobaron", resumen["aprobaron"])
            if resumen["es_estimado"]:
                st.caption("⚠️ Aprobaron es una ESTIMACIÓN (aún faltan cortes por calificar).")
            if resumen["asistencia_regular"] is None:
                st.caption("⚠️ Sin planilla de asistencia: esa celda quedó marcada para completar a mano.")
            if aviso_asistencia:
                st.warning(aviso_asistencia)

        st.caption(
            "Nota: Inasistencia, Reprobados y los dos % de cada materia (y la tabla resumen final) "
            "se recalculan solos con las fórmulas del Excel al abrirlo/guardarlo en Excel o LibreOffice."
        )

        with open(out_path, "rb") as f:
            st.download_button(
                "⬇️ Descargar Excel con todas las materias",
                data=f.read(),
                file_name=f"{excel_file.name.rsplit('.', 1)[0]}_corte{corte}_completo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        out_path.unlink(missing_ok=True)

    st.divider()
    st.subheader("5. Dashboard de rendimiento")

    if subject_rows:
        _render_dashboard_rendimiento(subject_rows, corte)
    else:
        st.info("Sube al menos un PDF de notas (sección 2) para ver el dashboard de rendimiento.")

    st.divider()
    entregas.render(usuario_id, "docente", materias_disponibles=materias_disponibles)

    st.divider()
    repositorio_asignaturas.render(usuario_id, "docente")
