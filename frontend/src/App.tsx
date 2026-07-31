import { Navigate, Route, Routes } from "react-router-dom";
import AvisoPrivacidad from "./components/AvisoPrivacidad";
import CalendarioAcademico from "./components/CalendarioAcademico";
import EntregasDocumentos from "./components/EntregasDocumentos";
import ProtectedRoute from "./components/ProtectedRoute";
import RepositorioAsignaturas from "./components/RepositorioAsignaturas";
import TareasModulo from "./components/TareasModulo";
import { useAuth } from "./context/AuthContext";
import DireccionLayout from "./layouts/DireccionLayout";
import DocenteLayout from "./layouts/DocenteLayout";
import SecretariaLayout from "./layouts/SecretariaLayout";
import CambiarPasswordPage from "./pages/CambiarPasswordPage";
import AdministracionUsuariosPage from "./pages/direccion/AdministracionUsuariosPage";
import InformesDocentesPage from "./pages/direccion/InformesDocentesPage";
import PeriodoActualPage from "./pages/direccion/PeriodoActualPage";
import CargarNotasPage from "./pages/docente/CargarNotasPage";
import LoginPage from "./pages/LoginPage";
import RecuperarPasswordPage from "./pages/RecuperarPasswordPage";
import RestablecerPasswordPage from "./pages/RestablecerPasswordPage";

function InicioSegunRol() {
  const { usuario } = useAuth();
  if (!usuario) return <Navigate to="/login" replace />;
  // Orden: primero la contraseña temporal (credencial sin rotar), despues
  // el aviso de privacidad -- igual que en el gate del backend (ver
  // backend/main.py, _gate).
  if (usuario.debe_cambiar_password) return <CambiarPasswordPage forzado />;
  if (!usuario.acepto_tratamiento_datos) return <AvisoPrivacidad />;
  if (usuario.rol === "docente") return <Navigate to="/docente" replace />;
  if (usuario.rol === "secretaria_programa") return <Navigate to="/secretaria" replace />;
  return <Navigate to="/direccion" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/recuperar-password" element={<RecuperarPasswordPage />} />
      <Route path="/restablecer-password" element={<RestablecerPasswordPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <InicioSegunRol />
          </ProtectedRoute>
        }
      />

      <Route
        path="/docente"
        element={
          <ProtectedRoute rolesPermitidos={["docente"]}>
            <DocenteLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="calendario" replace />} />
        <Route path="calendario" element={<CalendarioAcademico />} />
        <Route path="tareas" element={<TareasModulo />} />
        <Route path="notas" element={<CargarNotasPage />} />
        <Route path="entregas" element={<EntregasDocumentos />} />
        <Route path="repositorio" element={<RepositorioAsignaturas />} />
      </Route>

      <Route
        path="/direccion"
        element={
          <ProtectedRoute rolesPermitidos={["director", "secretario"]}>
            <DireccionLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="calendario" replace />} />
        <Route path="calendario" element={<CalendarioAcademico />} />
        <Route path="tareas" element={<TareasModulo />} />
        <Route path="periodo" element={<PeriodoActualPage />} />
        <Route path="informes" element={<InformesDocentesPage />} />
        <Route path="entregas" element={<EntregasDocumentos />} />
        <Route path="usuarios" element={<AdministracionUsuariosPage />} />
        <Route path="repositorio" element={<RepositorioAsignaturas />} />
      </Route>

      <Route
        path="/secretaria"
        element={
          <ProtectedRoute rolesPermitidos={["secretaria_programa"]}>
            <SecretariaLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="calendario" replace />} />
        <Route path="calendario" element={<CalendarioAcademico />} />
        <Route path="tareas" element={<TareasModulo />} />
        <Route path="entregas" element={<EntregasDocumentos />} />
        <Route path="repositorio" element={<RepositorioAsignaturas />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
