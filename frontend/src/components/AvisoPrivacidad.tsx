import { Fragment, useEffect, useState } from "react";
import { api, mensajeError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Politica } from "../types";

function renderParrafo(parrafo: string, indice: number) {
  const partes = parrafo.split(/\*\*(.+?)\*\*/g);
  return (
    <p key={indice} style={{ marginBottom: "0.85rem", lineHeight: 1.55 }}>
      {partes.map((parte, i) =>
        i % 2 === 1 ? <strong key={i}>{parte}</strong> : <Fragment key={i}>{parte}</Fragment>
      )}
    </p>
  );
}

export default function AvisoPrivacidad() {
  const { usuario, actualizarUsuario, logout } = useAuth();
  const [politica, setPolitica] = useState<Politica | null>(null);
  const [acepto, setAcepto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Politica>("/consentimiento/politica")
      .then(({ data }) => setPolitica(data))
      .catch((err) => setError(mensajeError(err, "No se pudo cargar el aviso de privacidad.")));
  }, []);

  async function aceptar() {
    setEnviando(true);
    setError(null);
    try {
      const { data } = await api.post("/consentimiento/aceptar");
      actualizarUsuario(data);
    } catch (err) {
      setError(mensajeError(err, "No se pudo registrar la aceptación. Intenta de nuevo."));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div style={{ maxWidth: "780px", margin: "2rem auto", padding: "0 1rem" }}>
      <section className="card">
        <h2>🔒 {politica?.titulo ?? "Aviso de Privacidad y Autorización para el Tratamiento de Datos Personales"}</h2>
        <p className="texto-ayuda">
          Hola {usuario?.nombre_completo}. Antes de continuar, debes leer y aceptar esta política. Aplica a los 4
          roles del sistema (Docente, Director, Secretario Académico y Secretaria del Programa).
        </p>

        {error && <p className="mensaje mensaje--error">{error}</p>}

        <div
          style={{
            maxHeight: "45vh",
            overflowY: "auto",
            border: "1px solid var(--color-borde, #ccc)",
            borderRadius: "8px",
            padding: "1rem",
            marginBottom: "1rem",
          }}
        >
          {politica ? (
            politica.texto.split(/\n\n+/).map((parrafo, i) => renderParrafo(parrafo, i))
          ) : (
            <p>Cargando…</p>
          )}
        </div>

        <label style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", marginBottom: "1rem" }}>
          <input type="checkbox" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} />
          <span>
            He leído y acepto el tratamiento de mis datos personales conforme a lo descrito en esta política.
          </span>
        </label>

        <div style={{ display: "flex", gap: "0.75rem" }}>
          <button className="btn btn--primario" disabled={!acepto || !politica || enviando} onClick={aceptar}>
            {enviando ? "Guardando…" : "Aceptar y continuar"}
          </button>
          <button className="btn btn--secondary" onClick={logout}>
            Cerrar sesión
          </button>
        </div>
      </section>
    </div>
  );
}
