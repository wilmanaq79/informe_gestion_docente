import { Outlet } from "react-router-dom";
import Header from "../components/Header";
import Sidebar from "../components/ui/Sidebar";

const SECCIONES = [
  { to: "calendario", etiqueta: "🗓️ Calendario académico" },
  { to: "tareas", etiqueta: "📋 Tareas" },
  { to: "periodo", etiqueta: "🟢 Periodo actual" },
  { to: "informes", etiqueta: "📊 Informes y seguimiento docente" },
  { to: "entregas", etiqueta: "📎 Entregas" },
  { to: "usuarios", etiqueta: "👤 Usuarios" },
  { to: "repositorio", etiqueta: "📚 Repositorio" },
];

export default function DireccionLayout() {
  return (
    <>
      <Header />
      <div className="app-shell__body">
        <Sidebar secciones={SECCIONES} />
        <main className="page">
          <Outlet />
        </main>
      </div>
    </>
  );
}
