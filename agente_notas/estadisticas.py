"""
Calculo de estadisticas de rendimiento academico para el dashboard.

Trabaja sobre la misma lista de estudiantes que produce
agente_notas.core.leer_pdf_notas, y usa la misma nota definitiva
(agente_notas.core.definitiva_estudiante) que ya usa el agente para decidir
Aprobados, asi que el dashboard es consistente con lo que se escribe en el
Excel.
"""
import statistics
from dataclasses import dataclass, field


@dataclass
class EstadisticasMateria:
    materia: str
    grupo: str | None
    corte: int
    notas: list  # [{"nombre": str, "nota": float}, ...]
    n: int = field(init=False)
    promedio: float = field(init=False)
    mediana: float = field(init=False)
    desviacion: float = field(init=False)
    rango: float = field(init=False)
    coef_variacion: float = field(init=False)  # desviacion / promedio, en %
    mejor_nombre: str = field(init=False)
    mejor_nota: float = field(init=False)
    peor_nombre: str = field(init=False)
    peor_nota: float = field(init=False)

    def __post_init__(self):
        valores = [n["nota"] for n in self.notas]
        self.n = len(valores)
        self.promedio = statistics.fmean(valores) if valores else 0.0
        self.mediana = statistics.median(valores) if valores else 0.0
        self.desviacion = statistics.pstdev(valores) if len(valores) > 1 else 0.0
        self.rango = (max(valores) - min(valores)) if valores else 0.0
        self.coef_variacion = (self.desviacion / self.promedio * 100) if self.promedio else 0.0
        mejor = max(self.notas, key=lambda n: n["nota"]) if self.notas else {"nombre": "N/D", "nota": 0.0}
        peor = min(self.notas, key=lambda n: n["nota"]) if self.notas else {"nombre": "N/D", "nota": 0.0}
        self.mejor_nombre, self.mejor_nota = mejor["nombre"], mejor["nota"]
        self.peor_nombre, self.peor_nota = peor["nombre"], peor["nota"]


def estadisticas_materia(materia, grupo, estudiantes, corte) -> EstadisticasMateria:
    from agente_notas.core import definitiva_estudiante

    notas = [
        {"nombre": e["nombre"], "nota": round(definitiva_estudiante(e, corte), 1)}
        for e in estudiantes
    ]
    return EstadisticasMateria(materia=materia, grupo=grupo, corte=corte, notas=notas)


def resumen_general(lista_estadisticas: list[EstadisticasMateria]) -> dict:
    """Agrega las notas de todas las materias en un solo pool para las
    metricas 'de todos los estudiantes' / 'en general'."""
    todas_las_notas = [n["nota"] for est in lista_estadisticas for n in est.notas]
    if not todas_las_notas:
        return {
            "promedio_general": 0.0,
            "mediana_general": 0.0,
            "desviacion_general": 0.0,
            "coef_variacion_general": 0.0,
            "n_total": 0,
            "mejor_materia": None,
            "materia_mayor_dispersion": None,
        }

    mejor_materia = max(lista_estadisticas, key=lambda e: e.promedio)
    materia_mayor_dispersion = max(lista_estadisticas, key=lambda e: e.desviacion)
    promedio_general = statistics.fmean(todas_las_notas)
    desviacion_general = statistics.pstdev(todas_las_notas) if len(todas_las_notas) > 1 else 0.0

    return {
        "promedio_general": promedio_general,
        "mediana_general": statistics.median(todas_las_notas),
        "desviacion_general": desviacion_general,
        "coef_variacion_general": (desviacion_general / promedio_general * 100) if promedio_general else 0.0,
        "n_total": len(todas_las_notas),
        "mejor_materia": mejor_materia,
        "materia_mayor_dispersion": materia_mayor_dispersion,
    }


# --- Interpretacion en lenguaje natural -------------------------------------
# Umbral de coeficiente de variacion (CV = desviacion / promedio) de uso
# comun en estadistica descriptiva para calificar la homogeneidad de un
# grupo: <15% bajo (grupo homogeneo), 15-30% moderado, >30% alto (heterogeneo).
CV_BAJO = 15.0
CV_MODERADO = 30.0


def _nivel_dispersion(cv: float) -> tuple:
    """Devuelve (etiqueta, descripcion) segun el coeficiente de variacion."""
    if cv < CV_BAJO:
        return ("baja", "el grupo es bastante homogéneo: la mayoría de los estudiantes obtuvo notas parecidas")
    if cv < CV_MODERADO:
        return ("moderada", "hay una variedad razonable de desempeños dentro del grupo")
    return ("alta", "el grupo es heterogéneo: conviven estudiantes con muy buen desempeño y otros muy rezagados")


