import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import Header from "../components/Header";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { usuario, login, cargando } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (usuario) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión.");
    }
  }

  return (
    <>
      <Header />
      <main className="page page--centrado">
        <form className="card card--login" onSubmit={handleSubmit}>
          <h2>Iniciar sesión</h2>
          <label>
            Usuario
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
          </label>
          <label>
            Contraseña
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <p className="mensaje mensaje--error">{error}</p>}
          <button type="submit" className="btn btn--primario" disabled={cargando}>
            {cargando ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </main>
    </>
  );
}
