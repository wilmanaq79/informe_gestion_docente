import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import DireccionPage from "./pages/DireccionPage";
import DocentePage from "./pages/DocentePage";
import LoginPage from "./pages/LoginPage";
import SecretariaProgramaPage from "./pages/SecretariaProgramaPage";

function InicioSegunRol() {
  const { usuario } = useAuth();
  if (!usuario) return <Navigate to="/login" replace />;
  if (usuario.rol === "docente") return <DocentePage />;
  if (usuario.rol === "secretaria_programa") return <SecretariaProgramaPage />;
  return <DireccionPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <InicioSegunRol />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
