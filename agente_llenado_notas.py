"""
Agente de llenado automatico de notas para el
'FORMATO GESTION Y AUTOEVALUACION DOCENTE' (MI-DO-FO16) -- version linea de comandos.

Para el formulario web (subir PDF + elegir corte desde el navegador) usa:
    streamlit run app.py

USO
----
python agente_llenado_notas.py --pdf ejemplos/Notas_sistemas_opertivo_corte_2.pdf \
    --excel "documentos/MI-DO-FO16 Formato Gestion...xlsx" \
    --out salida.xlsx \
    --corte 2 \
    --asistencia-excel ejemplos/Asistencia_sistemas_operativo_corte_2_PRUEBA.xlsx

--corte indica a que corte corresponde el PDF cargado (1, 2 o 3=Final) y
determina si Aprobados/Evaluados se calculan de forma exacta (corte 3, con
los 3 cortes completos) o estimada (corte 1 o 2, proyectando el acumulado
sobre 100 puntos). Ver agente_notas/core.py para el detalle de las reglas.
Despues de generar el archivo, recalcula sus formulas con
scripts/recalc_excel_com.py o abriendolo una vez en Excel.
"""
import argparse
import sys

from agente_notas.core import (
    calcular_resumen,
    escribir_en_excel,
    leer_asistencia_excel,
    leer_pdf_notas,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", required=True, help="Ruta al PDF de notas (Academusoft)")
    ap.add_argument("--excel", required=True, help="Ruta al Excel del formato de gestion docente")
    ap.add_argument("--out", required=True, help="Ruta de salida (no se sobreescribe el original)")
    ap.add_argument("--corte", type=int, required=True, choices=[1, 2, 3], help="Corte al que corresponde el PDF: 1, 2 o 3 (Final)")
    ap.add_argument("--materia", help="Nombre de la materia tal como aparece en el Excel (columna B). Si se omite, se toma del PDF.")
    ap.add_argument("--asistencia-regular", type=int, default=None, help="Numero de estudiantes con asistencia regular, si ya se conoce el dato (manual)")
    ap.add_argument("--asistencia-excel", help="Ruta a una planilla de asistencia por semanas (columnas 'Semana N' con P/A) para calcular Asistencia regular automaticamente")
    args = ap.parse_args()

    materia_pdf, grupo, estudiantes = leer_pdf_notas(args.pdf)
    materia = args.materia or materia_pdf
    if materia is None:
        sys.exit("No se pudo determinar la materia; pasa --materia explicitamente.")

    asistencia_regular = args.asistencia_regular
    if args.asistencia_excel:
        datos_asistencia = leer_asistencia_excel(args.asistencia_excel)
        asistencia_regular = datos_asistencia["asistencia_regular"]
        if datos_asistencia["matriculados_asistencia"] != len(estudiantes):
            print(
                f"AVISO: la planilla de asistencia tiene {datos_asistencia['matriculados_asistencia']} "
                f"estudiantes y el PDF de notas tiene {len(estudiantes)}. Verifica que sean el mismo grupo/corte.",
                file=sys.stderr,
            )

    resumen = calcular_resumen(estudiantes, args.corte, asistencia_regular)
    fila = escribir_en_excel(args.excel, args.out, materia, resumen)

    print(f"Materia: {materia}  (bloque en fila {fila} de 'INFORME FINAL')  -- Corte {args.corte}")
    print(f"Matriculados       : {resumen['matriculados']}")
    print(f"Asistencia regular : {resumen['asistencia_regular'] if resumen['asistencia_regular'] is not None else '(sin dato, dejar manual)'}")
    print(f"Evaluados          : {resumen['evaluados']}")
    print(f"Aprobaron          : {resumen['aprobaron']}" + (" (ESTIMADO)" if resumen["es_estimado"] else ""))
    print(f"Archivo generado   : {args.out}")
    print("Recuerda recalcular las formulas del archivo de salida (recalc_excel_com.py o abrirlo en Excel).")


if __name__ == "__main__":
    main()
