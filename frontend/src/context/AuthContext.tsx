import { createContext, ReactNode, useContext, useState } from "react";
import { api, mensajeError } from "../api/client";
import { LoginResponse, Usuario } from "../types";

interface AuthContextValue {
  usuario: Usuario | null;
  cargando: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  actualizarUsuario: (usuario: Usuario) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function usuarioGuardado(): Usuario | null {
  const raw = localStorage.getItem("usuario");
  return raw ? (JSON.parse(raw) as Usuario) : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(usuarioGuardado());
  const [cargando, setCargando] = useState(false);

  async function login(username: string, password: string) {
    setCargando(true);
    try {
      const { data } = await api.post<LoginResponse>("/auth/login", { username, password });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("usuario", JSON.stringify(data.usuario));
      setUsuario(data.usuario);
    } catch (error) {
      throw new Error(mensajeError(error, "Usuario o contraseña incorrectos."));
    } finally {
      setCargando(false);
    }
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("usuario");
    setUsuario(null);
  }

  function actualizarUsuario(nuevoUsuario: Usuario) {
    localStorage.setItem("usuario", JSON.stringify(nuevoUsuario));
    setUsuario(nuevoUsuario);
  }

  return (
    <AuthContext.Provider value={{ usuario, cargando, login, logout, actualizarUsuario }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
