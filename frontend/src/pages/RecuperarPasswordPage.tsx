import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import Header from "../components/Header";
import { api, mensajeError } from "../api/client";

export default function RecuperarPasswordPage() {
  const [username, setUsername] = useState("");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const { data } = await api.post("/auth/solicitar-recuperacion", { username });
      // Siempre se muestra el mismo mensaje generico que devuelve el
      // backend, exista o no el usuario -- evita revelar cuentas validas.
      setMensaje(data.mensaje);
    } catch (err) {
      setError(mensajeError(err, "No se pudo procesar la solicitud."));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <Header />
      <main className="page page--centrado">
        <form className="card card--login" onSubmit={handleSubmit}>
          <h2>¿Olvidaste tu contraseña?</h2>
          <p className="texto-ayuda" style={{ marginTop: "-0.5rem" }}>
            Ingresa tu usuario y, si tienes un correo institucional registrado, te enviaremos un enlace para
            restablecerla.
          </p>
          <label>
            Usuario
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
          </label>
          {error && <p className="mensaje mensaje--error">{error}</p>}
          {mensaje && <p className="mensaje mensaje--exito">{mensaje}</p>}
          <button type="submit" className="btn btn--primario" disabled={enviando}>
            {enviando ? "Enviando…" : "Enviar enlace de recuperación"}
          </button>
          <p className="texto-ayuda">
            <Link to="/login">Volver a iniciar sesión</Link>
          </p>
        </form>
      </main>
    </>
  );
}
