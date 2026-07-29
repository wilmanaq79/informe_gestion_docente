import { describe, expect, it } from "vitest";
import { mensajeError } from "./client";

function fakeAxiosError(detail: unknown) {
  return {
    isAxiosError: true,
    response: { data: { detail } },
  };
}

describe("mensajeError", () => {
  it("usa el detail del backend cuando es un string", () => {
    const error = fakeAxiosError("No se pudo aprobar la entrega.");
    expect(mensajeError(error, "fallback")).toBe("No se pudo aprobar la entrega.");
  });

  it("usa el fallback cuando el detail no es un string", () => {
    const error = fakeAxiosError({ algo: "no es texto" });
    expect(mensajeError(error, "fallback")).toBe("fallback");
  });

  it("usa el fallback cuando no es un error de axios", () => {
    expect(mensajeError(new Error("cualquier cosa"), "fallback")).toBe("fallback");
  });

  it("usa el fallback por defecto si no se indica uno", () => {
    expect(mensajeError(new Error("x"))).toBe("Ocurrió un error inesperado.");
  });
});
