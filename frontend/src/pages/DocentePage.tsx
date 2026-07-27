import { ChangeEvent, useEffect, useState } from "react";
import { api, mensajeError } from "../api/client";
import Header from "../components/Header";
import { GraficoDispersion, GraficoPromedioVsMejor, GraficoRanking } from "../components/charts/DashboardCharts";
import { EstudianteNota, PdfPreview, ProcesarResponse, ResumenMateria } from "../types";

const CORTE_LABELS: Record<number, string> = { 1: "Corte 1", 2: "Corte 2", 3: "Corte 3 / Final" };

const ETIQUETA_ESTADO: Record<string, string> = {
  asegurado: "✅ Aprobó asegurado",
  en_riesgo: "⚠️ En riesgo",
  matematicamente_reprobado: "❌ Ya no puede aprobar",
  aprobado: "✅ Aprobó",
  reprobado: "❌ Reprobó",
};

// El nombre que trae el PDF (Academusoft) puede no coincidir letra por letra
// con el de la plantilla Excel (p. ej. "PROFESIONAL" vs "PROFECIONAL", un
// error de tipeo del formato institucional). Se busca la materia de la
// plantilla cuyo nombre contenga al detectado (coincidencia aproximada),
// igual que hacía la versión Streamlit, en vez de usar el nombre crudo del
// PDF tal cual -- si no coincide con ninguna opcion del <select>, el Excel
// no la encuentra al procesar.
function mejorCoincidencia(detectada: string | null, disponibles: string[]): string {
  if (disponibles.length === 0) return detectada ?? "";
  if (!detectada) return disponibles[0];
  const detectadaNorm = detectada.trim().toLowerCase();
  const match = disponibles.find((m) => detectadaNorm.includes(m.trim().toLowerCase()));
  return match ?? disponibles[0];
}

interface PdfItem {
  id: string;
  file: File;
  materiaSeleccionada: string;
  preview: PdfPreview | null;
  cargando: boolean;
  error: string | null;
  asistenciaFile: File | null;
  asistenciaRegular: number | null;
  asistenciaAviso: string | null;
}

