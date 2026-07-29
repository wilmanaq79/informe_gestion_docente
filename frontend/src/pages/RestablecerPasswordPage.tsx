import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import Header from "../components/Header";
import { api, mensajeError } from "../api/client";

export default function RestablecerPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [passwordNueva, setPasswordNueva] = useState("");
  const [confirmarPassword, setConfirmarPassword] = useState("");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (passwordNueva !== confirmarPassword) {
      setError("La confirmación no coincide con la contraseña nueva.");
      return;
    }
    setGuardando(true);
    try {
      const { data } = await api.post("/auth/restablecer-password", { token, password_nueva: passwordNueva });
      setMensaje(data.mensaje);
    } catch (err) {
      setError(mensajeError(err, "No se pudo restablecer la contraseña."));
    } finally {
      setGuardando(false);
    }
  }

  if (!token) {
    return (
      <>
        <Header />
        <main className="page page--centrado">
          <div className="card card--login">
            <p className="mensaje mensaje--error">El enlace no incluye un token válido.</p>
            <p className="texto-ayuda">
              <Link to="/recuperar-password">Solicitar un nuevo enlace</Link>
            </p>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Header />
      <main className="page page--centrado">
        <form className="card card--login" onSubmit={handleSubmit}>
          <h2>Restablecer contraseña</h2>
          {!mensaje && (
            <>
              <label>
                Contraseña nueva
                <input
                  type="password"
                  value={passwordNueva}
                  onChange={(e) => setPasswordNueva(e.target.value)}
                  autoFocus
                  required
                  minLength={8}
                />
              </label>
              <label>
                Confirmar contraseña nueva
                <input
                  type="password"
                  value={confirmarPassword}
                  onChange={(e) => setConfirmarPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </label>
              {error && <p className="mensaje mensaje--error">{error}</p>}
              <button type="submit" className="btn btn--primario" disabled={guardando}>
                {guardando ? "Guardando…" : "Restablecer contraseña"}
              </button>
            </>
          )}
          {mensaje && (
            <>
              <p className="mensaje mensaje--exito">{mensaje}</p>
              <Link to="/login" className="btn btn--primario" style={{ textAlign: "center" }}>
                Iniciar sesión
              </Link>
            </>
          )}
        </form>
      </main>
    </>
  );
}
