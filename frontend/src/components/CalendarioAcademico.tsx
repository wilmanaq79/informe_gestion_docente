import { FormEvent, useEffect, useState } from "react";
import { api, mensajeError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { EventoCalendario, Periodo } from "../types";

function formatearFecha(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("es-CO", { day: "2-digit", month: "long", year: "numeric" });
}

function formatearRango(inicio: string, fin: string | null): string {
  if (!fin || fin === inicio) return formatearFecha(inicio);
  return `Del ${formatearFecha(inicio)} al ${formatearFecha(fin)}`;
}

const FORM_VACIO = { actividad: "", fecha_inicio: "", fecha_fin: "", orden: 0 };

export default function CalendarioAcademico() {
  const { usuario } = useAuth();
  const puedeEditar = usuario?.rol === "director" || usuario?.rol === "secretario";

  const [periodos, setPeriodos] = useState<Periodo[]>([]);
  const [periodoId, setPeriodoId] = useState<number | null>(null);
  const [eventos, setEventos] = useState<EventoCalendario[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState(FORM_VACIO);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api
      .get<Periodo[]>("/periodos")
      .then(({ data }) => {
        setPeriodos(data);
        const activo = data.find((p) => p.activo) ?? data[0];
        if (activo) setPeriodoId(activo.id);
      })
      .catch((err) => setError(mensajeError(err, "No se pudo cargar el listado de periodos.")));
  }, []);

  useEffect(() => {
    if (periodoId == null) return;
    cargarEventos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodoId]);

  async function cargarEventos() {
    try {
      const { data } = await api.get<EventoCalendario[]>("/calendario", { params: { periodo_id: periodoId } });
      setEventos(data);
    } catch (err) {
      setError(mensajeError(err, "No se pudo cargar el calendario académico."));
    }
  }

  function editar(evento: EventoCalendario) {
    setEditandoId(evento.id);
    setForm({
      actividad: evento.actividad,
      fecha_inicio: evento.fecha_inicio,
      fecha_fin: evento.fecha_fin ?? "",
      orden: evento.orden,
    });
  }

  function cancelarEdicion() {
    setEditandoId(null);
    setForm(FORM_VACIO);
  }

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (periodoId == null) return;
    setGuardando(true);
    setError(null);
    try {
      const payload = {
        actividad: form.actividad,
        fecha_inicio: form.fecha_inicio,
        fecha_fin: form.fecha_fin || null,
        orden: form.orden,
      };
      if (editandoId != null) {
        await api.put(`/calendario/${editandoId}`, payload);
      } else {
        await api.post("/calendario", { periodo_id: periodoId, ...payload });
      }
      cancelarEdicion();
      await cargarEventos();
    } catch (err) {
      setError(mensajeError(err, "No se pudo guardar el evento."));
    } finally {
      setGuardando(false);
    }
  }

  async function borrar(evento: EventoCalendario) {
    const confirmado = window.confirm(`¿Borrar "${evento.actividad}" del calendario?`);
    if (!confirmado) return;
    try {
      await api.delete(`/calendario/${evento.id}`);
      await cargarEventos();
    } catch (err) {
      setError(mensajeError(err, "No se pudo borrar el evento."));
    }
  }

  const periodoSeleccionado = periodos.find((p) => p.id === periodoId);

  return (
    <section className="card">
      <h2>🗓️ Calendario académico{periodoSeleccionado ? ` — ${periodoSeleccionado.nombre}` : ""}</h2>
      <p className="texto-ayuda">
        Fechas oficiales del semestre: inicio y fin de clases, parciales y límites de reporte de notas por
        corte.
        {!puedeEditar && " Solo el Director y el Secretario Académico pueden editar este calendario."}
      </p>

      {error && <p className="mensaje mensaje--error">{error}</p>}

      <label>
        Periodo
        <select value={periodoId ?? ""} onChange={(e) => setPeriodoId(Number(e.target.value))}>
          {periodos.map((p) => (
            <option key={p.id} value={p.id}>
              {p.nombre}
              {p.activo ? " (activo)" : ""}
            </option>
          ))}
        </select>
      </label>

      {eventos.length === 0 ? (
        <p className="mensaje mensaje--info">Todavía no hay eventos cargados para este periodo.</p>
      ) : (
        <div className="tabla-scroll">
          <table className="tabla">
            <thead>
              <tr>
                <th>Actividad</th>
                <th>Fechas</th>
                {puedeEditar && <th></th>}
              </tr>
            </thead>
            <tbody>
              {eventos.map((ev) => (
                <tr key={ev.id}>
                  <td>{ev.actividad}</td>
                  <td>{formatearRango(ev.fecha_inicio, ev.fecha_fin)}</td>
                  {puedeEditar && (
                    <td>
                      <button className="btn btn--secondary" onClick={() => editar(ev)}>
                        ✏️ Editar
                      </button>{" "}
                      <button className="btn btn--secondary btn--peligro" onClick={() => borrar(ev)}>
                        🗑️ Borrar
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {puedeEditar && periodoId != null && (
        <details open={editandoId != null}>
          <summary>{editandoId != null ? "✏️ Editar evento" : "➕ Agregar evento al calendario"}</summary>
          <form className="formulario-grid" onSubmit={guardar}>
            <label>
              Actividad
              <input
                value={form.actividad}
                onChange={(e) => setForm({ ...form, actividad: e.target.value })}
                required
              />
            </label>
            <label>
              Fecha inicio
              <input
                type="date"
                value={form.fecha_inicio}
                onChange={(e) => setForm({ ...form, fecha_inicio: e.target.value })}
                required
              />
            </label>
            <label>
              Fecha fin (opcional, solo si es un rango)
              <input
                type="date"
                value={form.fecha_fin}
                onChange={(e) => setForm({ ...form, fecha_fin: e.target.value })}
              />
            </label>
            <label>
              Orden en el calendario
              <input
                type="number"
                value={form.orden}
                onChange={(e) => setForm({ ...form, orden: Number(e.target.value) })}
              />
            </label>
            <div>
              <button type="submit" className="btn btn--primario" disabled={guardando}>
                {guardando ? "Guardando…" : editandoId != null ? "Guardar cambios" : "Agregar"}
              </button>{" "}
              {editandoId != null && (
                <button type="button" className="btn btn--secondary" onClick={cancelarEdicion}>
                  Cancelar
                </button>
              )}
            </div>
          </form>
        </details>
      )}
    </section>
  );
}
