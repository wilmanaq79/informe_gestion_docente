import CalendarioAcademico from "../components/CalendarioAcademico";
import EntregasDocumentos from "../components/EntregasDocumentos";
import Header from "../components/Header";
import RepositorioAsignaturas from "../components/RepositorioAsignaturas";
import SeccionNav from "../components/ui/SeccionNav";

const SECCIONES_NAV = [
  { id: "calendario", etiqueta: "🗓️ Calendario académico" },
  { id: "entregas", etiqueta: "📎 Entregas" },
  { id: "repositorio", etiqueta: "📚 Repositorio" },
];

export default function SecretariaProgramaPage() {
  return (
    <>
      <Header />
      <SeccionNav secciones={SECCIONES_NAV} />
      <main className="page">
        <p className="texto-ayuda">
          Revisa las entregas documentales de los docentes (listas de asistencia, notas firmadas, informe de
          gestión docente) y aprueba o rechaza cada una. Al aprobar, se notifica por correo al Director, al
          Secretario Académico, a la Secretaria del Programa y al docente.
        </p>

        <CalendarioAcademico />

        <EntregasDocumentos />

        <RepositorioAsignaturas />
      </main>
    </>
  );
}
