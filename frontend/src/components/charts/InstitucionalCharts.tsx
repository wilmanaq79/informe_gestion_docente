import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  TooltipProps,
  XAxis,
  YAxis,
} from "recharts";
import { CorteDashboard, DocenteDashboard, MateriaDashboard } from "../../types";
import { GRIDLINE, MUTED, PALETA } from "./ChartTheme";

const CORTE_NOMBRE: Record<number, string> = { 1: "Corte 1", 2: "Corte 2", 3: "Corte 3 / Final" };

const ALTO_POR_FILA = 30;
const LIMITE_DEFECTO = 8;

function truncar(texto: string, max = 20): string {
  return texto.length > max ? `${texto.slice(0, max - 1)}…` : texto;
}

function TooltipGenerico({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="grafico-tooltip">
      <strong>{label}</strong>
      {payload.map((p) => (
        <div key={p.dataKey as string} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
        </div>
      ))}
    </div>
  );
}

function TooltipMateria({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const fila = payload[0].payload as MateriaDashboard;
  return (
    <div className="grafico-tooltip">
      <strong>{fila.materia}</strong>
      <div>Docente: {fila.docente}</div>
      {fila.grupo && <div>Grupo: {fila.grupo}</div>}
      <div>{fila.corte_nombre}</div>
      <div>Promedio: {fila.promedio.toFixed(1)}</div>
      <div>
        Aprobaron: {fila.aprobaron} / {fila.evaluados}
      </div>
    </div>
  );
}

function TooltipDocente({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload as DocenteDashboard;
  return (
    <div className="grafico-tooltip">
      <strong>{d.docente}</strong>
      <div>% Aprobación: {d.pct_aprobacion.toFixed(1)}%</div>
      <div>Promedio: {d.promedio.toFixed(1)}</div>
      <div>
        Aprobaron: {d.aprobaron} / {d.evaluados}
      </div>
    </div>
  );
}

/** Barra horizontal con altura fija por fila (no depende del contenedor) y
 * un boton "Mostrar todas" cuando hay mas filas que el limite -- para que
 * el grafico se mantenga legible sin importar si hay 1 o 50 materias/docentes. */
function useListaExpandible<T>(datos: T[], limite: number) {
  const [expandido, setExpandido] = useState(false);
  const visibles = expandido ? datos : datos.slice(0, limite);
  const hayMas = datos.length > limite;
  return { visibles, hayMas, expandido, setExpandido };
}

export function GraficoPromedioPorMateria({ porMateria }: { porMateria: MateriaDashboard[] }) {
  const ordenados = [...porMateria].sort((a, b) => a.promedio - b.promedio);
  const { visibles, hayMas, expandido, setExpandido } = useListaExpandible(ordenados, LIMITE_DEFECTO);
  const alto = Math.max(160, visibles.length * ALTO_POR_FILA + 40);

  return (
    <>
      <ResponsiveContainer width="100%" height={alto}>
        <BarChart data={visibles} layout="vertical" margin={{ top: 5, right: 40, left: 8, bottom: 5 }}>
          <CartesianGrid stroke={GRIDLINE} horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fill: MUTED, fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey="materia"
            tick={{ fill: MUTED, fontSize: 11 }}
            width={130}
            tickFormatter={(v: string) => truncar(v, 18)}
          />
          <Tooltip content={<TooltipMateria />} cursor={{ fill: "rgba(137,135,129,0.08)" }} />
          <Bar dataKey="promedio" fill={PALETA[0]} radius={[0, 4, 4, 0]} barSize={18}>
            <LabelList dataKey="promedio" position="right" formatter={(v: number) => v.toFixed(1)} fill={MUTED} fontSize={11} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {hayMas && (
        <button className="btn btn--secondary btn--chico" onClick={() => setExpandido(!expandido)}>
          {expandido ? "Mostrar solo las de menor promedio" : `Mostrar todas (${ordenados.length})`}
        </button>
      )}
    </>
  );
}

export function GraficoEvolucionPorCorte({ porCorte }: { porCorte: CorteDashboard[] }) {
  const datos = porCorte.map((c) => ({
    corte: CORTE_NOMBRE[c.corte_numero] ?? `Corte ${c.corte_numero}`,
    Promedio: c.promedio,
    "% Aprobación": c.pct_aprobacion,
  }));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={datos} margin={{ top: 20, right: 10, left: 0, bottom: 10 }}>
        <CartesianGrid stroke={GRIDLINE} vertical={false} />
        <XAxis dataKey="corte" tick={{ fill: MUTED, fontSize: 12 }} />
        <YAxis domain={[0, 100]} tick={{ fill: MUTED, fontSize: 12 }} />
        <Tooltip content={<TooltipGenerico />} cursor={{ fill: "rgba(137,135,129,0.08)" }} />
        <Legend wrapperStyle={{ color: MUTED, fontSize: 12 }} />
        <Bar dataKey="Promedio" fill={PALETA[0]} radius={[4, 4, 0, 0]} maxBarSize={60}>
          <LabelList dataKey="Promedio" position="top" formatter={(v: number) => v.toFixed(1)} fill={MUTED} fontSize={11} />
        </Bar>
        <Bar dataKey="% Aprobación" fill={PALETA[2]} radius={[4, 4, 0, 0]} maxBarSize={60}>
          <LabelList dataKey="% Aprobación" position="top" formatter={(v: number) => `${v.toFixed(0)}%`} fill={MUTED} fontSize={11} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GraficoComparacionDocentes({ porDocente }: { porDocente: DocenteDashboard[] }) {
  const ordenados = [...porDocente].sort((a, b) => a.pct_aprobacion - b.pct_aprobacion);
  const { visibles, hayMas, expandido, setExpandido } = useListaExpandible(ordenados, LIMITE_DEFECTO);
  const alto = Math.max(160, visibles.length * ALTO_POR_FILA + 40);

  return (
    <>
      <ResponsiveContainer width="100%" height={alto}>
        <BarChart data={visibles} layout="vertical" margin={{ top: 5, right: 40, left: 8, bottom: 5 }}>
          <CartesianGrid stroke={GRIDLINE} horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fill: MUTED, fontSize: 12 }} unit="%" />
          <YAxis
            type="category"
            dataKey="docente"
            tick={{ fill: MUTED, fontSize: 11 }}
            width={130}
            tickFormatter={(v: string) => truncar(v, 18)}
          />
          <Tooltip content={<TooltipDocente />} cursor={{ fill: "rgba(137,135,129,0.08)" }} />
          <Bar dataKey="pct_aprobacion" fill={PALETA[1]} radius={[0, 4, 4, 0]} barSize={18}>
            <LabelList dataKey="pct_aprobacion" position="right" formatter={(v: number) => `${v.toFixed(0)}%`} fill={MUTED} fontSize={11} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {hayMas && (
        <button className="btn btn--secondary btn--chico" onClick={() => setExpandido(!expandido)}>
          {expandido ? "Mostrar solo los de menor aprobación" : `Mostrar todos (${ordenados.length})`}
        </button>
      )}
    </>
  );
}
