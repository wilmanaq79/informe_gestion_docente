import { useEffect, useState } from "react";
import { api, mensajeError } from "../api/client";
import {
  GraficoComparacionDocentes,
  GraficoEvolucionPorCorte,
  GraficoPromedioPorMateria,
} from "./charts/InstitucionalCharts";
import { Dashboard } from "../types";

const ETIQUETA_ESTADO: Record<string, { texto: string; clase: string }> = {
  asegurado: { texto: "Ya aseguraron ganar la materia", clase: "proyeccion-item--ok" },
  aprobado: { texto: "Aprobaron", clase: "proyeccion-item--ok" },
  en_riesgo: { texto: "En riesgo (aún pueden ganar o perder)", clase: "proyeccion-item--riesgo" },
  matematicamente_reprobado: { texto: "Ya no pueden aprobar", clase: "proyeccion-item--mal" },
  reprobado: { texto: "Reprobaron", clase: "proyeccion-item--mal" },
};

export default function DashboardInstitucional() {
  const [datos, setDatos] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Dashboard>("/dashboard")
      .then(({ data }) => setDatos(data))
      .catch((err) => setError(mensajeError(err, "No se pudo cargar el dashboard institucional.")));
  }, []);

  if (error) {
    return (
      <section className="card">
        <p className="mensaje mensaje--error">{error}</p>
      </section>
    );
  }

  if (!datos) {
    return (
      <section className="card">
        <p className="texto-ayuda">Cargando dashboard institucional…</p>
      </section>
    );
  }

  if (datos.kpis.total_materias === 0) {
    return (
      <section className="card">
        <h2>📊 Dashboard institucional</h2>
        <p className="mensaje mensaje--info">
          Todavía no hay informes cargados por ningún docente. En cuanto empiecen a procesar sus notas, aquí
          verás cómo evolucionan los estudiantes y las asignaturas de todo el programa.
        </p>
      </section>
    );
  }

  const { kpis } = datos;

  return (
    <section className="card">
      <h2>📊 Dashboard institucional</h2>
      <p className="texto-ayuda">
        Cómo va evolucionando el rendimiento de los estudiantes y las asignaturas en todo el Programa de
        Ingeniería de Sistemas, para apoyar decisiones y estrategias de mejora.
      </p>

      <div className="totales-generales">
        <Kpi etiqueta="Docentes con informes" valor={kpis.total_docentes} />
        <Kpi etiqueta="Materias reportadas" valor={kpis.total_materias} />
        <Kpi etiqueta="Matriculados" valor={kpis.total_matriculados} />
        <Kpi etiqueta="Evaluados" valor={kpis.total_evaluados} />
        <Kpi etiqueta="Aprobaron" valor={kpis.total_aprobaron} />
        <Kpi etiqueta="Promedio general" valor={kpis.promedio_general.toFixed(1)} />
        <Kpi etiqueta="% Aprobación general" valor={`${kpis.pct_aprobacion_general.toFixed(1)}%`} />
      </div>

      {Object.keys(datos.conteo_estado_actual).length > 0 && (
        <>
          <h4>Proyección general: ¿quiénes ganan y quiénes pierden, en todo el programa?</h4>
          <div className="proyeccion">
            {Object.entries(datos.conteo_estado_actual).map(([estado, cantidad]) => (
              <div key={estado} className={`proyeccion-item ${ETIQUETA_ESTADO[estado]?.clase ?? ""}`}>
                <span className="proyeccion-item__valor">{cantidad}</span>
                <span className="proyeccion-item__etiqueta">{ETIQUETA_ESTADO[estado]?.texto ?? estado}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="grid-2">
        <div>
          <h4>Promedio por asignatura (corte más reciente de cada una)</h4>
          <GraficoPromedioPorMateria porMateria={datos.por_materia} />
        </div>
        <div>
          <h4>% de aprobación por docente</h4>
          <GraficoComparacionDocentes porDocente={datos.por_docente} />
        </div>
      </div>

      {datos.por_corte.length > 0 && (
        <>
          <h4>Evolución por corte (todas las asignaturas)</h4>
          <p className="texto-ayuda">
            Promedio y % de aprobación acumulados de todas las materias que ya tienen informe en cada corte.
          </p>
          <GraficoEvolucionPorCorte porCorte={datos.por_corte} />
        </>
      )}
    </section>
  );
}

function Kpi({ etiqueta, valor }: { etiqueta: string; valor: string | number }) {
  return (
    <div className="kpi">
      <span className="kpi__valor">{valor}</span>
      <span className="kpi__etiqueta">{etiqueta}</span>
    </div>
  );
}
