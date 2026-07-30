import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RepositorioAsignaturas from "./RepositorioAsignaturas";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { RepositorioAsignatura, Usuario } from "../types";

vi.mock("../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

function usuarioFalso(overrides: Partial<Usuario> = {}): Usuario {
  return {
    id: 1,
    nombre_completo: "PYTEST Director",
    rol: "director",
    programa_id: 1,
    programa_nombre: "Ingeniería de Sistemas",
    ...overrides,
  } as Usuario;
}

const ENTRADA_EXISTENTE: RepositorioAsignatura = {
  id: 1,
  asignatura: "SISTEMAS OPERATIVOS",
  docente_id: null,
  docente_nombre: null,
  silabo_nombre_archivo: null,
  silabo_tamano_bytes: null,
  programa_nombre_archivo: null,
  programa_tamano_bytes: null,
  creado_en: "2026-01-01T00:00:00Z",
  actualizado_en: "2026-01-01T00:00:00Z",
  creado_por_nombre: null,
  actualizado_por_nombre: null,
};

describe("RepositorioAsignaturas — sugerencia de materia al agregar", () => {
  it("al elegir una sugerencia, prellena el campo 'Nombre de la asignatura'", async () => {
    vi.mocked(useAuth).mockReturnValue({
      usuario: usuarioFalso(),
      cargando: false,
      login: vi.fn(),
      logout: vi.fn(),
      actualizarUsuario: vi.fn(),
    });
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === "/repositorio-asignaturas") return Promise.resolve({ data: [ENTRADA_EXISTENTE] });
      if (url === "/usuarios") return Promise.resolve({ data: [] });
      if (url === "/repositorio-asignaturas/materias-sugeridas") {
        return Promise.resolve({ data: ["SISTEMAS OPERATIVOS", "INTELIGENCIA ARTIFICIAL"] });
      }
      return Promise.resolve({ data: [] });
    });

    render(<RepositorioAsignaturas />);

    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/repositorio-asignaturas/materias-sugeridas"));

    fireEvent.click(screen.getByText("➕ Agregar asignatura al repositorio"));

    // "SISTEMAS OPERATIVOS" ya esta en el repositorio (ENTRADA_EXISTENTE) --
    // no debe ofrecerse de nuevo como sugerencia, solo la que falta.
    const selectSugerencia = screen.getByLabelText("Elegir una materia ya registrada por algún docente (opcional)");
    expect(screen.queryByRole("option", { name: "SISTEMAS OPERATIVOS" })).not.toBeInTheDocument();

    fireEvent.change(selectSugerencia, { target: { value: "INTELIGENCIA ARTIFICIAL" } });

    expect(screen.getByLabelText("Nombre de la asignatura")).toHaveValue("INTELIGENCIA ARTIFICIAL");
  });

  it("sin sugerencias disponibles, no muestra el selector y el campo queda libre", async () => {
    vi.mocked(useAuth).mockReturnValue({
      usuario: usuarioFalso(),
      cargando: false,
      login: vi.fn(),
      logout: vi.fn(),
      actualizarUsuario: vi.fn(),
    });
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === "/repositorio-asignaturas") return Promise.resolve({ data: [] });
      if (url === "/usuarios") return Promise.resolve({ data: [] });
      if (url === "/repositorio-asignaturas/materias-sugeridas") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });

    render(<RepositorioAsignaturas />);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/repositorio-asignaturas/materias-sugeridas"));

    fireEvent.click(screen.getByText("➕ Agregar asignatura al repositorio"));

    expect(
      screen.queryByLabelText("Elegir una materia ya registrada por algún docente (opcional)")
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Nombre de la asignatura")).toHaveValue("");
  });
});
