import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  TooltipProps,
  XAxis,
  YAxis,
} from "recharts";
import { ResumenMateria } from "../../types";
import { GRIDLINE, MUTED, PALETA } from "./ChartTheme";

function TooltipMateria({ active, payload, label }: TooltipProps<number, string>) {
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

export function GraficoPromedioVsMejor({ resultados }: { resultados: ResumenMateria[] }) {
  const datos = resultados.map((r) => ({
    materia: r.materia,
    Promedio: r.promedio,
    "Mejor nota": r.mejor_nota,
  }));
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={datos} margin={{ top: 20, right: 10, left: 0, bottom: 10 }} barCategoryGap="20%">
        <CartesianGrid stroke={GRIDLINE} vertical={false} />
        <XAxis dataKey="materia" tick={false} axisLine={{ stroke: GRIDLINE }} tickLine={false} />
        <YAxis domain={[0, 110]} tick={{ fill: MUTED, fontSize: 12 }} />
        <Tooltip content={<TooltipMateria />} cursor={{ fill: "rgba(137,135,129,0.08)" }} />
        <Legend wrapperStyle={{ color: MUTED, fontSize: 12 }} />
        <Bar dataKey="Promedio" fill={PALETA[0]} radius={[4, 4, 0, 0]} maxBarSize={48} />
        <Bar dataKey="Mejor nota" fill={PALETA[1]} radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GraficoDispersion({ resultados }: { resultados: ResumenMateria[] }) {
  const datos = resultados.map((r) => ({ materia: r.materia, "Desv. estándar": r.desviacion }));
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={datos} margin={{ top: 20, right: 10, left: 0, bottom: 10 }} barCategoryGap="20%">
        <CartesianGrid stroke={GRIDLINE} vertical={false} />
        <XAxis dataKey="materia" tick={false} axisLine={{ stroke: GRIDLINE }} tickLine={false} />
        <YAxis tick={{ fill: MUTED, fontSize: 12 }} />
        <Tooltip content={<TooltipMateria />} cursor={{ fill: "rgba(137,135,129,0.08)" }} />
        <Bar dataKey="Desv. estándar" fill={PALETA[2]} radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GraficoRanking({ resumen }: { resumen: ResumenMateria }) {
  const datos = [...resumen.notas]
    .sort((a, b) => b.nota - a.nota)
    .map((n) => ({ nombre: n.nombre, nota: n.nota }));
  const alto = Math.max(320, datos.length * 24);

  return (
    <>
      <ResponsiveContainer width="100%" height={alto}>
        <BarChart data={datos} layout="vertical" margin={{ top: 10, right: 30, left: 160, bottom: 10 }}>
          <CartesianGrid stroke={GRIDLINE} horizontal={false} />
          <XAxis type="number" domain={[0, 105]} tick={{ fill: MUTED, fontSize: 12 }} />
          <YAxis type="category" dataKey="nombre" tick={{ fill: MUTED, fontSize: 11 }} width={155} />
          <Tooltip content={<TooltipMateria />} cursor={{ fill: "rgba(137,135,129,0.08)" }} />
          <Bar dataKey="nota" radius={[0, 4, 4, 0]}>
            {datos.map((d, i) => (
              <Cell key={i} fill={d.nota >= 60 ? "#0ca30c" : "#d03b3b"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="texto-ayuda">🟢 Nota ≥ 60 (aprueba) · 🔴 Nota &lt; 60 (reprueba)</p>
    </>
  );
}
