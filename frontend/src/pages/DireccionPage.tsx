import { FormEvent, useEffect, useState } from "react";
import { api, mensajeError } from "../api/client";
import CalendarioAcademico from "../components/CalendarioAcademico";
import DashboardInstitucional from "../components/DashboardInstitucional";
import EntregasDocumentos from "../components/EntregasDocumentos";
import Header from "../components/Header";
import { useAuth } from "../context/AuthContext";
import { DocenteDetalle, DocenteResumen, Periodo, UsuarioAdmin, UsuarioCreate } from "../types";

const CORTE_NOMBRE: Record<number, string> = { 1: "Corte 1", 2: "Corte 2", 3: "Corte 3 / Final" };

export default function DireccionPage() {
  const { usuario } = useAuth();
  const esDirector = usuario?.rol === "director";

  const [docentes, setDocentes] = useState<DocenteResumen[]>([]);
  const [docenteSeleccionado, setDocenteSeleccionado] = useState<number | null>(null);
  const [detalle, setDetalle] = useState<DocenteDetalle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generandoPdf, setGenerandoPdf] = useState(false);
  const [generandoConsolidado, setGenerandoConsolidado] = useState(false);
  const [borrandoId, setBorrandoId] = useState<number | null>(null);

  const [periodos, setPeriodos] = useState<Periodo[]>([]);
  const [anio, setAnio] = useState<number | null>(null);
  const [semestre, setSemestre] = useState<number | null>(null);
  const [corte, setCorte] = useState<number | null>(null);

  useEffect(() => {
    cargarPeriodos();
  }, []);

  async function cargarPeriodos() {
    try {
      const { data } = await api.get<Periodo[]>("/periodos");
      setPeriodos(data);
      if (data.length > 0) {
        setAnio(data[0].anio);
        setSemestre(data[0].semestre);
      }
    } catch (err) {
      setError(mensajeError(err, "No se pudo cargar el listado de años/semestres."));
    }
  }

  const aniosDisponibles = [...new Set(periodos.map((p) => p.anio))].sort((a, b) => b - a);
  // Cada Año académico tiene siempre 2 semestres (así no haya informes
  // cargados todavía para uno de ellos, p.ej. el semestre que aún no arranca).
  const semestresDelAnio = [1, 2];

  const [activandoId, setActivandoId] = useState<number | null>(null);
  const [nuevoAnio, setNuevoAnio] = useState(new Date().getFullYear());
  const [nuevoSemestre, setNuevoSemestre] = useState(1);
  const [creandoPeriodo, setCreandoPeriodo] = useState(false);

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

  function parametrosAlcance() {
    const params: Record<string, number> = {};
    if (anio != null) params.anio = anio;
    if (semestre != null) params.semestre = semestre;
    if (corte != null) params.corte = corte;
    return params;
  }

  useEffect(() => {
    if (anio == null) return;
    cargarDocentes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anio, semestre]);

  async function cargarDetalle() {
    if (docenteSeleccionado == null) return;
    try {
      const { data } = await api.get<DocenteDetalle>(`/docentes/${docenteSeleccionado}`, {
        params: parametrosAlcance(),
      });
      setDetalle(data);
    } catch (err) {
      setError(mensajeError(err, "No se pudo cargar el detalle del docente."));
    }
  }

  async function borrarInforme(informeId: number, corteNombre: string, asignatura: string) {
    const confirmado = window.confirm(
      `¿Borrar el informe de ${corteNombre} de "${asignatura}"? Esta acción no se puede deshacer.`
    );
    if (!confirmado) return;
    setBorrandoId(informeId);
    try {
      await api.delete(`/informes/${informeId}`);
      await cargarDetalle();
      await cargarDocentes();
    } catch (err) {
      setError(mensajeError(err, "No se pudo borrar el informe."));
    } finally {
      setBorrandoId(null);
    }
  }

  async function cargarDocentes() {
    try {
      const { data } = await api.get<DocenteResumen[]>("/docentes", { params: parametrosAlcance() });
      setDocentes(data);
      if (data.length > 0) setDocenteSeleccionado(data[0].id);
      else setDocenteSeleccionado(null);
    } catch (err) {
      setError(mensajeError(err, "No se pudo cargar el listado de docentes."));
    }
  }

  useEffect(() => {
    cargarDetalle();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docenteSeleccionado, corte]);

  function etiquetaAlcance(): string {
    if (anio == null) return "";
    const sem = semestre != null ? `Semestre ${semestre}` : "ambos semestres";
    const cor = corte != null ? `_Corte${corte}` : "";
    return `${anio}${semestre != null ? `-${semestre}` : ` (${sem})`}${cor}`;
  }

  async function generarPdf() {
    if (docenteSeleccionado == null) return;
    setGenerandoPdf(true);
    try {
      const response = await api.get(`/reportes/docente/${docenteSeleccionado}`, {
        responseType: "blob",
        params: parametrosAlcance(),
      });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      const nombre = detalle?.nombre_completo.replace(/ /g, "_") ?? "docente";
      link.download = `Informe_${nombre}_${etiquetaAlcance()}.pdf`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(mensajeError(err, "No se pudo generar el informe PDF."));
    } finally {
      setGenerandoPdf(false);
    }
  }

  async function generarConsolidado() {
    setGenerandoConsolidado(true);
    try {
      const response = await api.get("/reportes/consolidado", {
        responseType: "blob",
        params: parametrosAlcance(),
      });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `Informe_consolidado_${etiquetaAlcance()}.pdf`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(mensajeError(err, "No se pudo generar el informe consolidado."));
    } finally {
      setGenerandoConsolidado(false);
    }
  }

  return (
    <>
      <Header />
      <main className="page">
        <p className="texto-ayuda">
          Resumen de todos los docentes del Programa de Ingeniería de Sistemas, con acceso al detalle e
          informe PDF de cada uno.
        </p>

        {error && <p className="mensaje mensaje--error">{error}</p>}

        <section className="card">
          <h2>🗓️ Año · Semestre · Corte</h2>
          <p className="texto-ayuda">
            Elige el alcance de los informes consolidados y el dashboard. Cada Año tiene 2 semestres y cada
            semestre tiene 3 cortes.
          </p>
          <div className="formulario-grid">
            <label>
              Año
              <select value={anio ?? ""} onChange={(e) => setAnio(Number(e.target.value))}>
                {aniosDisponibles.length === 0 && <option value="">Sin periodos registrados</option>}
                {aniosDisponibles.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Semestre
              <select
                value={semestre ?? "ambos"}
                onChange={(e) => setSemestre(e.target.value === "ambos" ? null : Number(e.target.value))}
              >
                <option value="ambos">Todo el año (ambos semestres)</option>
                {semestresDelAnio.map((s) => (
                  <option key={s} value={s}>
                    Semestre {s}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Corte
              <select value={corte ?? "reciente"} onChange={(e) => setCorte(e.target.value === "reciente" ? null : Number(e.target.value))}>
                <option value="reciente">Más reciente cargado</option>
                <option value="1">Corte 1</option>
                <option value="2">Corte 2</option>
                <option value="3">Corte 3 / Final</option>
              </select>
            </label>
          </div>
        </section>

        <section className="card">
          <h2>🟢 Periodo actual del sistema</h2>
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

        <CalendarioAcademico />

        <DashboardInstitucional anio={anio} semestre={semestre} corte={corte} />

        {esDirector && (
          <section className="card">
            <h2>📚 Informe de todos los docentes</h2>
            <p className="texto-ayuda">
              Genera en un solo PDF el informe de gestión de los {docentes.length} docente(s) registrados,
              cada uno en su propia página, para el alcance elegido arriba (Año/Semestre/Corte).
            </p>
            <button
              className="btn btn--primario"
              onClick={generarConsolidado}
              disabled={generandoConsolidado || docentes.length === 0}
            >
              {generandoConsolidado ? "Generando…" : "📚 Generar informe de todos los docentes"}
            </button>
          </section>
        )}

        <section className="card">
          {docentes.length === 0 ? (
            <p className="mensaje mensaje--info">
              Todavía no hay docentes registrados. Usa "Administración de usuarios" más abajo para crear sus
              cuentas.
            </p>
          ) : (
            <div className="tabla-scroll">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Docente</th>
                    <th>Materias este periodo</th>
                    <th>Informes cargados</th>
                    <th>Último corte reportado</th>
                  </tr>
                </thead>
                <tbody>
                  {docentes.map((d) => (
                    <tr
                      key={d.id}
                      className={d.id === docenteSeleccionado ? "fila-seleccionada" : ""}
                      onClick={() => setDocenteSeleccionado(d.id)}
                    >
                      <td>{d.nombre_completo}</td>
                      <td>{d.materias_periodo}</td>
                      <td>{d.informes_cargados}</td>
                      <td>{d.ultimo_corte ? CORTE_NOMBRE[d.ultimo_corte] : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {detalle && (
          <section className="card">
            <h2>Detalle e informe PDF — {detalle.nombre_completo}</h2>
            {detalle.asignaciones.length === 0 ? (
              <p className="mensaje mensaje--warning">Este docente no tiene materias cargadas en el periodo actual.</p>
            ) : (
              detalle.asignaciones.map((a) => (
                <details key={a.id} className="detalle-interpretacion">
                  <summary>
                    {a.asignatura}
                    {a.grupo ? ` — Grupo ${a.grupo}` : ""}
                  </summary>
                  {a.informes.length === 0 ? (
                    <p>Sin informes cargados todavía.</p>
                  ) : (
                    <div className="tabla-scroll">
                      <table className="tabla">
                        <thead>
                          <tr>
                            <th>Corte</th>
                            <th>Matriculados</th>
                            <th>Asist. regular</th>
                            <th>Evaluados</th>
                            <th>Aprobaron</th>
                            <th>Promedio</th>
                            <th>Desv. estándar</th>
                            {esDirector && <th></th>}
                          </tr>
                        </thead>
                        <tbody>
                          {a.informes.map((i) => (
                            <tr key={i.corte_numero}>
                              <td>{i.corte_nombre}</td>
                              <td>{i.matriculados}</td>
                              <td>{i.asistencia_regular ?? "—"}</td>
                              <td>{i.evaluados}</td>
                              <td>
                                {i.aprobaron}
                                {i.es_estimado ? " (est.)" : ""}
                              </td>
                              <td>{i.promedio?.toFixed(1) ?? "—"}</td>
                              <td>{i.desviacion != null ? `±${i.desviacion.toFixed(1)}` : "—"}</td>
                              {esDirector && (
                                <td>
                                  <button
                                    className="btn btn--secondary btn--peligro"
                                    disabled={borrandoId === i.id}
                                    onClick={() => borrarInforme(i.id, i.corte_nombre, a.asignatura)}
                                  >
                                    {borrandoId === i.id ? "Borrando…" : "🗑️ Borrar"}
                                  </button>
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </details>
              ))
            )}
            <button className="btn btn--primario" onClick={generarPdf} disabled={generandoPdf}>
              {generandoPdf ? "Generando…" : "📄 Generar informe PDF de este docente"}
            </button>
          </section>
        )}

        <AdministracionUsuarios onUsuarioCreado={cargarDocentes} />

        <EntregasDocumentos />
      </main>
    </>
  );
}

function AdministracionUsuarios({ onUsuarioCreado }: { onUsuarioCreado: () => void }) {
  const [form, setForm] = useState<UsuarioCreate>({
    nombre_completo: "",
    cedula: "",
    email: "",
    username: "",
    password: "",
    rol: "docente",
  });
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [mensaje, setMensaje] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);
  const [creando, setCreando] = useState(false);

  async function cargarUsuarios() {
    try {
      const { data } = await api.get<UsuarioAdmin[]>("/usuarios");
      setUsuarios(data);
    } catch (err) {
      setMensaje({ tipo: "error", texto: mensajeError(err, "No se pudo cargar el listado de usuarios.") });
    }
  }

  useEffect(() => {
    cargarUsuarios();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setCreando(true);
    setMensaje(null);
    try {
      await api.post("/usuarios", form);
      setMensaje({ tipo: "exito", texto: `Usuario '${form.username}' creado con rol '${form.rol}'.` });
      setForm({ nombre_completo: "", cedula: "", email: "", username: "", password: "", rol: "docente" });
      cargarUsuarios();
      onUsuarioCreado();
    } catch (err) {
      setMensaje({ tipo: "error", texto: mensajeError(err, "No se pudo crear el usuario.") });
    } finally {
      setCreando(false);
    }
  }

  return (
    <section className="card">
      <h2>👤 Administración de usuarios</h2>
      <p className="texto-ayuda">Crea aquí las cuentas de los 27 docentes, el Director y el Secretario Académico.</p>

      <details open={usuarios.length === 0}>
        <summary>➕ Crear nuevo usuario</summary>
        <form className="formulario-grid" onSubmit={handleSubmit}>
          <label>
            Nombre completo
            <input
              value={form.nombre_completo}
              onChange={(e) => setForm({ ...form, nombre_completo: e.target.value })}
              required
            />
          </label>
          <label>
            Cédula (opcional)
            <input value={form.cedula} onChange={(e) => setForm({ ...form, cedula: e.target.value })} />
          </label>
          <label>
            Correo (opcional)
            <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label>
            Usuario (para iniciar sesión)
            <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          </label>
          <label>
            Contraseña temporal
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
          </label>
          <label>
            Rol
            <select value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value })}>
              <option value="docente">docente</option>
              <option value="director">director</option>
              <option value="secretario">secretario</option>
              <option value="secretaria_programa">secretaria del programa</option>
            </select>
          </label>
          {mensaje && <p className={`mensaje mensaje--${mensaje.tipo === "exito" ? "exito" : "error"}`}>{mensaje.texto}</p>}
          <button type="submit" className="btn btn--primario" disabled={creando}>
            {creando ? "Creando…" : "Crear usuario"}
          </button>
        </form>
      </details>

      <details>
        <summary>Ver usuarios registrados</summary>
        <div className="tabla-scroll">
          <table className="tabla">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Usuario</th>
                <th>Rol</th>
                <th>Activo</th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id}>
                  <td>{u.nombre_completo}</td>
                  <td>{u.username}</td>
                  <td>{u.rol}</td>
                  <td>{u.activo ? "Sí" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
