import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import EstadoVacio from "./EstadoVacio";

describe("EstadoVacio", () => {
  it("muestra el texto indicado", () => {
    render(<EstadoVacio texto="No hay entregas para este filtro." />);
    expect(screen.getByText("No hay entregas para este filtro.")).toBeInTheDocument();
  });

  it("usa el icono por defecto cuando no se indica uno", () => {
    render(<EstadoVacio texto="x" />);
    expect(screen.getByText("📭")).toBeInTheDocument();
  });

  it("usa el icono personalizado cuando se indica", () => {
    render(<EstadoVacio icono="📎" texto="x" />);
    expect(screen.getByText("📎")).toBeInTheDocument();
  });
});
