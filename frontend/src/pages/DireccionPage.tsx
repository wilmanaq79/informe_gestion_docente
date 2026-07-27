import { FormEvent, useEffect, useState } from "react";
import { api, mensajeError } from "../api/client";
import DashboardInstitucional from "../components/DashboardInstitucional";
import Header from "../components/Header";
import { useAuth } from "../context/AuthContext";
import { DocenteDetalle, DocenteResumen, UsuarioAdmin, UsuarioCreate } from "../types";

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

  useEffect(() => {
    cargarDocentes();
  }, []);

  async function cargarDetalle() {
    if (docenteSeleccionado == null) return;
    try {
      const { data } = await api.get<DocenteDetalle>(`/docentes/${docenteSeleccionado}`);
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
      const { data } = await api.get<DocenteResumen[]>("/docentes");
      setDocentes(data);
      if (data.length > 0) setDocenteSeleccionado(data[0].id);
    } catch (err) {
      setError(mensajeError(err, "No se pudo cargar el listado de docentes."));
    }
  }

  useEffect(() => {
    cargarDetalle();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docenteSeleccionado]);

  async function generarPdf() {
    if (docenteSeleccionado == null) return;
    setGenerandoPdf(true);
    try {
      const response = await api.get(`/reportes/docente/${docenteSeleccionado}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      const nombre = detalle?.nombre_completo.replace(/ /g, "_") ?? "docente";
      link.download = `Informe_${nombre}.pdf`;
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
      const response = await api.get("/reportes/consolidado", { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "Informe_consolidado_todos_los_docentes.pdf";
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
          Resumen de todos los docentes del Programa de Ingeniería de Sistemas para el periodo actual, con
          acceso al detalle e informe PDF de cada uno.
        </p>

        {error && <p className="mensaje mensaje--error">{error}</p>}

        <DashboardInstitucional />

        {esDirector && (
          <section className="card">
            <h2>📚 Informe de todos los docentes</h2>
            <p className="texto-ayuda">
              Genera en un solo PDF el informe de gestión de los {docentes.length} docente(s) registrados,
              cada uno en su propia página.
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
