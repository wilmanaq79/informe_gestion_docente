import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import RestablecerPasswordPage from "./RestablecerPasswordPage";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, api: { post: vi.fn() } };
});

vi.mock("../components/Header", () => ({ default: () => null }));

function renderConToken(query: string) {
  return render(
    <MemoryRouter initialEntries={[`/restablecer-password${query}`]}>
      <Routes>
        <Route path="/restablecer-password" element={<RestablecerPasswordPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("RestablecerPasswordPage", () => {
  it("sin token en la URL, muestra un error y no el formulario", () => {
    renderConToken("");
    expect(screen.getByText("El enlace no incluye un token válido.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Contraseña nueva")).not.toBeInTheDocument();
  });

  it("con token en la URL, muestra el formulario de contraseña nueva", () => {
    renderConToken("?token=abc123");
    expect(screen.getByLabelText("Contraseña nueva")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirmar contraseña nueva")).toBeInTheDocument();
  });
});
