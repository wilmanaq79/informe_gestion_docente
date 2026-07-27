import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { Notificacion } from "../types";

function formatearFecha(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function NotificacionesBell() {
  const [abierto, setAbierto] = useState(false);
  const [noLeidas, setNoLeidas] = useState(0);
  const [notificaciones, setNotificaciones] = useState<Notificacion[]>([]);
  const contenedorRef = useRef<HTMLDivElement>(null);

  async function cargarContador() {
    try {
      const { data } = await api.get<{ no_leidas: number }>("/notificaciones/contador");
      setNoLeidas(data.no_leidas);
    } catch {
      // silencioso: la campanita no debe romper el resto de la app
    }
  }

  async function cargarLista() {
    try {
      const { data } = await api.get<Notificacion[]>("/notificaciones");
      setNotificaciones(data);
    } catch {
      // silencioso
    }
  }

  useEffect(() => {
    cargarContador();
  }, []);

  useEffect(() => {
    function alHacerClicFuera(e: MouseEvent) {
      if (contenedorRef.current && !contenedorRef.current.contains(e.target as Node)) {
        setAbierto(false);
      }
    }
    document.addEventListener("mousedown", alHacerClicFuera);
    return () => document.removeEventListener("mousedown", alHacerClicFuera);
  }, []);

  async function alAbrir() {
    const nuevoEstado = !abierto;
    setAbierto(nuevoEstado);
    if (nuevoEstado) await cargarLista();
  }

  async function marcarTodasLeidas() {
    try {
      await api.post("/notificaciones/leer-todas");
      setNotificaciones((prev) => prev.map((n) => ({ ...n, leida: true })));
      setNoLeidas(0);
    } catch {
      // silencioso
    }
  }

  async function marcarUnaLeida(n: Notificacion) {
    if (n.leida) return;
    try {
      await api.post(`/notificaciones/${n.id}/leer`);
      setNotificaciones((prev) => prev.map((x) => (x.id === n.id ? { ...x, leida: true } : x)));
      setNoLeidas((prev) => Math.max(0, prev - 1));
    } catch {
      // silencioso
    }
  }

  return (
    <div ref={contenedorRef} style={{ position: "relative" }}>
      <button
        className="btn btn--secondary"
        onClick={alAbrir}
        aria-label="Notificaciones"
        style={{ position: "relative" }}
      >
        🔔
        {noLeidas > 0 && (
          <span
            style={{
              position: "absolute",
              top: -6,
              right: -6,
              background: "#d03b3b",
              color: "white",
              borderRadius: "999px",
              fontSize: "0.7rem",
              padding: "0.05rem 0.4rem",
              fontWeight: 700,
            }}
          >
            {noLeidas}
          </span>
        )}
      </button>

      {abierto && (
        <div
          className="card"
          style={{
            position: "absolute",
            top: "110%",
            right: 0,
            width: "min(380px, 90vw)",
            maxHeight: "420px",
            overflowY: "auto",
            zIndex: 50,
            boxShadow: "0 4px 18px rgba(0,0,0,0.35)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong>Notificaciones</strong>
            {noLeidas > 0 && (
              <button className="btn btn--secondary btn--chico" onClick={marcarTodasLeidas}>
                Marcar todas leídas
              </button>
            )}
          </div>
          {notificaciones.length === 0 ? (
            <p className="texto-ayuda">No tienes notificaciones todavía.</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0" }}>
              {notificaciones.map((n) => (
                <li
                  key={n.id}
                  onClick={() => marcarUnaLeida(n)}
                  style={{
                    padding: "0.5rem 0",
                    borderBottom: "1px solid rgba(255,255,255,0.08)",
                    cursor: n.leida ? "default" : "pointer",
                    opacity: n.leida ? 0.65 : 1,
                  }}
                >
                  <div style={{ fontWeight: n.leida ? 400 : 700 }}>{n.mensaje}</div>
                  <div className="texto-ayuda" style={{ fontSize: "0.75rem" }}>
                    {formatearFecha(n.creado_en)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
