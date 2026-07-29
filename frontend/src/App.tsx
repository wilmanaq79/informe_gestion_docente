import { Navigate, Route, Routes } from "react-router-dom";
import AvisoPrivacidad from "./components/AvisoPrivacidad";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import CambiarPasswordPage from "./pages/CambiarPasswordPage";
import DireccionPage from "./pages/DireccionPage";
import DocentePage from "./pages/DocentePage";
import LoginPage from "./pages/LoginPage";
import RecuperarPasswordPage from "./pages/RecuperarPasswordPage";
import RestablecerPasswordPage from "./pages/RestablecerPasswordPage";
import SecretariaProgramaPage from "./pages/SecretariaProgramaPage";

function InicioSegunRol() {
  const { usuario } = useAuth();
  if (!usuario) return <Navigate to="/login" replace />;
  // Orden: primero la contraseña temporal (credencial sin rotar), despues
  // el aviso de privacidad -- igual que en el gate del backend (ver
  // backend/main.py, _gate).
  if (usuario.debe_cambiar_password) return <CambiarPasswordPage forzado />;
  if (!usuario.acepto_tratamiento_datos) return <AvisoPrivacidad />;
  if (usuario.rol === "docente") return <DocentePage />;
  if (usuario.rol === "secretaria_programa") return <SecretariaProgramaPage />;
  return <DireccionPage />;
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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
