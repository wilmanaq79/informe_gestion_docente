import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdministracionUsuarios } from "./AdministracionUsuariosPage";
import { api } from "../../api/client";
import { UsuarioAdmin } from "../../types";

vi.mock("../../api/client", async () => {
  const actual = await vi.importActual<typeof import("../../api/client")>("../../api/client");
  return {
    ...actual,
    api: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
  };
});

const USUARIO_EXISTENTE: UsuarioAdmin = {
  id: 7,
  nombre_completo: "PYTEST Docente",
  cedula: "123456",
  email: "docente@example.com",
  telefono: null,
  username: "pytest_docente",
  rol: "docente",
  activo: true,
};

describe("AdministracionUsuarios", () => {
  it("al hacer clic en Editar, precarga el formulario y guarda con PUT", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [USUARIO_EXISTENTE] });
    vi.mocked(api.put).mockResolvedValue({ data: {} });

    render(<AdministracionUsuarios onUsuarioCreado={vi.fn()} />);

    await screen.findByText("PYTEST Docente");

    fireEvent.click(screen.getByRole("button", { name: "✏️ Editar" }));

    // El formulario de edicion debe abrirse precargado con los datos actuales.
    expect(screen.getByDisplayValue("PYTEST Docente")).toBeInTheDocument();
    expect(screen.getByDisplayValue("123456")).toBeInTheDocument();
    expect(screen.getByDisplayValue("docente@example.com")).toBeInTheDocument();

    // En modo edicion no deben aparecer los campos de alta (usuario/contraseña/rol).
    expect(screen.queryByLabelText("Contraseña temporal")).not.toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("PYTEST Docente"), {
      target: { value: "PYTEST Docente Corregido" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith(
        "/usuarios/7",
        expect.objectContaining({ nombre_completo: "PYTEST Docente Corregido" })
      );
    });
    expect(api.post).not.toHaveBeenCalled();
  });

  it("el formulario de creación exige cédula y correo (atributo required)", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [] });

    render(<AdministracionUsuarios onUsuarioCreado={vi.fn()} />);
    await waitFor(() => expect(api.get).toHaveBeenCalled());

    expect(screen.getByLabelText("Cédula")).toBeRequired();
    expect(screen.getByLabelText("Correo institucional")).toBeRequired();
  });
});
