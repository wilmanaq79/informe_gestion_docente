import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import RecuperarPasswordPage from "./RecuperarPasswordPage";
import { api } from "../api/client";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, api: { post: vi.fn() } };
});

vi.mock("../components/Header", () => ({ default: () => null }));

const MENSAJE_GENERICO = "Si el usuario existe, se enviará un correo con instrucciones para recuperar la contraseña.";

describe("RecuperarPasswordPage", () => {
  it("muestra el mensaje genérico cuando el usuario SÍ existe", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { mensaje: MENSAJE_GENERICO } });

    render(
      <MemoryRouter>
        <RecuperarPasswordPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Usuario"), { target: { value: "wilman" } });
    fireEvent.click(screen.getByRole("button", { name: /Enviar enlace/ }));

    await waitFor(() => expect(screen.getByText(MENSAJE_GENERICO)).toBeInTheDocument());
  });

  it("muestra el MISMO mensaje genérico cuando el usuario NO existe (anti-enumeración)", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { mensaje: MENSAJE_GENERICO } });

    render(
      <MemoryRouter>
        <RecuperarPasswordPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Usuario"), { target: { value: "no_existe" } });
    fireEvent.click(screen.getByRole("button", { name: /Enviar enlace/ }));

    await waitFor(() => expect(screen.getByText(MENSAJE_GENERICO)).toBeInTheDocument());
  });
});
