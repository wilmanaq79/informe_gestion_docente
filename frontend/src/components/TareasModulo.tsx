import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { api, mensajeError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { CategoriaTarea, EstadoTarea, EvidenciaTarea, IndicadoresTareas, PrioridadTarea, Tarea, UsuarioAdmin } from "../types";
import EstadoVacio from "./ui/EstadoVacio";

const ROLES_ASIGNAN = ["director", "secretario"];

// Todos los roles administrativos, sin el Docente -- pedido explicito
// del usuario para reactivar una tarea Vencida.
const ROLES_REACTIVAN = ["director", "secretario", "secretaria_programa"];

const ESTADOS_CANCELABLES = ["BORRADOR", "SIN_COMENZAR", "EN_PROCESO", "DEVUELTA_OBSERVACIONES", "PENDIENTE_REVISION"];

// Una tarea Terminada o Cancelada queda cerrada: ya no se puede asignar/
// reasignar (el backend valida lo mismo en db.repository.asignar_tarea).
const ESTADOS_CERRADOS = ["TERMINADA", "CANCELADA"];

// El boton de evidencias solo debe estar activo mientras la tarea este
// activa -- se desactiva en Terminada, Vencida o Cancelada.
const ESTADOS_TAREA_INACTIVA = ["TERMINADA", "VENCIDA", "CANCELADA"];

// Mapeo de los 10 estados reales del modulo a las 4 columnas del tablero
// Scrum/Kanban pedido por el usuario -- "Story" (fila del mockup original)
// se representa aqui como la categoria de la tarea, mostrada en cada
// tarjeta, ya que el modulo no tiene una entidad "Historia" separada.
const COLUMNAS_KANBAN: { clave: string; titulo: string; estados: string[] }[] = [
  { clave: "por_hacer", titulo: "📝 Por hacer", estados: ["BORRADOR", "PROGRAMADA", "SIN_COMENZAR"] },
  { clave: "en_proceso", titulo: "🔄 En proceso", estados: ["EN_PROCESO", "PENDIENTE_REVISION", "DEVUELTA_OBSERVACIONES", "SUSPENDIDA"] },
  { clave: "terminada", titulo: "✅ Terminada", estados: ["TERMINADA"] },
  { clave: "vencida_cancelada", titulo: "⏰ Vencida / 🔴 Cancelada", estados: ["VENCIDA", "CANCELADA"] },
];

const FORM_VACIO = {
  titulo: "",
  descripcion: "",
  objetivo: "",
  resultado_esperado: "",
  tipo: "institucional" as "institucional" | "personal",
  categoria_id: "",
  prioridad_id: "",
  fecha_inicio: "",
  fecha_limite: "",
  requiere_evidencia: false,
};

/** Módulo de tareas académicas/administrativas (ver
 * docs/especificacionModuloTareas.md): lista y tablero Kanban con
 * filtros, creación, asignación/publicación, transiciones de estado
 * (iniciar/terminar/cancelar) e indicadores. Las funcionalidades de
 * subtareas, evidencias y evaluación llegan en fases posteriores. */
export default function TareasModulo() {
  const { usuario } = useAuth();
  const esAdmin = ROLES_ASIGNAN.includes(usuario?.rol ?? "");
  const esSecretariaPrograma = usuario?.rol === "secretaria_programa";

  const [tareas, setTareas] = useState<Tarea[]>([]);
  const [indicadores, setIndicadores] = useState<IndicadoresTareas | null>(null);
  const [categorias, setCategorias] = useState<CategoriaTarea[]>([]);
  const [prioridades, setPrioridades] = useState<PrioridadTarea[]>([]);
  const [estados, setEstados] = useState<EstadoTarea[]>([]);
  const [docentes, setDocentes] = useState<UsuarioAdmin[]>([]);
  const [filtroEstado, setFiltroEstado] = useState("");
  const [vista, setVista] = useState<"lista" | "tablero">("tablero");
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const [form, setForm] = useState(FORM_VACIO);
  const [creando, setCreando] = useState(false);

  const [asignandoId, setAsignandoId] = useState<number | null>(null);
  const [responsableElegido, setResponsableElegido] = useState<Record<number, string>>({});
  const [cancelandoId, setCancelandoId] = useState<number | null>(null);
  const [motivoCancelacion, setMotivoCancelacion] = useState<Record<number, string>>({});
  const [devolviendoId, setDevolviendoId] = useState<number | null>(null);
  const [motivoDevolucion, setMotivoDevolucion] = useState<Record<number, string>>({});
  const [reactivandoId, setReactivandoId] = useState<number | null>(null);
  const [nuevaFechaLimite, setNuevaFechaLimite] = useState<Record<number, string>>({});
  const [generandoInforme, setGenerandoInforme] = useState(false);

  const [evidenciasAbiertoId, setEvidenciasAbiertoId] = useState<number | null>(null);
  const [evidenciasPorTarea, setEvidenciasPorTarea] = useState<Record<number, EvidenciaTarea[]>>({});
  const [subiendoEvidenciaId, setSubiendoEvidenciaId] = useState<number | null>(null);

  const colorPorPrioridad = useMemo(() => {
    const mapa: Record<string, string> = {};
    prioridades.forEach((p) => {
      mapa[p.nombre] = p.color;
    });
    return mapa;
  }, [prioridades]);

  useEffect(() => {
    api.get<CategoriaTarea[]>("/tareas/catalogos/categorias").then(({ data }) => setCategorias(data)).catch(() => {});
    api.get<PrioridadTarea[]>("/tareas/catalogos/prioridades").then(({ data }) => {
      setPrioridades(data);
      if (data.length > 0) setForm((f) => ({ ...f, prioridad_id: String(data[1]?.id ?? data[0].id) }));
    }).catch(() => {});
    api.get<EstadoTarea[]>("/tareas/catalogos/estados").then(({ data }) => setEstados(data)).catch(() => {});
    if (esAdmin) {
      api.get<UsuarioAdmin[]>("/usuarios").then(({ data }) => setDocentes(data.filter((u) => u.rol === "docente"))).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroEstado]);

  async function cargar() {
    try {
      const { data } = await api.get<Tarea[]>("/tareas", { params: filtroEstado ? { estado: filtroEstado } : {} });
      setTareas(data);
    } catch (err) {
      setError(mensajeError(err, "No se pudo cargar el listado de tareas."));
    }
    try {
      const { data } = await api.get<IndicadoresTareas>("/tareas/indicadores");
      setIndicadores(data);
    } catch {
      // los KPIs son informativos -- si fallan, no bloquean el resto del modulo.
    }
  }

  function esResponsable(t: Tarea): boolean {
    if (!usuario) return false;
    if (t.responsable_principal_id === usuario.id) return true;
    return t.responsables_secundarios.some((r) => r.usuario_id === usuario.id);
  }

  function puedeIniciar(t: Tarea): boolean {
    return ["SIN_COMENZAR", "DEVUELTA_OBSERVACIONES"].includes(t.estado_nombre) && (esResponsable(t) || esAdmin);
  }

  function puedeTerminar(t: Tarea): boolean {
    if (t.estado_nombre !== "EN_PROCESO") return false;
    return esResponsable(t) || esAdmin;
  }

  function puedeAprobarODevolver(t: Tarea): boolean {
    return esAdmin && t.estado_nombre === "PENDIENTE_REVISION";
  }

  function puedeSubirEvidencia(t: Tarea): boolean {
    return t.requiere_evidencia && (esResponsable(t) || esAdmin);
  }

  function puedeReactivar(t: Tarea): boolean {
    return t.estado_nombre === "VENCIDA" && ROLES_REACTIVAN.includes(usuario?.rol ?? "");
  }

  function puedeCancelar(t: Tarea): boolean {
    if (!ESTADOS_CANCELABLES.includes(t.estado_nombre)) return false;
    if (esAdmin) return true;
    return t.tipo === "personal" && t.creado_por_id === usuario?.id;
  }

  function puedeAsignar(t: Tarea): boolean {
    return esAdmin && !ESTADOS_CERRADOS.includes(t.estado_nombre);
  }

  async function crear(e: FormEvent) {
    e.preventDefault();
    if (!form.titulo.trim() || !form.prioridad_id) return;
    setCreando(true);
    setError(null);
    setMensaje(null);
    try {
      await api.post("/tareas", {
        titulo: form.titulo.trim(),
        descripcion: form.descripcion || undefined,
        objetivo: form.objetivo || undefined,
        resultado_esperado: form.resultado_esperado || undefined,
        tipo: esSecretariaPrograma ? form.tipo : esAdmin ? form.tipo : "personal",
        categoria_id: form.categoria_id ? Number(form.categoria_id) : null,
        prioridad_id: Number(form.prioridad_id),
        fecha_inicio: form.fecha_inicio || null,
        fecha_limite: form.fecha_limite || null,
        requiere_evidencia: form.requiere_evidencia,
      });
      setMensaje(esSecretariaPrograma ? "Borrador creado. Un Director o Secretario debe publicarlo." : "Tarea creada.");
      setForm({ ...FORM_VACIO, prioridad_id: form.prioridad_id });
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo crear la tarea."));
    } finally {
      setCreando(false);
    }
  }

  async function asignar(id: number) {
    const responsableId = responsableElegido[id];
    if (!responsableId) return;
    try {
      await api.post(`/tareas/${id}/asignar`, { responsable_principal_id: Number(responsableId) });
      setMensaje("Tarea asignada.");
      setAsignandoId(null);
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo asignar la tarea."));
    }
  }

  async function publicar(id: number) {
    try {
      await api.post(`/tareas/${id}/publicar`);
      setMensaje("Tarea publicada.");
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo publicar la tarea."));
    }
  }

  async function iniciar(id: number) {
    try {
      await api.post(`/tareas/${id}/iniciar`);
      setMensaje("Tarea iniciada.");
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo iniciar la tarea."));
    }
  }

  async function terminar(id: number) {
    try {
      const { data } = await api.post<Tarea>(`/tareas/${id}/terminar`);
      setMensaje(data.estado_nombre === "PENDIENTE_REVISION" ? "Tarea enviada a revisión." : "Tarea terminada.");
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo terminar la tarea."));
    }
  }

  async function aprobar(id: number) {
    try {
      await api.post(`/tareas/${id}/aprobar`);
      setMensaje("Tarea aprobada y cerrada.");
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo aprobar la tarea."));
    }
  }

  async function devolver(id: number) {
    const motivo = (motivoDevolucion[id] ?? "").trim();
    if (!motivo) return;
    try {
      await api.post(`/tareas/${id}/devolver`, { motivo });
      setMensaje("Tarea devuelta con observaciones.");
      setDevolviendoId(null);
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo devolver la tarea."));
    }
  }

  async function reactivar(id: number) {
    const nuevaFecha = nuevaFechaLimite[id];
    if (!nuevaFecha) return;
    try {
      await api.post(`/tareas/${id}/reactivar`, { nueva_fecha_limite: nuevaFecha });
      setMensaje("Tarea reactivada.");
      setReactivandoId(null);
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo reactivar la tarea."));
    }
  }

  async function cancelar(id: number) {
    const motivo = (motivoCancelacion[id] ?? "").trim();
    if (!motivo) return;
    try {
      await api.post(`/tareas/${id}/cancelar`, { motivo });
      setMensaje("Tarea cancelada.");
      setCancelandoId(null);
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo cancelar la tarea."));
    }
  }

  async function generarInforme() {
    setGenerandoInforme(true);
    setError(null);
    try {
      const response = await api.get("/tareas/informe", {
        responseType: "blob",
        params: filtroEstado ? { estado: filtroEstado } : {},
      });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `Informe_tareas_${new Date().toISOString().slice(0, 10)}.pdf`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(mensajeError(err, "No se pudo generar el informe PDF."));
    } finally {
      setGenerandoInforme(false);
    }
  }

  async function cargarEvidencias(id: number) {
    try {
      const { data } = await api.get<EvidenciaTarea[]>(`/tareas/${id}/evidencias`);
      setEvidenciasPorTarea((prev) => ({ ...prev, [id]: data }));
    } catch (err) {
      setError(mensajeError(err, "No se pudieron cargar las evidencias."));
    }
  }

  function alternarEvidencias(id: number) {
    if (evidenciasAbiertoId === id) {
      setEvidenciasAbiertoId(null);
      return;
    }
    setEvidenciasAbiertoId(id);
    cargarEvidencias(id);
  }

  async function subirEvidencia(id: number, e: ChangeEvent<HTMLInputElement>) {
    const archivo = e.target.files?.[0];
    e.target.value = "";
    if (!archivo) return;
    setSubiendoEvidenciaId(id);
    try {
      const datos = new FormData();
      datos.append("archivo", archivo);
      await api.post(`/tareas/${id}/evidencias`, datos, { headers: { "Content-Type": "multipart/form-data" } });
      setMensaje("Evidencia subida.");
      await cargarEvidencias(id);
    } catch (err) {
      setError(mensajeError(err, "No se pudo subir la evidencia."));
    } finally {
      setSubiendoEvidenciaId(null);
    }
  }

  async function descargarEvidencia(tareaId: number, ev: EvidenciaTarea) {
    try {
      const response = await api.get(`/tareas/${tareaId}/evidencias/${ev.id}/descargar`, { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = ev.nombre_archivo;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(mensajeError(err, "No se pudo descargar la evidencia."));
    }
  }

  async function verEvidencia(tareaId: number, ev: EvidenciaTarea) {
    try {
      const response = await api.get(`/tareas/${tareaId}/evidencias/${ev.id}/descargar`, { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const ventana = window.open(url, "_blank");
      if (!ventana) {
        setError("El navegador bloqueó la ventana de previsualización. Permite las ventanas emergentes e intenta de nuevo.");
      }
      setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(mensajeError(err, "No se pudo previsualizar la evidencia."));
    }
  }

  async function borrarEvidencia(tareaId: number, evidenciaId: number) {
    try {
      await api.delete(`/tareas/${tareaId}/evidencias/${evidenciaId}`);
      setMensaje("Evidencia eliminada.");
      await cargarEvidencias(tareaId);
    } catch (err) {
      setError(mensajeError(err, "No se pudo eliminar la evidencia."));
    }
  }

  function renderAcciones(t: Tarea) {
    return (
      <div className="kanban__tarjeta-acciones">
        {esAdmin && t.estado_nombre === "BORRADOR" && (
          <button className="btn btn--secondary btn--chico" onClick={() => publicar(t.id)}>
            Publicar
          </button>
        )}
        {puedeIniciar(t) && (
          <button className="btn btn--primario btn--chico" onClick={() => iniciar(t.id)}>
            ▶️ Iniciar
          </button>
        )}
        {puedeTerminar(t) && (
          <button className="btn btn--primario btn--chico" onClick={() => terminar(t.id)}>
            {!esAdmin && t.requiere_aprobacion ? "📤 Enviar a revisión" : "✅ Terminar"}
          </button>
        )}
        {puedeAprobarODevolver(t) && (
          <button className="btn btn--primario btn--chico" onClick={() => aprobar(t.id)}>
            ✔️ Aprobar
          </button>
        )}
        {puedeAprobarODevolver(t) && devolviendoId !== t.id && (
          <button className="btn btn--secondary btn--chico" onClick={() => setDevolviendoId(t.id)}>
            ↩️ Devolver
          </button>
        )}
        {puedeReactivar(t) && reactivandoId !== t.id && (
          <button className="btn btn--primario btn--chico" onClick={() => setReactivandoId(t.id)}>
            🔄 Reactivar
          </button>
        )}
        {puedeAsignar(t) && asignandoId !== t.id && (
          <button className="btn btn--secondary btn--chico" onClick={() => setAsignandoId(t.id)}>
            Asignar
          </button>
        )}
        {puedeCancelar(t) && cancelandoId !== t.id && (
          <button className="btn btn--peligro btn--chico" onClick={() => setCancelandoId(t.id)}>
            Cancelar
          </button>
        )}
        {t.requiere_evidencia && (
          <button
            className="btn btn--secondary btn--chico"
            onClick={() => alternarEvidencias(t.id)}
            disabled={ESTADOS_TAREA_INACTIVA.includes(t.estado_nombre)}
            title={
              ESTADOS_TAREA_INACTIVA.includes(t.estado_nombre)
                ? "Esta tarea ya no está activa; las evidencias quedaron guardadas pero no se pueden gestionar aquí."
                : undefined
            }
          >
            📎 Evidencias
          </button>
        )}
        {puedeAsignar(t) && asignandoId === t.id && (
          <>
            <select
              value={responsableElegido[t.id] ?? ""}
              onChange={(e) => setResponsableElegido({ ...responsableElegido, [t.id]: e.target.value })}
            >
              <option value="">— Elegir docente —</option>
              {docentes.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.nombre_completo}
                </option>
              ))}
            </select>{" "}
            <button className="btn btn--primario btn--chico" onClick={() => asignar(t.id)}>
              Confirmar
            </button>
          </>
        )}
        {cancelandoId === t.id && (
          <>
            <input
              type="text"
              placeholder="Motivo de cancelación"
              value={motivoCancelacion[t.id] ?? ""}
              onChange={(e) => setMotivoCancelacion({ ...motivoCancelacion, [t.id]: e.target.value })}
            />{" "}
            <button className="btn btn--peligro btn--chico" onClick={() => cancelar(t.id)}>
              Confirmar cancelación
            </button>
          </>
        )}
        {devolviendoId === t.id && (
          <>
            <input
              type="text"
              placeholder="Observaciones para el responsable"
              value={motivoDevolucion[t.id] ?? ""}
              onChange={(e) => setMotivoDevolucion({ ...motivoDevolucion, [t.id]: e.target.value })}
            />{" "}
            <button className="btn btn--secondary btn--chico" onClick={() => devolver(t.id)}>
              Confirmar devolución
            </button>
          </>
        )}
        {reactivandoId === t.id && (
          <>
            <input
              type="date"
              value={nuevaFechaLimite[t.id] ?? ""}
              onChange={(e) => setNuevaFechaLimite({ ...nuevaFechaLimite, [t.id]: e.target.value })}
            />{" "}
            <button className="btn btn--primario btn--chico" onClick={() => reactivar(t.id)}>
              Confirmar reactivación
            </button>
          </>
        )}
        {evidenciasAbiertoId === t.id && (
          <div className="evidencias-panel">
            {(evidenciasPorTarea[t.id] ?? []).length === 0 && (
              <p className="texto-ayuda">Sin evidencias adjuntas todavía.</p>
            )}
            <ul className="evidencias-lista">
              {(evidenciasPorTarea[t.id] ?? []).map((ev) => (
                <li key={ev.id}>
                  📄 {ev.nombre_archivo}{" "}
                  <span className="texto-ayuda">({(ev.tamano_bytes / 1024).toFixed(0)} KB)</span>{" "}
                  <button className="evidencias-lista__nombre" onClick={() => verEvidencia(t.id, ev)}>
                    👁️ Ver
                  </button>{" "}
                  <button className="evidencias-lista__nombre" onClick={() => descargarEvidencia(t.id, ev)}>
                    ⬇️ Descargar
                  </button>{" "}
                  {(esAdmin || ev.subido_por_id === usuario?.id) && (
                    <button className="btn-quitar" onClick={() => borrarEvidencia(t.id, ev.id)}>
                      ✕
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {puedeSubirEvidencia(t) && (
              <input
                type="file"
                onChange={(e) => subirEvidencia(t.id, e)}
                disabled={subiendoEvidenciaId === t.id}
              />
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <section className="card" id="tareas">
      <h2>📋 Tareas académicas y administrativas</h2>
      <p className="texto-ayuda">
        {esAdmin
          ? "Crea, asigna, publica y da seguimiento a tareas institucionales o personales."
          : esSecretariaPrograma
          ? "Crea borradores de tareas; un Director o Secretario Académico los publica."
          : "Consulta tus tareas asignadas, inícialas, termínalas y crea tareas personales."}
      </p>

      {error && <p className="mensaje mensaje--error">{error}</p>}
      {mensaje && <p className="mensaje mensaje--exito">{mensaje}</p>}

      {indicadores && (
        <div className="kpis-grid">
          <div className="kpi-tarjeta">
            <div className="kpi-tarjeta__valor">{indicadores.total}</div>
            <div className="kpi-tarjeta__etiqueta">Total de tareas</div>
          </div>
          <div className="kpi-tarjeta kpi-tarjeta--exito">
            <div className="kpi-tarjeta__valor">{indicadores.cumplimiento_pct}%</div>
            <div className="kpi-tarjeta__etiqueta">Cumplimiento</div>
          </div>
          <div className="kpi-tarjeta kpi-tarjeta--advertencia">
            <div className="kpi-tarjeta__valor">{indicadores.proximas_a_vencer}</div>
            <div className="kpi-tarjeta__etiqueta">Próximas a vencer (≤3 días)</div>
            {indicadores.proximas_a_vencer_detalle.length > 0 && (
              <ul className="kpi-tarjeta__lista">
                {indicadores.proximas_a_vencer_detalle.map((t) => (
                  <li key={t.id}>
                    <strong>{t.codigo}</strong> — {t.titulo}
                    <br />
                    <span className="texto-ayuda">
                      {t.dias_restantes === 0 ? "vence hoy" : `vence en ${t.dias_restantes} día(s)`}
                      {t.responsable_principal_nombre && <> · {t.responsable_principal_nombre}</>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="kpi-tarjeta kpi-tarjeta--alerta">
            <div className="kpi-tarjeta__valor">{indicadores.vencidas}</div>
            <div className="kpi-tarjeta__etiqueta">Vencidas</div>
          </div>
          <div className="kpi-tarjeta">
            <div className="kpi-tarjeta__valor">{indicadores.por_estado["EN_PROCESO"] ?? 0}</div>
            <div className="kpi-tarjeta__etiqueta">En proceso</div>
          </div>
          <div className="kpi-tarjeta">
            <div className="kpi-tarjeta__valor">{indicadores.por_estado["TERMINADA"] ?? 0}</div>
            <div className="kpi-tarjeta__etiqueta">Terminadas</div>
          </div>
        </div>
      )}

      <div className="vista-toggle">
        <button
          className={vista === "tablero" ? "btn btn--primario btn--chico" : "btn btn--secondary btn--chico"}
          onClick={() => setVista("tablero")}
        >
          🗂️ Tablero
        </button>
        <button
          className={vista === "lista" ? "btn btn--primario btn--chico" : "btn btn--secondary btn--chico"}
          onClick={() => setVista("lista")}
        >
          📋 Lista
        </button>{" "}
        <button className="btn btn--secondary btn--chico" onClick={generarInforme} disabled={generandoInforme}>
          {generandoInforme ? "Generando…" : "📄 Generar informe"}
        </button>
      </div>

      <label>
        Filtrar por estado
        <select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)}>
          <option value="">— Todos —</option>
          {estados.map((e) => (
            <option key={e.id} value={e.nombre}>
              {e.icono} {e.nombre}
            </option>
          ))}
        </select>
      </label>

      {tareas.length === 0 ? (
        <EstadoVacio icono="📋" texto="No hay tareas para mostrar todavía." />
      ) : vista === "tablero" ? (
        <div className="kanban">
          {COLUMNAS_KANBAN.map((columna) => {
            const tareasColumna = tareas.filter((t) => columna.estados.includes(t.estado_nombre));
            return (
              <div key={columna.clave} className="kanban__columna">
                <p className="kanban__titulo">
                  {columna.titulo}
                  <span className="kanban__contador">{tareasColumna.length}</span>
                </p>
                {tareasColumna.length === 0 && <p className="texto-ayuda">Sin tareas.</p>}
                {tareasColumna.map((t) => (
                  <div
                    key={t.id}
                    className="kanban__tarjeta"
                    style={{ borderLeftColor: colorPorPrioridad[t.prioridad_nombre] ?? "var(--marca-azul)" }}
                  >
                    <div className="kanban__tarjeta-titulo">
                      {t.codigo} — {t.titulo}
                    </div>
                    <div className="kanban__tarjeta-meta">
                      {t.categoria_nombre ?? "Sin categoría"} · {t.estado_icono} {t.estado_nombre}
                      <br />
                      {t.responsable_principal_nombre ?? "— Sin asignar —"}
                      {t.fecha_inicio && <> · inicia {t.fecha_inicio}</>}
                      {t.fecha_limite && <> · vence {t.fecha_limite}</>}
                    </div>
                    {renderAcciones(t)}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="tabla-scroll">
          <table className="tabla">
            <thead>
              <tr>
                <th>Código</th>
                <th>Título</th>
                <th>Tipo</th>
                <th>Categoría</th>
                <th>Prioridad</th>
                <th>Estado</th>
                <th>Responsable</th>
                <th>Fecha inicio</th>
                <th>Fecha límite</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {tareas.map((t) => (
                <tr key={t.id}>
                  <td>{t.codigo}</td>
                  <td>{t.titulo}</td>
                  <td>{t.tipo === "institucional" ? "Institucional" : "Personal"}</td>
                  <td>{t.categoria_nombre ?? "—"}</td>
                  <td>{t.prioridad_nombre}</td>
                  <td>{t.estado_icono} {t.estado_nombre}</td>
                  <td>{t.responsable_principal_nombre ?? "— Sin asignar —"}</td>
                  <td>{t.fecha_inicio ?? "—"}</td>
                  <td>{t.fecha_limite ?? "—"}</td>
                  <td>{renderAcciones(t)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <details style={{ marginTop: "1rem" }}>
        <summary>➕ Crear tarea</summary>
        <form className="formulario-grid" onSubmit={crear}>
          <label>
            Título
            <input value={form.titulo} onChange={(e) => setForm({ ...form, titulo: e.target.value })} required />
          </label>
          <label>
            Descripción
            <textarea value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />
          </label>
          <label>
            Objetivo
            <input value={form.objetivo} onChange={(e) => setForm({ ...form, objetivo: e.target.value })} />
          </label>
          <label>
            Resultado esperado
            <input
              value={form.resultado_esperado}
              onChange={(e) => setForm({ ...form, resultado_esperado: e.target.value })}
            />
          </label>
          {(esAdmin || esSecretariaPrograma) && (
            <label>
              Tipo
              <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value as "institucional" | "personal" })}>
                <option value="institucional">Institucional</option>
                <option value="personal">Personal</option>
              </select>
            </label>
          )}
          <label>
            Categoría
            <select value={form.categoria_id} onChange={(e) => setForm({ ...form, categoria_id: e.target.value })}>
              <option value="">— Sin categoría —</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </label>
          <label>
            Prioridad
            <select value={form.prioridad_id} onChange={(e) => setForm({ ...form, prioridad_id: e.target.value })} required>
              {prioridades.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.icono} {p.nombre}
                </option>
              ))}
            </select>
          </label>
          <label>
            Fecha de inicio
            <input type="date" value={form.fecha_inicio} onChange={(e) => setForm({ ...form, fecha_inicio: e.target.value })} />
          </label>
          <label>
            Fecha límite
            <input type="date" value={form.fecha_limite} onChange={(e) => setForm({ ...form, fecha_limite: e.target.value })} />
          </label>
          <label className="campo-checkbox">
            <input
              type="checkbox"
              checked={form.requiere_evidencia}
              onChange={(e) => setForm({ ...form, requiere_evidencia: e.target.checked })}
            />
            Requiere evidencia
          </label>
          <button type="submit" className="btn btn--primario" disabled={creando}>
            {creando ? "Creando…" : esSecretariaPrograma && form.tipo === "institucional" ? "Crear borrador" : "Crear tarea"}
          </button>
        </form>
      </details>
    </section>
  );
}
