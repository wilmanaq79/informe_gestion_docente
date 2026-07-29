import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Header from "./Header";
import { useAuth } from "../context/AuthContext";
import { Usuario } from "../types";

vi.mock("../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("./NotificacionesBell", () => ({
  default: () => null,
}));

function usuarioFalso(overrides: Partial<Usuario> = {}): Usuario {
  return {
    id: 1,
    nombre_completo: "PYTEST Usuario",
    rol: "director",
    programa_id: 1,
    programa_nombre: null,
    ...overrides,
  } as Usuario;
}

describe("Header", () => {
  it("renderiza el nombre del programa del usuario autenticado", () => {
    vi.mocked(useAuth).mockReturnValue({
      usuario: usuarioFalso({ programa_nombre: "Ingeniería Civil" }),
      cargando: false,
      login: vi.fn(),
      logout: vi.fn(),
      actualizarUsuario: vi.fn(),
    });

    render(<Header />);

    expect(screen.getByText("Programa de Ingeniería Civil")).toBeInTheDocument();
  });

  it("cambia dinámicamente el título si el usuario es de otro programa (no queda fijo)", () => {
    vi.mocked(useAuth).mockReturnValue({
      usuario: usuarioFalso({ programa_nombre: "Ingeniería Industrial" }),
      cargando: false,
      login: vi.fn(),
      logout: vi.fn(),
      actualizarUsuario: vi.fn(),
    });

    render(<Header />);

    expect(screen.getByText("Programa de Ingeniería Industrial")).toBeInTheDocument();
    expect(screen.queryByText("Programa de Ingeniería de Sistemas")).not.toBeInTheDocument();
  });

  it("usa un texto por defecto cuando no hay usuario autenticado", () => {
    vi.mocked(useAuth).mockReturnValue({
      usuario: null,
      cargando: false,
      login: vi.fn(),
      logout: vi.fn(),
      actualizarUsuario: vi.fn(),
    });

    render(<Header />);

    expect(screen.getByText("Programa de Gestión Docente")).toBeInTheDocument();
  });
});
