"""Genera el informe PDF consolidado de un docente (para el Director del
Programa y el Secretario Academico), con todas sus materias y el detalle
por corte guardado en la base de datos."""
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

RAIZ = Path(__file__).resolve().parent.parent
ESCUDO_UNPA = RAIZ / "assets" / "escudo_unpa.jpg"
LOGO_PROGRAMA = RAIZ / "assets" / "logo_programa.png"

AZUL = colors.HexColor("#2a78d6")
GRIS = colors.HexColor("#52514e")
GRIS_CLARO = colors.HexColor("#e1e0d9")

ETIQUETA_ESTADO = {
    "asegurado": "Aprobó asegurado",
    "en_riesgo": "En riesgo",
    "matematicamente_reprobado": "Ya no puede aprobar",
    "aprobado": "Aprobó",
    "reprobado": "Reprobó",
}


def describir_alcance(anio: int, semestre: int | None = None, corte: int | None = None) -> str:
    """Texto legible del alcance elegido por el Director/Secretario, p.ej.
    'Año 2026 · Semestre 1 · Corte 2' o 'Año 2026 (ambos semestres)'."""
    partes = [f"Año {anio}"]
    partes.append(f"Semestre {semestre}" if semestre is not None else "ambos semestres")
    if corte is not None:
        partes.append(f"Corte {corte}")
    if semestre is None:
        return f"{partes[0]} ({partes[1]})" + (f" · {partes[2]}" if len(partes) > 2 else "")
    return " · ".join(partes)


def _encabezado(story, styles, etiqueta_alcance, programa_nombre: str, logo_ruta: Path | None = None):
    """programa_nombre: nombre del programa académico del docente/alcance
    de este informe (cada programa ve su propio nombre en el
    encabezado, en vez del literal fijo "Ingeniería de Sistemas").
    logo_ruta: logo específico del programa (Programa.logo_ruta_archivo);
    si el programa no tiene uno propio cargado, se usa el logo genérico
    compartido (LOGO_PROGRAMA)."""
    logo_a_usar = logo_ruta if logo_ruta is not None and logo_ruta.exists() else LOGO_PROGRAMA

    logos = []
    if ESCUDO_UNPA.exists():
        logos.append(Image(str(ESCUDO_UNPA), width=1.8 * cm, height=1.8 * cm))
    if logo_a_usar.exists():
        logos.append(Image(str(logo_a_usar), width=3.2 * cm, height=1.8 * cm))

    titulo = Paragraph(
        "<b>Universidad del Pacífico</b><br/>"
        f"Programa de {programa_nombre}<br/>"
        "Informe de Gestión y Autoevaluación Docente",
        ParagraphStyle("titulo", parent=styles["Normal"], fontSize=12, leading=15, textColor=AZUL),
    )

    if logos:
        fila = [logos[0] if logos else "", titulo, logos[1] if len(logos) > 1 else ""]
        tabla = Table([fila], colWidths=[2.2 * cm, 12 * cm, 3.6 * cm])
        tabla.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story.append(tabla)
    else:
        story.append(titulo)

    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            f"Alcance: <b>{etiqueta_alcance}</b>  ·  Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=GRIS),
        )
    )
    story.append(Spacer(1, 10))


