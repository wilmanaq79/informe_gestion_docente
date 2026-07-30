import { FormEvent, useEffect, useState } from "react";
import { api, mensajeError } from "../../api/client";
import { Periodo } from "../../types";

export default function PeriodoActualPage() {
  const [periodos, setPeriodos] = useState<Periodo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activandoId, setActivandoId] = useState<number | null>(null);
  const [nuevoAnio, setNuevoAnio] = useState(new Date().getFullYear());
  const [nuevoSemestre, setNuevoSemestre] = useState(1);
  const [creandoPeriodo, setCreandoPeriodo] = useState(false);

  useEffect(() => {
    cargarPeriodos();
  }, []);

  async function cargarPeriodos() {
    try {
      const { data } = await api.get<Periodo[]>("/periodos");
      setPeriodos(data);
    } catch (err) {
      setError(mensajeError(err, "No se pudo cargar el listado de años/semestres."));
    }
  }

  async function activarPeriodo(periodoId: number) {
    setActivandoId(periodoId);
    try {
      await api.post(`/periodos/${periodoId}/activar`);
      await cargarPeriodos();
    } catch (err) {
      setError(mensajeError(err, "No se pudo activar el periodo."));
    } finally {
      setActivandoId(null);
    }
  }

  async function crearPeriodo(e: FormEvent) {
    e.preventDefault();
    setCreandoPeriodo(true);
    try {
      await api.post("/periodos", { anio: nuevoAnio, semestre: nuevoSemestre });
      await cargarPeriodos();
    } catch (err) {
      setError(mensajeError(err, "No se pudo crear el periodo."));
    } finally {
      setCreandoPeriodo(false);
    }
  }

  return (
    <section className="card">
      <h2>🟢 Periodo actual del sistema</h2>
      {error && <p className="mensaje mensaje--error">{error}</p>}
      <p className="texto-ayuda">
        Es el periodo donde caen las notas que los docentes cargan hoy. Al iniciar un semestre nuevo,
        créalo (si no existe) y actívalo aquí.
      </p>
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              <th>Periodo</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {periodos.map((p) => (
              <tr key={p.id}>
                <td>{p.nombre}</td>
                <td>{p.activo ? "🟢 Activo" : "—"}</td>
                <td>
                  {!p.activo && (
                    <button
                      className="btn btn--secondary"
                      disabled={activandoId === p.id}
                      onClick={() => activarPeriodo(p.id)}
                    >
                      {activandoId === p.id ? "Activando…" : "Activar como periodo actual"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <details>
        <summary>➕ Crear un nuevo periodo (p. ej. el próximo semestre)</summary>
        <form className="formulario-grid" onSubmit={crearPeriodo}>
          <label>
            Año
            <input
              type="number"
              value={nuevoAnio}
              onChange={(e) => setNuevoAnio(Number(e.target.value))}
              required
            />
          </label>
          <label>
            Semestre
            <select value={nuevoSemestre} onChange={(e) => setNuevoSemestre(Number(e.target.value))}>
              <option value={1}>Semestre 1</option>
              <option value={2}>Semestre 2</option>
            </select>
          </label>
          <button type="submit" className="btn btn--primario" disabled={creandoPeriodo}>
            {creandoPeriodo ? "Creando…" : "Crear periodo"}
          </button>
        </form>
      </details>
    </section>
  );
}