export default function DocentePage() {
  const [corte, setCorte] = useState(2);
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [materiasDisponibles, setMateriasDisponibles] = useState<string[]>([]);
  const [pdfItems, setPdfItems] = useState<PdfItem[]>([]);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);
  const [resultado, setResultado] = useState<ProcesarResponse | null>(null);
  const [materiaFoco, setMateriaFoco] = useState<string>("");

  // Re-previsualiza todos los PDF ya cargados cuando cambia el corte.
  useEffect(() => {
    pdfItems.forEach((item) => previsualizarPdf(item.id, item.file));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [corte]);

  async function handleExcelChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setExcelFile(file);
    setErrorGeneral(null);
    if (!file) return;
    try {
      const formData = new FormData();
      formData.append("excel", file);
      const { data } = await api.post<string[]>("/informes/materias-excel", formData);
      setMateriasDisponibles(data);
    } catch (error) {
      setErrorGeneral(mensajeError(error, "No se pudo leer la plantilla Excel."));
    }
  }

  async function previsualizarPdf(id: string, file: File) {
    setPdfItems((prev) => prev.map((it) => (it.id === id ? { ...it, cargando: true, error: null } : it)));
    try {
      const formData = new FormData();
      formData.append("pdf", file);
      formData.append("corte", String(corte));
      const { data } = await api.post<PdfPreview>("/informes/pdf-preview", formData);
      setPdfItems((prev) =>
        prev.map((it) =>
          it.id === id
            ? {
                ...it,
                preview: data,
                cargando: false,
                materiaSeleccionada:
                  it.materiaSeleccionada || mejorCoincidencia(data.materia_detectada, materiasDisponibles),
              }
            : it
        )
      );
    } catch (error) {
      setPdfItems((prev) =>
        prev.map((it) => (it.id === id ? { ...it, cargando: false, error: mensajeError(error, "No se pudo leer el PDF.") } : it))
      );
    }
  }

  function handlePdfsChange(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    setErrorGeneral(null);

    // Se calculan los duplicados leyendo el estado actual directamente (no
    // dentro del actualizador de setState): llamar efectos secundarios
    // (previsualizarPdf) desde un actualizador de estado es incorrecto y en
    // React StrictMode se ejecuta dos veces, duplicando las previsualizaciones.
    const yaCargados = new Set(pdfItems.map((it) => `${it.file.name}-${it.file.size}`));
    const repetidos: string[] = [];
    const nuevos: PdfItem[] = [];

    for (const file of files) {
      const clave = `${file.name}-${file.size}`;
      if (yaCargados.has(clave)) {
        repetidos.push(file.name);
        continue;
      }
      yaCargados.add(clave);
      nuevos.push({
        id: `${clave}-${Date.now()}-${Math.random()}`,
        file,
        materiaSeleccionada: "",
        preview: null,
        cargando: true,
        error: null,
        asistenciaFile: null,
        asistenciaRegular: null,
        asistenciaAviso: null,
      });
    }

    if (repetidos.length > 0) {
      setErrorGeneral(
        `Ya habías cargado ${repetidos.length === 1 ? "este archivo" : "estos archivos"}, no se agregó de nuevo: ${repetidos.join(", ")}.`
      );
    }

    setPdfItems((prev) => [...prev, ...nuevos]);
    setResultado(null);
    nuevos.forEach((item) => previsualizarPdf(item.id, item.file));
    e.target.value = "";
  }

  function quitarPdf(id: string) {
    setPdfItems((prev) => prev.filter((it) => it.id !== id));
  }

  function cambiarMateria(id: string, materia: string) {
    setPdfItems((prev) => prev.map((it) => (it.id === id ? { ...it, materiaSeleccionada: materia } : it)));
  }

  async function handleAsistenciaChange(id: string, e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setPdfItems((prev) => prev.map((it) => (it.id === id ? { ...it, asistenciaFile: file } : it)));
    if (!file) return;
    try {
      const formData = new FormData();
      formData.append("asistencia", file);
      const { data } = await api.post("/informes/asistencia-preview", formData);
      const item = pdfItems.find((it) => it.id === id);
      const aviso =
        item && item.preview && data.matriculados_asistencia !== item.preview.n_estudiantes
          ? `La planilla tiene ${data.matriculados_asistencia} estudiantes y el PDF tiene ${item.preview.n_estudiantes}. Verifica que sean el mismo grupo/corte.`
          : null;
      setPdfItems((prev) =>
        prev.map((it) => (it.id === id ? { ...it, asistenciaRegular: data.asistencia_regular, asistenciaAviso: aviso } : it))
      );
    } catch (error) {
      setPdfItems((prev) =>
        prev.map((it) => (it.id === id ? { ...it, asistenciaAviso: mensajeError(error, "No se pudo leer la asistencia.") } : it))
      );
    }
  }

  function contarEstados(progreso: EstudianteNota[]) {
    const conteo: Record<string, number> = {};
    for (const p of progreso) conteo[p.estado] = (conteo[p.estado] ?? 0) + 1;
    return conteo;
  }

  async function handleProcesar() {
    setErrorGeneral(null);
    if (!excelFile || pdfItems.length === 0) return;

    const materias = pdfItems.map((it) => it.materiaSeleccionada);
    const repetidas = materias.filter((m, i) => materias.indexOf(m) !== i);
    if (repetidas.length > 0) {
      setErrorGeneral(`Hay más de un PDF apuntando a la misma materia: ${[...new Set(repetidas)].join(", ")}.`);
      return;
    }

    setProcesando(true);
    try {
      const formData = new FormData();
      formData.append("corte", String(corte));
      formData.append("excel", excelFile);
      for (const item of pdfItems) {
        formData.append("pdfs", item.file);
        formData.append("materias", item.materiaSeleccionada);
        formData.append("asistencias_regular", item.asistenciaRegular != null ? String(item.asistenciaRegular) : "");
      }
      const { data } = await api.post<ProcesarResponse>("/informes/procesar", formData);
      setResultado(data);
      setMateriaFoco(data.resultados[0]?.materia ?? "");
    } catch (error) {
      setErrorGeneral(mensajeError(error, "No se pudo procesar la información."));
    } finally {
      setProcesando(false);
    }
  }

  function descargarExcel() {
    if (!resultado) return;
    const link = document.createElement("a");
    link.href = `data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,${resultado.excel_base64}`;
    link.download = resultado.excel_filename;
    link.click();
  }

  const materiaFocoResumen = resultado?.resultados.find((r) => r.materia === materiaFoco) ?? null;

  return (
    <>
      <Header />
      <main className="page">
        <p className="texto-ayuda">
          Carga los PDF de notas de todas tus materias para un corte, confirma a qué bloque de la plantilla
          corresponde cada uno, y el agente genera un solo Excel con Matriculados, Asistencia regular,
          Evaluados y Aprobaron de todas ellas. Cada materia procesada queda guardada en la base de datos
          para el Director y el Secretario Académico.
        </p>

        <section className="card">
          <h2>1. Corte y plantilla</h2>
          <div className="opciones-corte">
            {[1, 2, 3].map((c) => (
              <label key={c} className={`chip ${corte === c ? "chip--activo" : ""}`}>
                <input type="radio" name="corte" checked={corte === c} onChange={() => setCorte(c)} />
                {CORTE_LABELS[c]}
              </label>
            ))}
          </div>
          <label className="campo-archivo">
            Plantilla Excel del formato de gestión docente (MI-DO-FO16)
            <input type="file" accept=".xlsx" onChange={handleExcelChange} />
          </label>
          {excelFile && <p className="texto-ayuda">📄 {excelFile.name}</p>}
        </section>

        <section className="card">
          <h2>2. PDF de notas por materia</h2>
          <p className="texto-ayuda">Sube uno o varios PDF (uno por cada materia que dictas este corte).</p>
          <label className="campo-archivo">
            PDF de notas (reporte "Ver Calificaciones" de Academusoft)
            <input type="file" accept=".pdf" multiple onChange={handlePdfsChange} />
          </label>
        </section>

        {pdfItems.length > 0 && (
          <section className="card">
            <h2>3. Confirma la materia y la asistencia de cada PDF</h2>
            {pdfItems.map((item) => (
              <div key={item.id} className="panel-pdf">
                <div className="panel-pdf__titulo">
                  <strong>📄 {item.file.name}</strong>
                  {item.cargando && <span> — leyendo…</span>}
                  {item.preview && (
                    <span>
                      {" "}
                      → detectado: {item.preview.materia_detectada ?? "¿?"} ({item.preview.grupo ?? "grupo N/D"}) ·{" "}
                      {item.preview.n_estudiantes} estudiantes
                    </span>
                  )}
                  <button className="btn-quitar" onClick={() => quitarPdf(item.id)} title="Quitar">
                    ✕
                  </button>
                </div>

                {item.error && <p className="mensaje mensaje--error">{item.error}</p>}

                {item.preview && (
                  <>
                    <label>
                      Materia en la plantilla
                      {materiasDisponibles.length > 0 ? (
                        <select value={item.materiaSeleccionada} onChange={(e) => cambiarMateria(item.id, e.target.value)}>
                          {materiasDisponibles.map((m) => (
                            <option key={m} value={m}>
                              {m}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          value={item.materiaSeleccionada}
                          onChange={(e) => cambiarMateria(item.id, e.target.value)}
                        />
                      )}
                    </label>

                    <label className="campo-archivo">
                      Planilla de asistencia de {CORTE_LABELS[corte]} para esta materia (opcional)
                      <input type="file" accept=".xlsx" onChange={(e) => handleAsistenciaChange(item.id, e)} />
                    </label>
                    {item.asistenciaRegular != null && (
                      <p className="texto-ayuda">✅ Asistencia regular detectada: {item.asistenciaRegular}</p>
                    )}
                    {item.asistenciaAviso && <p className="mensaje mensaje--warning">{item.asistenciaAviso}</p>}

                    <h4>Evolución por corte y proyección de aprobación (Def. Pond)</h4>
                    <p className="texto-ayuda">
                      Ponderación real del acuerdo pedagógico: Corte 1 = 30%, Corte 2 = 30%, Corte 3 = 40%. "Def.
                      Pond" es lo que el estudiante ya tiene acumulado sobre 100; "Nota necesaria" es lo que le
                      falta sacar en lo que queda del curso para llegar a 60.
                    </p>
                    <ResumenConteoEstado corte={corte} conteo={contarEstados(item.preview.progreso)} />
                    <TablaProgreso progreso={item.preview.progreso} corte={corte} />
                  </>
                )}
              </div>
            ))}
          </section>
        )}

        <section className="card">
          <h2>4. Procesar</h2>
          {errorGeneral && <p className="mensaje mensaje--error">{errorGeneral}</p>}
          <button
            className="btn btn--primario"
            disabled={!excelFile || pdfItems.length === 0 || procesando}
            onClick={handleProcesar}
          >
            {procesando ? "Procesando…" : "🚀 Procesar todas las materias y generar un solo Excel"}
          </button>
        </section>

        {resultado && (
          <>
            <section className="card">
              <h2>Resultado</h2>
              <p className="mensaje mensaje--exito">
                Se actualizaron {resultado.resultados.length} materia(s) en un solo archivo y quedaron
                guardadas en la base de datos.
              </p>
              {resultado.resultados.map((r) => (
                <div key={r.materia} className="resumen-materia">
                  <h3>
                    {r.materia}
                    {r.grupo ? ` · grupo ${r.grupo}` : ""}
                  </h3>
                  <div className="kpis">
                    <Kpi etiqueta="Matriculados" valor={r.matriculados} />
                    <Kpi etiqueta="Asistencia regular" valor={r.asistencia_regular ?? "—"} />
                    <Kpi etiqueta="Evaluados" valor={r.evaluados} />
                    <Kpi etiqueta="Aprobaron" valor={r.aprobaron} />
                  </div>
                  {r.es_estimado && <p className="texto-ayuda">⚠️ Aprobaron es una ESTIMACIÓN (aún faltan cortes por calificar).</p>}
                  {r.asistencia_regular == null && (
                    <p className="texto-ayuda">⚠️ Sin planilla de asistencia: esa celda quedó marcada para completar a mano.</p>
                  )}
                </div>
              ))}
              <p className="texto-ayuda">
                Nota: Inasistencia, Reprobados y los dos % de cada materia se recalculan solos con las fórmulas
                del Excel al abrirlo/guardarlo en Excel o LibreOffice.
              </p>
              <button className="btn btn--primario" onClick={descargarExcel}>
                ⬇️ Descargar Excel con todas las materias
              </button>
            </section>

            <section className="card">
              <h2>5. Dashboard de rendimiento</h2>

              <h4>Totales de todas las materias</h4>
              <div className="totales-generales">
                <Kpi etiqueta="Matriculados" valor={sumar(resultado.resultados, "matriculados")} />
                <Kpi etiqueta="Asistencia regular" valor={sumarOpcional(resultado.resultados, "asistencia_regular")} />
                <Kpi etiqueta="Evaluados" valor={sumar(resultado.resultados, "evaluados")} />
                <Kpi etiqueta="Aprobaron" valor={sumar(resultado.resultados, "aprobaron")} />
              </div>

              <h4>Proyección: ¿quiénes ganan y quiénes pierden la materia?</h4>
              <p className="texto-ayuda">
                Suma de los {resultado.resultados.length} materia(s) procesadas, según el acumulado ponderado
                (Def. Pond) de cada estudiante a la fecha.
              </p>
              <ProyeccionGeneral resultados={resultado.resultados} corte={corte} />

              <div className="kpis">
                <Kpi
                  etiqueta="Promedio general (todos los estudiantes)"
                  valor={promedioGeneral(resultado.resultados).toFixed(1)}
                />
                <Kpi etiqueta="Dispersión general" valor={`±${dispersionGeneral(resultado.resultados).toFixed(1)}`} />
              </div>

              <div className="grid-2">
                <div>
                  <h4>Promedio general vs. mejor nota por asignatura</h4>
                  <GraficoPromedioVsMejor resultados={resultado.resultados} />
                </div>
                <div>
                  <h4>Dispersión (desviación estándar) por asignatura</h4>
                  <GraficoDispersion resultados={resultado.resultados} />
                </div>
              </div>

              <h4>Rendimiento por estudiante</h4>
              <label>
                Ver ranking de estudiantes de:
                <select value={materiaFoco} onChange={(e) => setMateriaFoco(e.target.value)}>
                  {resultado.resultados.map((r) => (
                    <option key={r.materia} value={r.materia}>
                      {r.materia}
                    </option>
                  ))}
                </select>
              </label>
              {materiaFocoResumen && <GraficoRanking resumen={materiaFocoResumen} />}
            </section>

            <section className="card">
              <h2>🧠 Interpretación del rendimiento</h2>
              <p className="mensaje mensaje--info">{resultado.interpretacion_general}</p>
              {resultado.resultados.map((r) => (
                <details key={r.materia} className="detalle-interpretacion">
                  <summary>
                    {r.materia} — promedio {r.promedio.toFixed(1)}, dispersión ±{r.desviacion.toFixed(1)}
                  </summary>
                  <div className="kpis">
                    <Kpi etiqueta="Promedio" valor={r.promedio.toFixed(1)} />
                    <Kpi etiqueta="Mediana" valor={r.mediana.toFixed(1)} />
                    <Kpi etiqueta="Desv. estándar" valor={`±${r.desviacion.toFixed(1)}`} />
                    <Kpi etiqueta="Coef. de variación" valor={`${r.coef_variacion.toFixed(0)}%`} />
                  </div>
                  <p>{r.interpretacion}</p>
                </details>
              ))}
            </section>
          </>
        )}
      </main>
    </>
  );
}

function Kpi({ etiqueta, valor }: { etiqueta: string; valor: string | number }) {
  return (
    <div className="kpi">
      <span className="kpi__valor">{valor}</span>
      <span className="kpi__etiqueta">{etiqueta}</span>
    </div>
  );
}

function ResumenConteoEstado({ corte, conteo }: { corte: number; conteo: Record<string, number> }) {
  if (corte === 3) {
    return (
      <p>
        ✅ {conteo["aprobado"] ?? 0} aprobaron · ❌ {conteo["reprobado"] ?? 0} reprobaron
      </p>
    );
  }
  return (
    <p>
      ✅ {conteo["asegurado"] ?? 0} ya aseguraron ganar la materia · ⚠️ {conteo["en_riesgo"] ?? 0} en riesgo (aún
      pueden ganar o perder) · ❌ {conteo["matematicamente_reprobado"] ?? 0} ya no pueden aprobar aunque saquen
      100 en lo que falta
    </p>
  );
}

function TablaProgreso({ progreso, corte }: { progreso: EstudianteNota[]; corte: number }) {
  const filas = [...progreso].sort((a, b) => b.def_pond - a.def_pond);
  return (
    <div className="tabla-scroll">
      <table className="tabla">
        <thead>
          <tr>
            <th>Estudiante</th>
            <th>Corte 1</th>
            {corte >= 2 && <th>Corte 2</th>}
            {corte >= 3 && <th>Corte 3</th>}
            <th>Def. Pond</th>
            <th>Nota necesaria</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.nombre}>
              <td>{f.nombre}</td>
              <td>{f.corte1}</td>
              {corte >= 2 && <td>{f.corte2}</td>}
              {corte >= 3 && <td>{f.corte3}</td>}
              <td>{f.def_pond.toFixed(1)}</td>
              <td>{f.nota_necesaria == null ? "—" : f.nota_necesaria.toFixed(1)}</td>
              <td>{ETIQUETA_ESTADO[f.estado]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function promedioGeneral(resultados: ResumenMateria[]): number {
  const todas = resultados.flatMap((r) => r.notas.map((n) => n.nota));
  return todas.length ? todas.reduce((a, b) => a + b, 0) / todas.length : 0;
}

function dispersionGeneral(resultados: ResumenMateria[]): number {
  const todas = resultados.flatMap((r) => r.notas.map((n) => n.nota));
  if (todas.length < 2) return 0;
  const media = promedioGeneral(resultados);
  const varianza = todas.reduce((acc, v) => acc + (v - media) ** 2, 0) / todas.length;
  return Math.sqrt(varianza);
}

function sumar(resultados: ResumenMateria[], campo: "matriculados" | "evaluados" | "aprobaron"): number {
  return resultados.reduce((acc, r) => acc + r[campo], 0);
}

function sumarOpcional(resultados: ResumenMateria[], campo: "asistencia_regular"): number | string {
  const conDato = resultados.filter((r) => r[campo] != null);
  if (conDato.length === 0) return "—";
  return conDato.reduce((acc, r) => acc + (r[campo] as number), 0);
}

const ETIQUETA_PROYECCION: Record<string, { texto: string; clase: string }> = {
  asegurado: { texto: "Ya aseguraron ganar la materia", clase: "proyeccion-item--ok" },
  aprobado: { texto: "Aprobaron", clase: "proyeccion-item--ok" },
  en_riesgo: { texto: "En riesgo (aún pueden ganar o perder)", clase: "proyeccion-item--riesgo" },
  matematicamente_reprobado: { texto: "Ya no pueden aprobar", clase: "proyeccion-item--mal" },
  reprobado: { texto: "Reprobaron", clase: "proyeccion-item--mal" },
};

function ProyeccionGeneral({ resultados, corte }: { resultados: ResumenMateria[]; corte: number }) {
  const total: Record<string, number> = {};
  for (const r of resultados) {
    for (const [estado, cantidad] of Object.entries(r.conteo_estado)) {
      total[estado] = (total[estado] ?? 0) + cantidad;
    }
  }

  const ordenEstados = corte === 3 ? ["aprobado", "reprobado"] : ["asegurado", "en_riesgo", "matematicamente_reprobado"];

  return (
    <div className="proyeccion">
      {ordenEstados.map((estado) => (
        <div key={estado} className={`proyeccion-item ${ETIQUETA_PROYECCION[estado].clase}`}>
          <span className="proyeccion-item__valor">{total[estado] ?? 0}</span>
          <span className="proyeccion-item__etiqueta">{ETIQUETA_PROYECCION[estado].texto}</span>
        </div>
      ))}
    </div>
  );
}