def _seccion_docente(story, styles, docente, etiqueta_alcance, periodo_ids=None, corte_filtro=None):
    """Agrega al story el bloque completo de un docente (datos + una tabla
    por materia). Reutilizado por el informe individual y el consolidado.

    periodo_ids: ids de PeriodoAcademico a incluir (None = todos los
    periodos del docente). corte_filtro: si se indica (1, 2 o 3), cada
    tabla de materia muestra unicamente el informe de ese corte."""
    story.append(Paragraph(f"<b>Docente:</b> {docente.nombre_completo}", styles["Heading2"]))
    datos_docente = []
    if docente.cedula:
        datos_docente.append(f"C.C. {docente.cedula}")
    if docente.email:
        datos_docente.append(docente.email)
    if docente.telefono:
        datos_docente.append(docente.telefono)
    if datos_docente:
        story.append(Paragraph("  ·  ".join(datos_docente), ParagraphStyle("datos", parent=styles["Normal"], textColor=GRIS)))
    story.append(Spacer(1, 12))

    asignaciones = docente.asignaciones
    if periodo_ids is not None:
        asignaciones = [a for a in asignaciones if a.periodo_id in periodo_ids]

    if not asignaciones:
        story.append(Paragraph(f"Sin materias registradas para {etiqueta_alcance}.", styles["Normal"]))

    for asignacion in asignaciones:
        titulo_materia = asignacion.asignatura + (f" — Grupo {asignacion.grupo}" if asignacion.grupo else "")
        story.append(Paragraph(titulo_materia, styles["Heading3"]))

        informes = sorted(asignacion.informes, key=lambda i: i.corte.numero)
        if corte_filtro is not None:
            informes = [i for i in informes if i.corte.numero == corte_filtro]
        if not informes:
            mensaje = (
                f"Sin informe cargado para el Corte {corte_filtro}."
                if corte_filtro is not None
                else "Sin informes cargados todavía."
            )
            story.append(Paragraph(mensaje, styles["Normal"]))
            story.append(Spacer(1, 10))
            continue

        encabezado = ["Corte", "Matriculados", "Asist. regular", "Evaluados", "Aprobaron", "Promedio", "Desv. estándar"]
        filas = [encabezado]
        for informe in informes:
            filas.append(
                [
                    informe.corte.nombre,
                    str(informe.matriculados),
                    "—" if informe.asistencia_regular is None else str(informe.asistencia_regular),
                    str(informe.evaluados),
                    f"{informe.aprobaron}{' (est.)' if informe.es_estimado else ''}",
                    "—" if informe.promedio is None else f"{float(informe.promedio):.1f}",
                    "—" if informe.desviacion is None else f"±{float(informe.desviacion):.1f}",
                ]
            )

        tabla = Table(filas, colWidths=[3.3 * cm, 2.6 * cm, 2.6 * cm, 2.3 * cm, 2.3 * cm, 2.2 * cm, 2.6 * cm])
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f3")]),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(tabla)
        story.append(Spacer(1, 6))

        ultimo_informe = informes[-1]
        conteo_estado = {}
        for nota in ultimo_informe.notas:
            conteo_estado[nota.estado] = conteo_estado.get(nota.estado, 0) + 1
        if conteo_estado:
            resumen_txt = "  ·  ".join(
                f"{ETIQUETA_ESTADO.get(estado, estado)}: {cantidad}" for estado, cantidad in conteo_estado.items()
            )
            story.append(
                Paragraph(
                    f"<b>{ultimo_informe.corte.nombre}</b> — {resumen_txt}",
                    ParagraphStyle("estado", parent=styles["Normal"], fontSize=8.5, textColor=GRIS),
                )
            )

        story.append(Spacer(1, 14))


