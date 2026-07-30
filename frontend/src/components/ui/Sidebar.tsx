import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

interface Seccion {
  to: string;
  etiqueta: string;
}

/** Navegación lateral persistente para las páginas autenticadas: en
 * escritorio es una columna fija a la izquierda; en pantallas angostas
 * colapsa a un panel off-canvas que se abre con el botón ☰ del Header
 * (ver useSidebar/SidebarToggle) y se cierra al elegir una sección o al
 * tocar el fondo oscurecido. Sustituye a SeccionNav (anclas + scroll)
 * ahora que cada sección es una ruta propia. */
export default function Sidebar({ secciones }: { secciones: Seccion[] }) {
  const [abierto, setAbierto] = useState(false);

  // Si la ventana crece a tamaño de escritorio con el panel movil
  // abierto, se cierra para no dejar el overlay huerfano.
  useEffect(() => {
    function alRedimensionar() {
      if (window.innerWidth >= 900) setAbierto(false);
    }
    window.addEventListener("resize", alRedimensionar);
    return () => window.removeEventListener("resize", alRedimensionar);
  }, []);

  return (
    <>
      <button
        type="button"
        className="sidebar__boton-movil"
        aria-label={abierto ? "Cerrar menú" : "Abrir menú"}
        aria-expanded={abierto}
        onClick={() => setAbierto((v) => !v)}
      >
        ☰
      </button>

      {abierto && <div className="sidebar__overlay" onClick={() => setAbierto(false)} />}

      <nav className={`sidebar ${abierto ? "sidebar--abierto" : ""}`} aria-label="Navegación principal">
        {secciones.map((s) => (
          <NavLink
            key={s.to}
            to={s.to}
            className={({ isActive }) => `sidebar__link ${isActive ? "sidebar__link--activo" : ""}`}
            onClick={() => setAbierto(false)}
          >
            {s.etiqueta}
          </NavLink>
        ))}
      </nav>
    </>
  );
}
