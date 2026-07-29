import { describe, expect, it } from "vitest";
import { documentoNecesitaRevision, pendientesRevisionManual } from "./EntregasDocumentos";
import { DocumentoEntrega, Entrega } from "../types";

function documentoFalso(overrides: Partial<DocumentoEntrega> = {}): DocumentoEntrega {
  return {
    id: 1,
    tipo_documento: "lista_asistencia",
    descripcion_otro: null,
    materia: null,
    nombre_archivo: "archivo.pdf",
    tamano_bytes: 1024,
    subido_en: "2026-01-01T00:00:00Z",
    firma_detectada: null,
    firma_confianza: null,
    firma_detalle: null,
    visto_en: null,
    revisado_manualmente: false,
    revisado_por_nombre: null,
    revisado_en: null,
    ...overrides,
  };
}

function entregaFalsa(documentos: DocumentoEntrega[]): Entrega {
  return {
    id: 1,
    docente_id: 1,
    docente_nombre: "TEST",
    periodo_id: 1,
    periodo_nombre: "2026-1",
    corte_id: 1,
    corte_numero: 1,
    corte_nombre: "Corte 1",
    estado: "pendiente",
    documentos_firmados_confirmado: false,
    comentario_revision: null,
    revisado_por_nombre: null,
    revisado_en: null,
    notificacion_enviada: false,
    notificacion_error: null,
    creado_en: "2026-01-01T00:00:00Z",
    actualizado_en: "2026-01-01T00:00:00Z",
    todos_firmados_agente: false,
    documentos,
  };
}

describe("documentoNecesitaRevision", () => {
  it("un documento Firmado (true) no necesita revision", () => {
    expect(documentoNecesitaRevision(documentoFalso({ firma_detectada: true }))).toBe(false);
  });

  it("un documento No firmado (false) necesita revision", () => {
    expect(documentoNecesitaRevision(documentoFalso({ firma_detectada: false }))).toBe(true);
  });

  it("un documento en Revision manual (null) necesita revision", () => {
    expect(documentoNecesitaRevision(documentoFalso({ firma_detectada: null }))).toBe(true);
  });
});

describe("pendientesRevisionManual", () => {
  it("no bloquea si todos los documentos ya estan firmados o confirmados", () => {
    const entrega = entregaFalsa([
      documentoFalso({ id: 1, firma_detectada: true }),
      documentoFalso({ id: 2, firma_detectada: false, revisado_manualmente: true }),
    ]);
    expect(pendientesRevisionManual(entrega)).toHaveLength(0);
  });

  it("bloquea mientras falte confirmar un documento sin firmar", () => {
    const entrega = entregaFalsa([
      documentoFalso({ id: 1, firma_detectada: true }),
      documentoFalso({ id: 2, firma_detectada: false, revisado_manualmente: false }),
    ]);
    const pendientes = pendientesRevisionManual(entrega);
    expect(pendientes).toHaveLength(1);
    expect(pendientes[0].id).toBe(2);
  });

  it("bloquea mientras falte confirmar un documento en revision manual (null)", () => {
    const entrega = entregaFalsa([documentoFalso({ id: 3, firma_detectada: null, revisado_manualmente: false })]);
    expect(pendientesRevisionManual(entrega)).toHaveLength(1);
  });
});