def _nivel_promedio(promedio: float) -> str:
    if promedio >= 80:
        return "excelente"
    if promedio >= 70:
        return "bueno"
    if promedio >= 60:
        return "aceptable, aunque cercano al mínimo de aprobación"
    return "preocupante, por debajo del mínimo de aprobación (60)"


def interpretar_materia(est: EstadisticasMateria) -> str:
    """Parrafo en lenguaje natural interpretando tendencia central y
    dispersion de una materia, para que el docente entienda el
    comportamiento del grupo sin tener que leer los numeros crudos."""
    etiqueta_cv, desc_cv = _nivel_dispersion(est.coef_variacion)
    nivel_prom = _nivel_promedio(est.promedio)

    partes = [
        f"**{est.materia}** — con {est.n} estudiantes, el promedio general es de "
        f"**{est.promedio:.1f}** puntos ({nivel_prom}) y la mediana es de **{est.mediana:.1f}**."
    ]

    diferencia = est.promedio - est.mediana
    if abs(diferencia) >= 3:
        if diferencia < 0:
            partes.append(
                "El promedio queda por debajo de la mediana, señal de que unos pocos estudiantes con "
                f"notas muy bajas (el más bajo: {est.peor_nombre}, {est.peor_nota:.1f}) están arrastrando "
                "el promedio hacia abajo — la mayoría del grupo está en realidad mejor que ese promedio."
            )
        else:
            partes.append(
                "El promedio queda por encima de la mediana, señal de que unos pocos estudiantes "
                f"destacados (el más alto: {est.mejor_nombre}, {est.mejor_nota:.1f}) están elevando el "
                "promedio — la mayoría del grupo está en realidad más cerca de la mediana."
            )
    else:
        partes.append("Promedio y mediana son muy parecidos, así que el promedio sí representa bien al grupo.")

    partes.append(
        f"La desviación estándar es de **±{est.desviacion:.1f}** puntos (coeficiente de variación "
        f"{est.coef_variacion:.0f}%), lo que indica una dispersión **{etiqueta_cv}**: {desc_cv}. "
        f"El rango entre la nota más alta ({est.mejor_nota:.1f}) y la más baja ({est.peor_nota:.1f}) es de "
        f"{est.rango:.1f} puntos."
    )

    if etiqueta_cv == "alta":
        partes.append(
            "Vale la pena revisar de cerca a los estudiantes con notas muy por debajo del promedio: "
            "podrían necesitar refuerzo o una estrategia de nivelación antes del siguiente corte."
        )

    return " ".join(partes)


def interpretar_general(general: dict, lista_estadisticas: list[EstadisticasMateria]) -> str:
    """Parrafo con la lectura global (todas las materias, todos los
    estudiantes)."""
    if general["n_total"] == 0:
        return "Aún no hay datos suficientes para interpretar el rendimiento."

    etiqueta_cv, desc_cv = _nivel_dispersion(general["coef_variacion_general"])
    nivel_prom = _nivel_promedio(general["promedio_general"])
    diferencia = general["promedio_general"] - general["mediana_general"]

    n_materias = len(lista_estadisticas)
    texto_materias = "1 asignatura" if n_materias == 1 else f"{n_materias} asignaturas"
    partes = [
        f"En conjunto, sobre **{general['n_total']} calificaciones** de {texto_materias}, "
        f"el promedio general es de **{general['promedio_general']:.1f}** puntos "
        f"({nivel_prom}) y la mediana es de **{general['mediana_general']:.1f}**."
    ]

    if abs(diferencia) >= 3:
        direccion = "por debajo" if diferencia < 0 else "por encima"
        partes.append(
            f"El promedio está {direccion} de la mediana, lo que sugiere que el desempeño no está "
            "distribuido de forma simétrica entre las asignaturas y estudiantes."
        )

    partes.append(
        f"La dispersión general (desviación estándar ±{general['desviacion_general']:.1f}, coeficiente de "
        f"variación {general['coef_variacion_general']:.0f}%) es **{etiqueta_cv}**: {desc_cv}."
    )

    if n_materias > 1 and general["mejor_materia"] is not None and general["materia_mayor_dispersion"] is not None:
        partes.append(
            f"La asignatura con mejor promedio es **{general['mejor_materia'].materia}** "
            f"({general['mejor_materia'].promedio:.1f} pts), mientras que "
            f"**{general['materia_mayor_dispersion'].materia}** es la que muestra mayor dispersión "
            f"entre sus estudiantes (±{general['materia_mayor_dispersion'].desviacion:.1f})."
        )

    return " ".join(partes)
