import { FormEvent, useEffect, useRef, useState } from "react";
import { api, mensajeError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { DocumentoEntrega, Entrega, Periodo } from "../types";
import EstadoVacio from "./ui/EstadoVacio";

const CORTE_NOMBRE: Record<number, string> = { 1: "Corte 1", 2: "Corte 2", 3: "Corte 3 / Final" };

const ESTADO_LABEL: Record<string, { texto: string; clase: string }> = {
  pendiente: { texto: "⏳ Pendiente de revisión", clase: "mensaje--warning" },
  aprobado: { texto: "✅ Aprobada", clase: "mensaje--exito" },
  rechazado: { texto: "❌ Rechazada — hay que volver a cargar", clase: "mensaje--error" },
};

function formatearTamano(bytes: number): string {
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

interface Props {
  materiasDisponibles?: string[];
}

export default function EntregasDocumentos({ materiasDisponibles = [] }: Props) {
  const { usuario } = useAuth();
  const esDocente = usuario?.rol === "docente";

  const [periodos, setPeriodos] = useState<Periodo[]>([]);
  const [anio, setAnio] = useState<number | null>(null);
  const [semestre, setSemestre] = useState<number | null>(null);
  const [corte, setCorte] = useState(1);
  const [estadoFiltro, setEstadoFiltro] = useState("");
  const [busquedaDocumento, setBusquedaDocumento] = useState("");
  const [tipos, setTipos] = useState<Record<string, string>>({});
  const [entregas, setEntregas] = useState<Entrega[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const aniosDisponibles = [...new Set(periodos.map((p) => p.anio))].sort((a, b) => b - a);
  const periodoId = periodos.find((p) => p.anio === anio && p.semestre === semestre)?.id ?? null;

  const [tipoDocumento, setTipoDocumento] = useState("lista_asistencia");
  const [materia, setMateria] = useState("");
  const [descripcionOtro, setDescripcionOtro] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const archivoInputRef = useRef<HTMLInputElement>(null);

  const [comentarios, setComentarios] = useState<Record<number, string>>({});
  const [procesandoId, setProcesandoId] = useState<number | null>(null);

  useEffect(() => {
    api
      .get<Periodo[]>("/periodos")
      .then(({ data }) => {
        setPeriodos(data);
        const activo = data.find((p) => p.activo) ?? data[0];
        if (activo) {
          setAnio(activo.anio);
          setSemestre(activo.semestre);
        }
      })
      .catch((err) => setError(mensajeError(err, "No se pudo cargar el listado de periodos.")));
    api
      .get<Record<string, string>>("/entregas/tipos-documento")
      .then(({ data }) => setTipos(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (periodoId == null) return;
    cargarEntregas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodoId, corte, estadoFiltro, busquedaDocumento]);

  async function cargarEntregas() {
    try {
      const params: Record<string, string | number> = { periodo_id: periodoId as number, corte_numero: corte };
      if (estadoFiltro) params.estado = estadoFiltro;
      if (busquedaDocumento.trim()) params.documento = busquedaDocumento.trim();
      const { data } = await api.get<Entrega[]>("/entregas", { params });
      setEntregas(data);
    } catch (err) {
      setError(mensajeError(err, "No se pudo cargar las entregas."));
    }
  }

  async function subirDocumento(e: FormEvent) {
    e.preventDefault();
    if (!archivo || periodoId == null) return;
    setSubiendo(true);
    setError(null);
    setMensaje(null);
    try {
      const form = new FormData();
      form.append("periodo_id", String(periodoId));
      form.append("corte_numero", String(corte));
      form.append("tipo_documento", tipoDocumento);
      form.append("materia", materia);
      form.append("descripcion_otro", descripcionOtro);
      form.append("archivo", archivo);
      await api.post("/entregas/documentos", form);
      setMensaje("Documento subido correctamente.");
      setArchivo(null);
      setMateria("");
      setDescripcionOtro("");
      if (archivoInputRef.current) archivoInputRef.current.value = "";
      await cargarEntregas();
    } catch (err) {
      setError(mensajeError(err, "No se pudo subir el documento."));
    } finally {
      setSubiendo(false);
    }
  }

  async function borrarDocumento(documentoId: number) {
    if (!window.confirm("¿Borrar este documento de la entrega?")) return;
    try {
      await api.delete(`/entregas/documentos/${documentoId}`);
      await cargarEntregas();
    } catch (err) {
      setError(mensajeError(err, "No se pudo borrar el documento."));
    }
  }

  async function descargarDocumento(doc: DocumentoEntrega) {
    try {
      const response = await api.get(`/entregas/documentos/${doc.id}/descargar`, { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = doc.nombre_archivo;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(mensajeError(err, "No se pudo descargar el documento."));
    }
  }

  async function verDocumento(doc: DocumentoEntrega) {
    try {
      const response = await api.get(`/entregas/documentos/${doc.id}/descargar`, { responseType: "blob" });
      const url = window.URL.createObjectURL(response.data);
      const ventana = window.open(url, "_blank");
      if (!ventana) {
        setError("El navegador bloqueó la ventana de previsualización. Permite las ventanas emergentes e intenta de nuevo.");
      }
      // El navegador necesita la URL viva mientras la pestaña la carga/renderiza.
      setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(mensajeError(err, "No se pudo previsualizar el documento."));
    }
  }

  async function aprobar(entregaId: number) {
    setProcesandoId(entregaId);
    setError(null);
    setMensaje(null);
    try {
      await api.post(`/entregas/${entregaId}/aprobar`, { comentario: comentarios[entregaId] || null });
      setMensaje(
        "Entrega aprobada. Se notificó por correo al Director, al Secretario Académico, a la Secretaria del Programa y al docente."
      );
      await cargarEntregas();
    } catch (err) {
      setError(mensajeError(err, "No se pudo aprobar la entrega."));
    } finally {
      setProcesandoId(null);
    }
  }

  async function rechazar(entregaId: number) {
    const comentario = comentarios[entregaId];
    if (!comentario || !comentario.trim()) {
      setError("Escribe el motivo del rechazo antes de rechazar.");
      return;
    }
    setProcesandoId(entregaId);
    setError(null);
    setMensaje(null);
    try {
      await api.post(`/entregas/${entregaId}/rechazar`, { comentario });
      setMensaje("Entrega rechazada. El docente verá el motivo y podrá volver a cargar los documentos.");
      await cargarEntregas();
    } catch (err) {
      setError(mensajeError(err, "No se pudo rechazar la entrega."));
    } finally {
      setProcesandoId(null);
    }
  }

  function tablaDocumentos(entrega: Entrega, permiteBorrar: boolean) {
    return (
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr>
              <th>Tipo</th>
              <th>Materia</th>
              <th>Archivo</th>
              <th>Tamaño</th>
              <th>Subido</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {entrega.documentos.map((d) => (
              <tr key={d.id}>
                <td>
                  {tipos[d.tipo_documento] ?? d.tipo_documento}
                  {d.tipo_documento === "otro" && d.descripcion_otro ? ` (${d.descripcion_otro})` : ""}
                </td>
                <td>{d.materia ?? "—"}</td>
                <td>{d.nombre_archivo}</td>
                <td>{formatearTamano(d.tamano_bytes)}</td>
                <td>{formatearFecha(d.subido_en)}</td>
                <td>
                  <button className="btn btn--secondary btn--chico" onClick={() => verDocumento(d)}>
                    👁️ Ver
                  </button>{" "}
                  <button className="btn btn--secondary btn--chico" onClick={() => descargarDocumento(d)}>
                    ⬇️ Descargar
                  </button>{" "}
                  {permiteBorrar && (
                    <button className="btn btn--secondary btn--peligro btn--chico" onClick={() => borrarDocumento(d.id)}>
                      🗑️ Borrar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <section className="card" id="entregas">
      <h2>📎 Entrega de documentos</h2>
      <p className="texto-ayuda">
        Listas de asistencia, notas firmadas, informe de gestión docente y demás soportes de la entrega del
        corte.
        {!esDocente &&
          " Revisa cada archivo y confirma que el docente cumplió con la entrega y que los documentos están firmados antes de aprobar."}
      </p>

      {error && <p className="mensaje mensaje--error">{error}</p>}
      {mensaje && <p className="mensaje mensaje--exito">{mensaje}</p>}

      <div className="formulario-grid">
        <label>
          Año
          <select value={anio ?? ""} onChange={(e) => setAnio(Number(e.target.value))}>
            {aniosDisponibles.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label>
          Semestre
          <select value={semestre ?? ""} onChange={(e) => setSemestre(Number(e.target.value))}>
            <option value={1}>Semestre 1</option>
            <option value={2}>Semestre 2</option>
          </select>
        </label>
        <label>
          Corte
          <select value={corte} onChange={(e) => setCorte(Number(e.target.value))}>
            <option value={1}>Corte 1</option>
            <option value={2}>Corte 2</option>
            <option value={3}>Corte 3 / Final</option>
          </select>
        </label>
        {!esDocente && (
          <>
            <label>
              Estado
              <select value={estadoFiltro} onChange={(e) => setEstadoFiltro(e.target.value)}>
                <option value="">Todos</option>
                <option value="pendiente">Pendientes</option>
                <option value="aprobado">Aprobadas</option>
                <option value="rechazado">Rechazadas</option>
              </select>
            </label>
            <label>
              Buscar por cédula del docente
              <input
                value={busquedaDocumento}
                onChange={(e) => setBusquedaDocumento(e.target.value)}
                placeholder="N.º de documento"
              />
            </label>
          </>
        )}
      </div>
      {periodoId == null && anio != null && (
        <p className="mensaje mensaje--info">No existe el periodo {anio}-{semestre}.</p>
      )}

      {esDocente ? (
        <>
          {entregas.length > 0 && (
            <details className="detalle-interpretacion" open style={{ marginTop: "1rem" }}>
              <summary>
                {ESTADO_LABEL[entregas[0].estado]?.texto ?? entregas[0].estado} — {CORTE_NOMBRE[corte]} (
                {entregas[0].documentos.length} documento{entregas[0].documentos.length === 1 ? "" : "s"})
              </summary>
              {entregas[0].estado === "rechazado" && entregas[0].comentario_revision && (
                <p className="mensaje mensaje--error">Motivo: {entregas[0].comentario_revision}</p>
              )}
              {entregas[0].estado === "aprobado" && entregas[0].revisado_por_nombre && (
                <p className="texto-ayuda">
                  Aprobada por {entregas[0].revisado_por_nombre} el {formatearFecha(entregas[0].revisado_en!)}
                </p>
              )}
              {entregas[0].documentos.length > 0 && tablaDocumentos(entregas[0], entregas[0].estado !== "aprobado")}
            </details>
          )}

          <details open={entregas.length === 0} style={{ marginTop: "1rem" }}>
            <summary>➕ Subir documento</summary>
            <form className="formulario-grid" onSubmit={subirDocumento}>
              <label>
                Tipo de documento
                <select value={tipoDocumento} onChange={(e) => setTipoDocumento(e.target.value)}>
                  {Object.entries(tipos).map(([clave, etiqueta]) => (
                    <option key={clave} value={clave}>
                      {etiqueta}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Materia (opcional)
                {materiasDisponibles.length > 0 ? (
                  <select value={materia} onChange={(e) => setMateria(e.target.value)}>
                    <option value="">— Ninguna en particular —</option>
                    {materiasDisponibles.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    value={materia}
                    onChange={(e) => setMateria(e.target.value)}
                    placeholder="Sube una plantilla en la sección 2 para elegir de una lista"
                  />
                )}
              </label>
              {tipoDocumento === "otro" && (
                <label>
                  Descripción del documento
                  <input
                    value={descripcionOtro}
                    onChange={(e) => setDescripcionOtro(e.target.value)}
                    required
                  />
                </label>
              )}
              <label className="campo-archivo">
                Archivo (PDF, Excel o imagen)
                <input
                  ref={archivoInputRef}
                  type="file"
                  accept=".pdf,.xlsx,.jpg,.jpeg,.png"
                  onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
                  required
                />
              </label>
              <button type="submit" className="btn btn--primario" disabled={subiendo || !archivo}>
                {subiendo ? "Subiendo…" : "Subir documento"}
              </button>
            </form>
          </details>
        </>
      ) : (
        <div style={{ marginTop: "1rem" }}>
          {entregas.length === 0 ? (
            <EstadoVacio icono="📎" texto="No hay entregas para este Periodo/Corte con el filtro elegido." />
          ) : (
            entregas.map((entrega) => (
              <details key={entrega.id} className="detalle-interpretacion">
                <summary>
                  {entrega.docente_nombre} — {ESTADO_LABEL[entrega.estado]?.texto ?? entrega.estado} (
                  {entrega.documentos.length} documento{entrega.documentos.length === 1 ? "" : "s"})
                </summary>

                {entrega.documentos.length === 0 ? (
                  <p className="texto-ayuda">Todavía no ha subido ningún documento.</p>
                ) : (
                  tablaDocumentos(entrega, true)
                )}

                {entrega.comentario_revision && (
                  <p className={`mensaje ${entrega.estado === "rechazado" ? "mensaje--error" : "mensaje--info"}`}>
                    Comentario de {entrega.revisado_por_nombre ?? "revisión"}: {entrega.comentario_revision}
                  </p>
                )}
                {entrega.notificacion_error && (
                  <p className="mensaje mensaje--warning">
                    No se pudo enviar el correo de notificación: {entrega.notificacion_error}
                  </p>
                )}

                <label>
                  Comentario (obligatorio para rechazar, opcional para aprobar)
                  <textarea
                    value={comentarios[entrega.id] ?? ""}
                    onChange={(e) => setComentarios({ ...comentarios, [entrega.id]: e.target.value })}
                    rows={2}
                  />
                </label>
                <button
                  className="btn btn--primario"
                  disabled={procesandoId === entrega.id || entrega.documentos.length === 0}
                  onClick={() => aprobar(entrega.id)}
                >
                  {procesandoId === entrega.id ? "Procesando…" : "✅ Aprobar entrega"}
                </button>{" "}
                <button
                  className="btn btn--secondary btn--peligro"
                  disabled={procesandoId === entrega.id}
                  onClick={() => rechazar(entrega.id)}
                >
                  ❌ Rechazar
                </button>
              </details>
            ))
          )}
        </div>
      )}
    </section>
  );
}
