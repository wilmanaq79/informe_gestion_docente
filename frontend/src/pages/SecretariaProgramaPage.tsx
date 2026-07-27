import CalendarioAcademico from "../components/CalendarioAcademico";
import EntregasDocumentos from "../components/EntregasDocumentos";
import Header from "../components/Header";

export default function SecretariaProgramaPage() {
  return (
    <>
      <Header />
      <main className="page">
        <p className="texto-ayuda">
          Revisa las entregas documentales de los docentes (listas de asistencia, notas firmadas, informe de
          gestión docente) y aprueba o rechaza cada una. Al aprobar, se notifica por correo al Director, al
          Secretario Académico, a la Secretaria del Programa y al docente.
        </p>

        <CalendarioAcademico />

        <EntregasDocumentos />
      </main>
    </>
  );
}
