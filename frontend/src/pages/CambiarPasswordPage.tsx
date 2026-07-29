import { FormEvent, useState } from "react";
import Header from "../components/Header";
import { api, mensajeError } from "../api/client";
import { useAuth } from "../context/AuthContext";

/** Se muestra de dos formas: como gate obligatorio (usuario.debe_cambiar_password
 * true, forzado=true, sin botón para salir) y como acción libre en cualquier
 * momento (forzado=false, con botón "Cancelar" para volver). */
export default function CambiarPasswordPage({ forzado = false, onExito }: { forzado?: boolean; onExito?: () => void }) {
  const { usuario, actualizarUsuario } = useAuth();
  const [passwordActual, setPasswordActual] = useState("");
  const [passwordNueva, setPasswordNueva] = useState("");
  const [confirmarPassword, setConfirmarPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState(false);
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
      const { data } = await api.post("/auth/cambiar-password", {
        password_actual: passwordActual,
        password_nueva: passwordNueva,
      });
      if (usuario) actualizarUsuario({ ...usuario, debe_cambiar_password: data.debe_cambiar_password });
      setExito(true);
      setPasswordActual("");
      setPasswordNueva("");
      setConfirmarPassword("");
      onExito?.();
    } catch (err) {
      setError(mensajeError(err, "No se pudo cambiar la contraseña."));
    } finally {
      setGuardando(false);
    }
  }

  const formulario = (
    <form className="card card--login" onSubmit={handleSubmit}>
      <h2>🔑 {forzado ? "Debes cambiar tu contraseña" : "Cambiar mi contraseña"}</h2>
      {forzado && (
        <p className="texto-ayuda" style={{ marginTop: "-0.5rem" }}>
          Tu cuenta tiene una contraseña temporal. Elige una nueva para continuar.
        </p>
      )}
      <label>
        Contraseña actual
        <input
          type="password"
          value={passwordActual}
          onChange={(e) => setPasswordActual(e.target.value)}
          autoFocus
          required
        />
      </label>
      <label>
        Contraseña nueva
        <input type="password" value={passwordNueva} onChange={(e) => setPasswordNueva(e.target.value)} required minLength={8} />
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
      {exito && !forzado && <p className="mensaje mensaje--exito">Contraseña actualizada correctamente.</p>}
      <button type="submit" className="btn btn--primario" disabled={guardando}>
        {guardando ? "Guardando…" : "Cambiar contraseña"}
      </button>
    </form>
  );

  if (!forzado) return formulario;

  return (
    <>
      <Header />
      <main className="page page--centrado">{formulario}</main>
    </>
  );
}
