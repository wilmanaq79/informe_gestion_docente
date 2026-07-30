import { Outlet } from "react-router-dom";
import Header from "../components/Header";
import Sidebar from "../components/ui/Sidebar";

const SECCIONES = [
  { to: "calendario", etiqueta: "🗓️ Calendario académico" },
  { to: "notas", etiqueta: "📥 Cargar notas (MI-DO-FO16)" },
  { to: "entregas", etiqueta: "📎 Entrega de documentos" },
  { to: "repositorio", etiqueta: "📚 Repositorio" },
];

export default function DocenteLayout() {
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
