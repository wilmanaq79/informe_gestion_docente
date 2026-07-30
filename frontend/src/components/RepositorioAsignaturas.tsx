import { FormEvent, useEffect, useState } from "react";
import { api, mensajeError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { FormatoInstitucional, RepositorioAsignatura, UsuarioAdmin } from "../types";
import EstadoVacio from "./ui/EstadoVacio";

type TipoArchivo = "silabo" | "programa";

const ETIQUETA_ARCHIVO: Record<TipoArchivo, string> = {
  silabo: "Sílabo",
  programa: "Programa de asignatura",
};

const ACEPTA_ARCHIVO: Record<TipoArchivo, string> = {
  silabo: ".pdf,.doc,.docx",
  programa: ".pdf,.doc,.docx",
};

function archivoDe(entrada: RepositorioAsignatura, tipo: TipoArchivo): { nombre: string | null; tamano: number | null } {
  switch (tipo) {
    case "silabo":
      return { nombre: entrada.silabo_nombre_archivo, tamano: entrada.silabo_tamano_bytes };
    case "programa":
      return { nombre: entrada.programa_nombre_archivo, tamano: entrada.programa_tamano_bytes };
  }
}

// Los 3 formatos institucionales son un unico juego de archivos por
// PROGRAMA ACADEMICO completo (backend/api/routers/
// formatos_institucionales.py), no por materia -- por eso no comparten
// tipo/estado con TipoArchivo ni con las entradas del repositorio.
type TipoInstitucional = "gestion_docente" | "acuerdo_pedagogico" | "plan_actividades" | "lista_asistencia";

const ETIQUETA_INSTITUCIONAL: Record<TipoInstitucional, string> = {
  gestion_docente: "Formato de gestión y autoevaluación docente",
  acuerdo_pedagogico: "Acuerdo pedagógico",
  plan_actividades: "Plan de actividades",
  lista_asistencia: "Lista de asistencia",
};

const ACEPTA_INSTITUCIONAL: Record<TipoInstitucional, string> = {
  gestion_docente: ".xlsx",
  acuerdo_pedagogico: ".doc,.docx",
  plan_actividades: ".doc,.docx",
  lista_asistencia: ".xlsx",
};

function archivoInstitucionalDe(
  formatos: FormatoInstitucional | null,
  tipo: TipoInstitucional
): { nombre: string | null; tamano: number | null } {
  if (!formatos) return { nombre: null, tamano: null };
  switch (tipo) {
    case "gestion_docente":
      return { nombre: formatos.gestion_docente_nombre_archivo, tamano: formatos.gestion_docente_tamano_bytes };
    case "acuerdo_pedagogico":
      return { nombre: formatos.acuerdo_pedagogico_nombre_archivo, tamano: formatos.acuerdo_pedagogico_tamano_bytes };
    case "plan_actividades":
      return { nombre: formatos.plan_actividades_nombre_archivo, tamano: formatos.plan_actividades_tamano_bytes };
    case "lista_asistencia":
      return { nombre: formatos.lista_asistencia_nombre_archivo, tamano: formatos.lista_asistencia_tamano_bytes };
  }
}

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
  const [materiasSugeridas, setMateriasSugeridas] = useState<string[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const [formatosInstitucionales, setFormatosInstitucionales] = useState<FormatoInstitucional | null>(null);

  const [nuevaAsignatura, setNuevaAsignatura] = useState("");
  const [nuevoDocenteId, setNuevoDocenteId] = useState("");
  const [creando, setCreando] = useState(false);

  const SIN_SUGERENCIA = "— Escribir el nombre manualmente —";

  useEffect(() => {
    if (puedeEditar) {
      api
        .get<UsuarioAdmin[]>("/usuarios")
        .then(({ data }) => setDocentes(data.filter((u) => u.rol === "docente")))
        .catch(() => {});
      // Materias ya conocidas del programa (desde asignaciones_academicas)
      // para sugerir/prellenar el nombre al agregar una asignatura, en vez
      // de depender solo de que se escriba a mano cada vez.
      api
        .get<string[]>("/repositorio-asignaturas/materias-sugeridas")
        .then(({ data }) => setMateriasSugeridas(data))
        .catch(() => {});
    }
    cargarFormatosInstitucionales();
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

  async function cargarFormatosInstitucionales() {
    try {
      const { data } = await api.get<FormatoInstitucional>("/formatos-institucionales");
      setFormatosInstitucionales(data);
    } catch (err) {
      setError(mensajeError(err, "No se pudieron cargar los formatos institucionales."));
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

  async function subirArchivo(id: number, tipo: TipoArchivo, archivo: File | null) {
    if (!archivo) return;
    const form = new FormData();
    form.append("archivo", archivo);
    try {
      await api.post(`/repositorio-asignaturas/${id}/${tipo}`, form);
      setMensaje(`${ETIQUETA_ARCHIVO[tipo]} actualizado.`);
      await cargar();
    } catch (err) {
      setError(mensajeError(err, `No se pudo subir el ${ETIQUETA_ARCHIVO[tipo].toLowerCase()}.`));
    }
  }

  async function borrarArchivo(id: number, tipo: TipoArchivo) {
    if (!window.confirm(`¿Quitar el ${ETIQUETA_ARCHIVO[tipo].toLowerCase()} de esta materia?`)) return;
    try {
      await api.delete(`/repositorio-asignaturas/${id}/${tipo}`);
      await cargar();
    } catch (err) {
      setError(mensajeError(err, `No se pudo quitar el ${ETIQUETA_ARCHIVO[tipo].toLowerCase()}.`));
    }
  }

  async function verArchivo(id: number, tipo: TipoArchivo) {
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

  async function descargarArchivo(id: number, tipo: TipoArchivo, nombreArchivo: string) {
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

  function bloqueArchivo(entrada: RepositorioAsignatura, tipo: TipoArchivo) {
    const { nombre, tamano } = archivoDe(entrada, tipo);
    const etiqueta = ETIQUETA_ARCHIVO[tipo];
    const puedeEditarEste = tipo === "programa" ? puedeEditarPrograma(entrada) : puedeEditar;

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
          <span className="texto-ayuda">No hay {etiqueta.toLowerCase()} cargado.</span>
        )}
        {puedeEditarEste && (
          <div style={{ marginTop: "0.25rem" }}>
            <input
              type="file"
              accept={ACEPTA_ARCHIVO[tipo]}
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

  async function subirFormatoInstitucional(tipo: TipoInstitucional, archivo: File | null) {
    if (!archivo) return;
    const form = new FormData();
    form.append("archivo", archivo);
    try {
      await api.post(`/formatos-institucionales/${tipo}`, form);
      setMensaje(`${ETIQUETA_INSTITUCIONAL[tipo]} actualizado.`);
      await cargarFormatosInstitucionales();
    } catch (err) {
      setError(mensajeError(err, `No se pudo subir el ${ETIQUETA_INSTITUCIONAL[tipo].toLowerCase()}.`));
    }
  }

  async function borrarFormatoInstitucional(tipo: TipoInstitucional) {
    if (!window.confirm(`¿Quitar el ${ETIQUETA_INSTITUCIONAL[tipo].toLowerCase()} del programa?`)) return;
    try {
      await api.delete(`/formatos-institucionales/${tipo}`);
      await cargarFormatosInstitucionales();
    } catch (err) {
      setError(mensajeError(err, `No se pudo quitar el ${ETIQUETA_INSTITUCIONAL[tipo].toLowerCase()}.`));
    }
  }

  async function verFormatoInstitucional(tipo: TipoInstitucional) {
    try {
      const response = await api.get(`/formatos-institucionales/${tipo}/descargar`, { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const ventana = window.open(url, "_blank");
      if (!ventana) setError("El navegador bloqueó la ventana de previsualización.");
      setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(mensajeError(err, "No se pudo previsualizar el archivo."));
    }
  }

  async function descargarFormatoInstitucional(tipo: TipoInstitucional, nombreArchivo: string) {
    try {
      const response = await api.get(`/formatos-institucionales/${tipo}/descargar`, { responseType: "blob" });
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

  function bloqueFormatoInstitucional(tipo: TipoInstitucional) {
    const { nombre, tamano } = archivoInstitucionalDe(formatosInstitucionales, tipo);
    const etiqueta = ETIQUETA_INSTITUCIONAL[tipo];

    return (
      <div style={{ marginBottom: "0.75rem" }}>
        <strong>{etiqueta}:</strong>{" "}
        {nombre ? (
          <>
            {nombre} ({formatearTamano(tamano)}){" "}
            <button className="btn btn--secondary btn--chico" onClick={() => verFormatoInstitucional(tipo)}>
              👁️ Ver
            </button>{" "}
            <button
              className="btn btn--secondary btn--chico"
              onClick={() => descargarFormatoInstitucional(tipo, nombre)}
            >
              ⬇️ Descargar
            </button>{" "}
            {esAdmin && (
              <button
                className="btn btn--secondary btn--peligro btn--chico"
                onClick={() => borrarFormatoInstitucional(tipo)}
              >
                🗑️ Quitar
              </button>
            )}
          </>
        ) : (
          <span className="texto-ayuda">No hay {etiqueta.toLowerCase()} cargado.</span>
        )}
        {esAdmin && (
          <div style={{ marginTop: "0.25rem" }}>
            <input
              type="file"
              accept={ACEPTA_INSTITUCIONAL[tipo]}
              onChange={(e) => {
                subirFormatoInstitucional(tipo, e.target.files?.[0] ?? null);
                e.target.value = "";
              }}
            />
          </div>
        )}
      </div>
    );
  }

  // Comparacion normalizada (minusculas + sin espacios extremos): la
  // misma materia puede estar guardada con distinta mayuscula/minuscula
  // en el repositorio ("Electiva Profesional II") y en las asignaciones
  // academicas ("ELECTIVA PROFESIONAL II") -- sin esto, la sugerencia
  // ofrecia una materia que en realidad ya estaba en el repositorio.
  const nombresEnRepoNormalizados = new Set(entradas.map((e) => e.asignatura.trim().toLowerCase()));

  return (
    <section className="card" id="repositorio">
      <h2>📚 Repositorio de sílabos y programas de asignatura</h2>
      <p className="texto-ayuda">
        Consulta y descarga el sílabo y el programa de asignatura de cada materia.
        {esAdmin && " Tú cargas y actualizas el sílabo; cada docente actualiza el programa de la asignatura que dicta."}
        {esDocente && " Puedes ver y descargar el sílabo, y actualizar el programa de asignatura únicamente de la materia que tú dictas."}
      </p>

      {error && <p className="mensaje mensaje--error">{error}</p>}
      {mensaje && <p className="mensaje mensaje--exito">{mensaje}</p>}

      <div style={{ marginBottom: "1.25rem" }}>
        <h3>Formatos institucionales del programa</h3>
        <p className="texto-ayuda">
          Gestión y autoevaluación docente, acuerdo pedagógico y plan de actividades: un único archivo por
          formato para todo el programa académico (no por materia).
          {esAdmin ? " Tú los cargas y actualizas; cualquier docente puede verlos y descargarlos." : " Puedes verlos y descargarlos."}
        </p>
        {bloqueFormatoInstitucional("gestion_docente")}
        {bloqueFormatoInstitucional("acuerdo_pedagogico")}
        {bloqueFormatoInstitucional("plan_actividades")}
        {bloqueFormatoInstitucional("lista_asistencia")}
      </div>

      <label>
        Buscar por asignatura o docente
        <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Ej: Sistemas Operativos" />
      </label>

      {entradas.length === 0 ? (
        <EstadoVacio icono="📚" texto="No hay asignaturas registradas en el repositorio todavía." />
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
            {materiasSugeridas.filter((m) => !nombresEnRepoNormalizados.has(m.trim().toLowerCase())).length > 0 && (
              <label>
                Elegir una materia ya registrada por algún docente (opcional)
                <select
                  value=""
                  onChange={(e) => {
                    if (e.target.value) setNuevaAsignatura(e.target.value);
                  }}
                >
                  <option value="">{SIN_SUGERENCIA}</option>
                  {materiasSugeridas
                    .filter((m) => !nombresEnRepoNormalizados.has(m.trim().toLowerCase()))
                    .map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                </select>
              </label>
            )}
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