def _seccion_resumen_institucional(story, styles, resumen: dict):
    """Pagina de resumen general del programa (KPIs + proyeccion de riesgo),
    igual a lo que muestra el dashboard institucional del Director/Secretario."""
    kpis = resumen["kpis"]
    story.append(Paragraph("Resumen General del Programa", styles["Heading2"]))
    story.append(Spacer(1, 8))

    filas_kpi = [
        ["Docentes con informes", "Materias reportadas", "Matriculados", "Evaluados", "Aprobaron"],
        [
            str(kpis["total_docentes"]),
            str(kpis["total_materias"]),
            str(kpis["total_matriculados"]),
            str(kpis["total_evaluados"]),
            str(kpis["total_aprobaron"]),
        ],
    ]
    tabla_kpi = Table(filas_kpi, colWidths=[3.6 * cm] * 5)
    tabla_kpi.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTSIZE", (0, 1), (-1, 1), 13),
                ("GRID", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 1), (-1, 1), 8),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
            ]
        )
    )
    story.append(tabla_kpi)
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            f"<b>Promedio general:</b> {kpis['promedio_general']:.1f}  ·  "
            f"<b>% Aprobación general:</b> {kpis['pct_aprobacion_general']:.1f}%",
            ParagraphStyle("kpitxt", parent=styles["Normal"], fontSize=10.5, textColor=GRIS),
        )
    )
    story.append(Spacer(1, 14))

    conteo_estado = resumen.get("conteo_estado_actual") or {}
    if conteo_estado:
        story.append(
            Paragraph(
                "Proyección general: ¿quiénes ganan y quiénes pierden la materia?",
                ParagraphStyle("subtitulo2", parent=styles["Heading3"], fontSize=11.5),
            )
        )
        story.append(Spacer(1, 6))
        filas_proy = [["Estado", "Estudiantes"]]
        for estado, cantidad in conteo_estado.items():
            filas_proy.append([ETIQUETA_ESTADO.get(estado, estado), str(cantidad)])
        tabla_proy = Table(filas_proy, colWidths=[8 * cm, 4 * cm])
        tabla_proy.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("GRID", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f3")]),
                    ("ALIGN", (1, 0), (1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(tabla_proy)

    por_materia = resumen.get("por_materia") or []
    if por_materia:
        story.append(Spacer(1, 16))
        story.append(
            Paragraph(
                "Promedio por asignatura (corte más reciente de cada una)",
                ParagraphStyle("subtitulo3", parent=styles["Heading3"], fontSize=11.5),
            )
        )
        story.append(Spacer(1, 6))
        celda_texto = ParagraphStyle("celda_texto", fontName="Helvetica", fontSize=8, leading=9.5, textColor=colors.black)
        filas_mat = [["Materia", "Docente", "Corte", "Matriculados", "Aprobaron/Evaluados", "Promedio"]]
        for m in sorted(por_materia, key=lambda x: x["promedio"]):
            filas_mat.append(
                [
                    Paragraph(m["materia"], celda_texto),
                    Paragraph(m["docente"], celda_texto),
                    m["corte_nombre"],
                    str(m["matriculados"]),
                    f"{m['aprobaron']}/{m['evaluados']}",
                    f"{m['promedio']:.1f}",
                ]
            )
        tabla_mat = Table(filas_mat, colWidths=[4.2 * cm, 4.2 * cm, 2.2 * cm, 2.4 * cm, 2.8 * cm, 2.2 * cm])
        tabla_mat.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f3")]),
                    ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(tabla_mat)


def generar_reporte_docente(
    docente, ruta_salida, etiqueta_alcance="2026-1", periodo_ids=None, corte_filtro=None,
    programa_nombre: str = "Gestión Docente", logo_ruta: Path | None = None,
):
    """docente: instancia de db.models.Usuario con .asignaciones precargadas
    (cada asignacion con .informes -> .corte y .notas).

    etiqueta_alcance: texto a mostrar en el encabezado (p.ej. "2026-1" o
    el resultado de describir_alcance(anio, semestre, corte)).
    periodo_ids: ids de PeriodoAcademico a incluir (None = todos).
    corte_filtro: si se indica, cada materia solo muestra el informe de
    ese corte.
    programa_nombre/logo_ruta: nombre y logo del programa académico del
    docente (cada programa ve su propio encabezado, no uno fijo).

    ruta_salida puede ser una ruta (str/Path) o un objeto tipo archivo
    (p.ej. io.BytesIO, para devolver el PDF sin tocar disco desde la API)."""
    destino = str(ruta_salida) if isinstance(ruta_salida, (str, Path)) else ruta_salida
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        destino, pagesize=letter,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    story = []
    _encabezado(story, styles, etiqueta_alcance, programa_nombre, logo_ruta)
    _seccion_docente(story, styles, docente, etiqueta_alcance, periodo_ids, corte_filtro)
    doc.build(story)
    return ruta_salida


def generar_reporte_consolidado(
    docentes, ruta_salida, etiqueta_alcance="2026-1", periodo_ids=None, corte_filtro=None, resumen_dashboard=None,
    programa_nombre: str = "Gestión Docente", logo_ruta: Path | None = None,
):
    """Un solo PDF con el informe de TODOS los docentes recibidos (de UN
    mismo programa académico), cada uno en su propia pagina. docentes:
    lista de db.models.Usuario (con .asignaciones precargadas, igual
    que generar_reporte_docente).

    etiqueta_alcance/periodo_ids/corte_filtro: igual que en
    generar_reporte_docente, aplicados a cada docente del consolidado.
    programa_nombre/logo_ruta: igual que en generar_reporte_docente.

    resumen_dashboard: dict devuelto por
    db.repository.resumen_dashboard_institucional(); si se pasa, se agrega
    una pagina inicial con los KPIs y la proyeccion de todo el programa
    (lo mismo que muestra el dashboard institucional del Director/Secretario)."""
    destino = str(ruta_salida) if isinstance(ruta_salida, (str, Path)) else ruta_salida
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        destino, pagesize=letter,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    story = []
    _encabezado(story, styles, etiqueta_alcance, programa_nombre, logo_ruta)
    story.append(
        Paragraph(
            f"Informe consolidado — {len(docentes)} docente(s)",
            ParagraphStyle("subtitulo", parent=styles["Normal"], fontSize=11, textColor=GRIS),
        )
    )
    story.append(Spacer(1, 10))

    if resumen_dashboard and resumen_dashboard["kpis"]["total_materias"] > 0:
        _seccion_resumen_institucional(story, styles, resumen_dashboard)
        story.append(PageBreak())

    for i, docente in enumerate(docentes):
        if i > 0:
            story.append(PageBreak())
        _seccion_docente(story, styles, docente, etiqueta_alcance, periodo_ids, corte_filtro)

    doc.build(story)
    return ruta_salida
