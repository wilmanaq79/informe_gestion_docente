"""Informe PDF del módulo de tareas (ver docs/especificacionModuloTareas.md,
sección 21 "Reportes"): lista de tareas + indicadores, con el MISMO
alcance de visibilidad por rol que ya aplica db.repository.listar_tareas
(cada rol solo puede generar el informe de lo que puede ver -- no hay una
ruta separada de "reporte" que evada esa regla). Reutiliza los colores y
el escudo institucional ya usados por agente_notas/reporte_pdf.py para
que ambos informes se vean consistentes."""
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from agente_notas.reporte_pdf import AZUL, ESCUDO_UNPA, GRIS, GRIS_CLARO, LOGO_PROGRAMA
from reportlab.lib import colors

ETIQUETA_TIPO = {"institucional": "Institucional", "personal": "Personal"}


def _encabezado(story, styles, programa_nombre: str, generado_por_nombre: str, filtros_texto: str, logo_ruta: Path | None):
    logo_a_usar = logo_ruta if logo_ruta is not None and logo_ruta.exists() else LOGO_PROGRAMA

    logos = []
    if ESCUDO_UNPA.exists():
        logos.append(Image(str(ESCUDO_UNPA), width=1.8 * cm, height=1.8 * cm))
    if logo_a_usar.exists():
        logos.append(Image(str(logo_a_usar), width=3.2 * cm, height=1.8 * cm))

    titulo = Paragraph(
        "<b>Universidad del Pacífico</b><br/>"
        f"Programa de {programa_nombre}<br/>"
        "Informe de Tareas Académicas y Administrativas",
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
            f"Generado por: <b>{generado_por_nombre}</b>  ·  "
            f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}<br/>"
            f"Alcance: {filtros_texto}",
            ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=GRIS),
        )
    )
    story.append(Spacer(1, 10))


def _seccion_indicadores(story, styles, indicadores: dict):
    story.append(Paragraph("Indicadores", styles["Heading2"]))
    story.append(Spacer(1, 6))

    filas_kpi = [
        ["Total", "Cumplimiento", "Próx. a vencer", "Vencidas", "En proceso", "Terminadas"],
        [
            str(indicadores["total"]),
            f"{indicadores['cumplimiento_pct']}%",
            str(indicadores["proximas_a_vencer"]),
            str(indicadores["vencidas"]),
            str(indicadores["por_estado"].get("EN_PROCESO", 0)),
            str(indicadores["por_estado"].get("TERMINADA", 0)),
        ],
    ]
    tabla_kpi = Table(filas_kpi, colWidths=[3 * cm] * 6)
    tabla_kpi.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("FONTSIZE", (0, 1), (-1, 1), 12),
                ("GRID", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 1), (-1, 1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ]
        )
    )
    story.append(tabla_kpi)
    story.append(Spacer(1, 14))


def _seccion_tareas(story, styles, tareas):
    story.append(Paragraph(f"Tareas ({len(tareas)})", styles["Heading2"]))
    story.append(Spacer(1, 6))

    if not tareas:
        story.append(Paragraph("No hay tareas para el alcance/filtros seleccionados.", styles["Normal"]))
        return

    celda_texto = ParagraphStyle("celda_texto", fontName="Helvetica", fontSize=7.5, leading=9, textColor=colors.black)
    encabezado = ["Código", "Título", "Categoría", "Tipo", "Prioridad", "Estado", "Responsable", "Fecha límite", "Avance"]
    filas = [encabezado]
    for t in tareas:
        filas.append(
            [
                f"TAR-{t.id:06d}",
                Paragraph(t.titulo, celda_texto),
                t.categoria.nombre if t.categoria else "—",
                ETIQUETA_TIPO.get(t.tipo, t.tipo),
                t.prioridad.nombre,
                f"{t.estado.icono} {t.estado.nombre}",
                Paragraph(t.responsable_principal.nombre_completo if t.responsable_principal else "— Sin asignar —", celda_texto),
                t.fecha_limite.strftime("%d/%m/%Y") if t.fecha_limite else "—",
                f"{t.porcentaje_avance}%",
            ]
        )

    tabla = Table(
        filas,
        colWidths=[2.1 * cm, 4.2 * cm, 2.4 * cm, 1.7 * cm, 1.8 * cm, 2.6 * cm, 3.2 * cm, 2 * cm, 1.5 * cm],
        repeatRows=1,
    )
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f3")]),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (3, 0), (5, -1), "CENTER"),
                ("ALIGN", (7, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(tabla)


def generar_informe_tareas(
    tareas, indicadores: dict, ruta_salida, programa_nombre: str, generado_por_nombre: str,
    filtros_texto: str = "Todas las tareas visibles", logo_ruta: Path | None = None,
):
    """tareas: list[db.models.Tarea] (con .categoria/.prioridad/.estado/
    .responsable_principal precargados, igual que devuelve
    db.repository.listar_tareas). indicadores: dict de
    db.repository.indicadores_tareas. ruta_salida puede ser una ruta
    (str/Path) o un objeto tipo archivo (p.ej. io.BytesIO)."""
    destino = str(ruta_salida) if isinstance(ruta_salida, (str, Path)) else ruta_salida
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        destino, pagesize=letter,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm, leftMargin=1.3 * cm, rightMargin=1.3 * cm,
    )
    story = []
    _encabezado(story, styles, programa_nombre, generado_por_nombre, filtros_texto, logo_ruta)
    _seccion_indicadores(story, styles, indicadores)
    _seccion_tareas(story, styles, tareas)
    doc.build(story)
    return ruta_salida
