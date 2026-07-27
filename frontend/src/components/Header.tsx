import { useAuth } from "../context/AuthContext";
import NotificacionesBell from "./NotificacionesBell";

export default function Header() {
  const { usuario, logout } = useAuth();

  return (
    <header className="app-header">
      <div className="app-header__brand">
        <img src="/escudo_unpa.jpg" alt="Escudo Universidad del Pacífico" className="app-header__logo" />
        <div className="app-header__titles">
          <span className="app-header__eyebrow">Universidad del Pacífico</span>
          <h1>Programa de Ingeniería de Sistemas</h1>
          <span className="app-header__subtitle">📋 Sistema de Gestión y Autoevaluación Docente</span>
        </div>
        <img src="/logo_programa.png" alt="Logo del programa" className="app-header__logo app-header__logo--programa" />
      </div>

      {usuario && (
        <div className="app-header__user">
          <span>
            👋 <strong>{usuario.nombre_completo}</strong> · rol: <em>{usuario.rol}</em>
          </span>
          <NotificacionesBell />
          <button onClick={logout} className="btn btn--secondary">
            Cerrar sesión
          </button>
        </div>
      )}
    </header>
  );
}
