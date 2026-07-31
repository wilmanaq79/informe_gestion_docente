import { Outlet } from "react-router-dom";
import Header from "../components/Header";
import Sidebar from "../components/ui/Sidebar";

const SECCIONES = [
  { to: "calendario", etiqueta: "🗓️ Calendario académico" },
  { to: "tareas", etiqueta: "📋 Tareas" },
  { to: "entregas", etiqueta: "📎 Entregas" },
  { to: "repositorio", etiqueta: "📚 Repositorio" },
];

export default function SecretariaLayout() {
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
