import { FormEvent, useEffect, useState } from "react";
import { api, mensajeError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { RepositorioAsignatura, UsuarioAdmin } from "../types";

function formatearTamano(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatearFecha(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function RepositorioAsignaturas() {
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "director" || usuario?.rol === "secretario" || usuario?.rol === "secretaria_programa";
  const esDocente = usuario?.rol === "docente";
  // El Director/Secretario Académico/Secretaria del Programa cargan el sílabo;
  // cada docente actualiza el programa de asignatura únicamente de su propia materia.
  const puedeEditar = esAdmin; // reasignar docente, crear/eliminar asignaturas, cargar sílabo
  function puedeEditarPrograma(entrada: RepositorioAsignatura): boolean {
    return esAdmin || (esDocente && entrada.docente_id === usuario?.id);
  }

  const [entradas, setEntradas] = useState<RepositorioAsignatura[]>([]);
  const [docentes, setDocentes] = useState<UsuarioAdmin[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const [nuevaAsignatura, setNuevaAsignatura] = useState("");
  const [nuevoDocenteId, setNuevoDocenteId] = useState("");
  const [creando, setCreando] = useState(false);

  useEffect(() => {
    if (puedeEditar) {
      api
        .get<UsuarioAdmin[]>("/usuarios")
        .then(({ data }) => setDocentes(data.filter((u) => u.rol === "docente")))
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busqueda]);

  async function cargar() {
    try {
      const { data } = await api.get<RepositorioAsignatura[]>("/repositorio-asignaturas", {
        params: busqueda.trim() ? { busqueda: busqueda.trim() } : {},
      });
      setEntradas(data);
    } catch (err) {
      setError(mensajeError(err, "No se pudo cargar el repositorio."));
    }
  }

  async function crear(e: FormEvent) {
    e.preventDefault();
    if (!nuevaAsignatura.trim()) return;
    setCreando(true);
    setError(null);
    setMensaje(null);
    try {
      await api.post("/repositorio-asignaturas", {
        asignatura: nuevaAsignatura.trim(),
        docente_id: nuevoDocenteId ? Number(nuevoDocenteId) : null,
      });
      setMensaje(`Asignatura "${nuevaAsignatura.trim()}" agregada al repositorio.`);
      setNuevaAsignatura("");
      setNuevoDocenteId("");
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo crear la asignatura."));
    } finally {
      setCreando(false);
    }
  }

  async function reasignarDocente(id: number, docenteId: string) {
    try {
      await api.put(`/repositorio-asignaturas/${id}`, { docente_id: docenteId ? Number(docenteId) : null });
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo reasignar el docente."));
    }
  }

  async function eliminarAsignatura(entrada: RepositorioAsignatura) {
    if (!window.confirm(`¿Eliminar "${entrada.asignatura}" del repositorio? Se borran también su sílabo y programa.`)) return;
    try {
      await api.delete(`/repositorio-asignaturas/${entrada.id}`);
      await cargar();
    } catch (err) {
      setError(mensajeError(err, "No se pudo eliminar la asignatura."));
    }
  }

  async function subirArchivo(id: number, tipo: "silabo" | "programa", archivo: File | null) {
    if (!archivo) return;
    const form = new FormData();
    form.append("archivo", archivo);
    try {
      await api.post(`/repositorio-asignaturas/${id}/${tipo}`, form);
      setMensaje(`${tipo === "silabo" ? "Sílabo" : "Programa de asignatura"} actualizado.`);
      await cargar();
    } catch (err) {
      setError(mensajeError(err, `No se pudo subir el ${tipo}.`));
    }
  }

  async function borrarArchivo(id: number, tipo: "silabo" | "programa") {
    if (!window.confirm(`¿Quitar el ${tipo === "silabo" ? "sílabo" : "programa de asignatura"} de esta materia?`)) return;
    try {
      await api.delete(`/repositorio-asignaturas/${id}/${tipo}`);
      await cargar();
    } catch (err) {
      setError(mensajeError(err, `No se pudo quitar el ${tipo}.`));
    }
  }

  async function verArchivo(id: number, tipo: "silabo" | "programa") {
    try {
      const response = await api.get(`/repositorio-asignaturas/${id}/${tipo}/descargar`, { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const ventana = window.open(url, "_blank");
      if (!ventana) setError("El navegador bloqueó la ventana de previsualización.");
      setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(mensajeError(err, "No se pudo previsualizar el archivo."));
    }
  }

  async function descargarArchivo(id: number, tipo: "silabo" | "programa", nombreArchivo: string) {
    try {
      const response = await api.get(`/repositorio-asignaturas/${id}/${tipo}/descargar`, { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = nombreArchivo;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(mensajeError(err, "No se pudo descargar el archivo."));
    }
  }

  function bloqueArchivo(entrada: RepositorioAsignatura, tipo: "silabo" | "programa") {
    const nombre = tipo === "silabo" ? entrada.silabo_nombre_archivo : entrada.programa_nombre_archivo;
    const tamano = tipo === "silabo" ? entrada.silabo_tamano_bytes : entrada.programa_tamano_bytes;
    const etiqueta = tipo === "silabo" ? "Sílabo" : "Programa de asignatura";
    const puedeEditarEste = tipo === "silabo" ? puedeEditar : puedeEditarPrograma(entrada);

    return (
      <div style={{ marginBottom: "0.75rem" }}>
        <strong>{etiqueta}:</strong>{" "}
        {nombre ? (
          <>
            {nombre} ({formatearTamano(tamano)}){" "}
            <button className="btn btn--secondary btn--chico" onClick={() => verArchivo(entrada.id, tipo)}>
              👁️ Ver
            </button>{" "}
            <button
              className="btn btn--secondary btn--chico"
              onClick={() => descargarArchivo(entrada.id, tipo, nombre)}
            >
              ⬇️ Descargar
            </button>{" "}
            {puedeEditarEste && (
              <button
                className="btn btn--secondary btn--peligro btn--chico"
                onClick={() => borrarArchivo(entrada.id, tipo)}
              >
                🗑️ Quitar
              </button>
            )}
          </>
        ) : (
          <span className="texto-ayuda">No hay {tipo === "silabo" ? "sílabo" : "programa"} cargado.</span>
        )}
        {puedeEditarEste && (
          <div style={{ marginTop: "0.25rem" }}>
            <input
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={(e) => {
                subirArchivo(entrada.id, tipo, e.target.files?.[0] ?? null);
                e.target.value = "";
              }}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <section className="card">
      <h2>📚 Repositorio de sílabos y programas de asignatura</h2>
      <p className="texto-ayuda">
        Consulta y descarga el sílabo y el programa de asignatura de cada materia.
        {esAdmin &&
          " Tú cargas y actualizas el sílabo; cada docente actualiza el programa de la asignatura que dicta."}
        {esDocente && " Puedes actualizar el programa de asignatura únicamente de la materia que tú dictas."}
      </p>

      {error && <p className="mensaje mensaje--error">{error}</p>}
      {mensaje && <p className="mensaje mensaje--exito">{mensaje}</p>}

      <label>
        Buscar por asignatura o docente
        <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Ej: Sistemas Operativos" />
      </label>

      {entradas.length === 0 ? (
        <p className="mensaje mensaje--info">No hay asignaturas registradas en el repositorio todavía.</p>
      ) : (
        entradas.map((entrada) => (
          <details key={entrada.id} className="detalle-interpretacion" style={{ marginTop: "0.75rem" }}>
            <summary>
              {entrada.asignatura} — {entrada.docente_nombre ?? "sin docente asignado"}
            </summary>

            {puedeEditar ? (
              <label>
                Docente que la dicta
                <select
                  value={entrada.docente_id ?? ""}
                  onChange={(e) => reasignarDocente(entrada.id, e.target.value)}
                >
                  <option value="">— Sin asignar —</option>
                  {docentes.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.nombre_completo}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <p className="texto-ayuda">Docente: {entrada.docente_nombre ?? "sin asignar"}</p>
            )}

            {bloqueArchivo(entrada, "silabo")}
            {bloqueArchivo(entrada, "programa")}

            <p className="texto-ayuda">
              Cargado: {formatearFecha(entrada.creado_en)} por {entrada.creado_por_nombre ?? "—"}
              {" · "}Última actualización: {formatearFecha(entrada.actualizado_en)} por{" "}
              {entrada.actualizado_por_nombre ?? "—"}
            </p>

            {puedeEditar && (
              <button className="btn btn--secondary btn--peligro" onClick={() => eliminarAsignatura(entrada)}>
                🗑️ Eliminar asignatura del repositorio
              </button>
            )}
          </details>
        ))
      )}

      {puedeEditar && (
        <details style={{ marginTop: "1rem" }}>
          <summary>➕ Agregar asignatura al repositorio</summary>
          <form className="formulario-grid" onSubmit={crear}>
            <label>
              Nombre de la asignatura
              <input value={nuevaAsignatura} onChange={(e) => setNuevaAsignatura(e.target.value)} required />
            </label>
            <label>
              Docente que la dicta (opcional)
              <select value={nuevoDocenteId} onChange={(e) => setNuevoDocenteId(e.target.value)}>
                <option value="">— Sin asignar —</option>
                {docentes.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.nombre_completo}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" className="btn btn--primario" disabled={creando}>
              {creando ? "Agregando…" : "Agregar"}
            </button>
          </form>
        </details>
      )}
    </section>
  );
}
