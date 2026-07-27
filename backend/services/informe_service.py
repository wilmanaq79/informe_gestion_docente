"""Logica de negocio para el flujo de carga y procesamiento de notas,
compartida por los routers de la API. Envuelve agente_notas.* y
db.repository.* -- la misma logica que ya usa vistas/docente.py en
Streamlit, para que ambas interfaces se comporten identico."""
import base64
import tempfile
from pathlib import Path

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
from db.repository import (
    guardar_informe_corte,
    obtener_o_crear_asignacion,
    periodo_activo,
)


def listar_materias_excel(excel_stream) -> list[str]:
    return listar_materias(excel_stream)


def previsualizar_pdf(pdf_stream, corte: int) -> dict:
    materia, grupo, estudiantes = leer_pdf_notas(pdf_stream)
    progreso = []
    conteo_estado: dict[str, int] = {}
    for e in estudiantes:
        p = analizar_progreso(e, corte)
        conteo_estado[p["estado"]] = conteo_estado.get(p["estado"], 0) + 1
        progreso.append(
            {
                "nombre": e["nombre"],
                "documento": e.get("documento"),
                "corte1": e["corte1"],
                "corte2": e["corte2"] if corte >= 2 else None,
                "corte3": e["corte3"] if corte >= 3 else None,
                "def_pond": round(p["pond"], 2),
                "nota_necesaria": None if p["necesaria"] is None else round(p["necesaria"], 2),
                "estado": p["estado"],
            }
        )
    return {
        "materia_detectada": materia,
        "grupo": grupo,
        "n_estudiantes": len(estudiantes),
        "progreso": progreso,
        "conteo_estado": conteo_estado,
    }


def previsualizar_asistencia(asistencia_stream) -> dict:
    return leer_asistencia_excel(asistencia_stream)


def _filas_notas_para_bd(estudiantes, corte):
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


def procesar_materias(db_session, docente_id: int, excel_stream, corte: int, items: list[dict]) -> dict:
    """items: [{"pdf_stream": file-like, "materia": str, "asistencia_regular": int|None}, ...]

    Escribe TODAS las materias en un solo Excel, persiste cada una en la
    base de datos (upsert por asignacion+corte), y devuelve el Excel
    resultante en base64 junto con el resumen/estadisticas de cada materia.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "salida.xlsx"
        wb = abrir_plantilla(excel_stream, str(out_path))

        periodo = periodo_activo(db_session)
        if periodo is None:
            raise ValueError(
                "No hay ningún periodo académico activo. El Director o el Secretario Académico debe "
                "activar uno primero (sección 'Año · Semestre · Corte')."
            )
        resultados_crudos = []
        stats_list = []

        try:
            for item in items:
                materia_detectada, grupo, estudiantes = leer_pdf_notas(item["pdf_stream"])
                materia = item.get("materia") or materia_detectada
                if not materia:
                    raise ValueError("No se pudo determinar la materia de uno de los PDF cargados.")

                resumen = calcular_resumen(estudiantes, corte, item.get("asistencia_regular"))
                escribir_bloque(wb, materia, resumen)

                stats = estadisticas_materia(materia, grupo, estudiantes, corte)
                stats_list.append(stats)

                filas_notas = _filas_notas_para_bd(estudiantes, corte)
                conteo_estado: dict[str, int] = {}
                for fila in filas_notas:
                    conteo_estado[fila["estado"]] = conteo_estado.get(fila["estado"], 0) + 1

                asignacion = obtener_o_crear_asignacion(
                    db_session, docente_id, periodo.id, materia, "Ingeniería de Sistemas", grupo
                )
                guardar_informe_corte(
                    db_session,
                    asignacion.id,
                    corte,
                    resumen,
                    stats.promedio,
                    stats.mediana,
                    stats.desviacion,
                    filas_notas,
                )

                resultados_crudos.append(
                    {"materia": materia, "grupo": grupo, "resumen": resumen, "stats": stats, "conteo_estado": conteo_estado}
                )
        except Exception:
            wb.close()
            raise

        guardar(wb, str(out_path))
        excel_bytes = out_path.read_bytes()

    general = resumen_general(stats_list)
    resultados = []
    for r in resultados_crudos:
        stats, resumen = r["stats"], r["resumen"]
        resultados.append(
            {
                "materia": r["materia"],
                "grupo": r["grupo"],
                "matriculados": resumen["matriculados"],
                "asistencia_regular": resumen["asistencia_regular"],
                "evaluados": resumen["evaluados"],
                "aprobaron": resumen["aprobaron"],
                "es_estimado": resumen["es_estimado"],
                "promedio": round(stats.promedio, 2),
                "mediana": round(stats.mediana, 2),
                "desviacion": round(stats.desviacion, 2),
                "mejor_nombre": stats.mejor_nombre,
                "mejor_nota": stats.mejor_nota,
                "coef_variacion": round(stats.coef_variacion, 1),
                "interpretacion": interpretar_materia(stats),
                "notas": stats.notas,
                "conteo_estado": r["conteo_estado"],
            }
        )

    return {
        "resultados": resultados,
        "interpretacion_general": interpretar_general(general, stats_list),
        "excel_base64": base64.b64encode(excel_bytes).decode("ascii"),
        "excel_filename": f"informe_gestion_docente_corte{corte}.xlsx",
    }
