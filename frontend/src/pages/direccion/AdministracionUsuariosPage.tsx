import { FormEvent, useEffect, useState } from "react";
import { api, mensajeError } from "../../api/client";
import { UsuarioAdmin, UsuarioCreate, UsuarioUpdate } from "../../types";

const FORM_USUARIO_VACIO: UsuarioCreate = {
  nombre_completo: "",
  cedula: "",
  email: "",
  telefono: "",
  username: "",
  password: "",
  rol: "docente",
};

export function AdministracionUsuarios({ onUsuarioCreado }: { onUsuarioCreado: () => void }) {
  const [form, setForm] = useState<UsuarioCreate>(FORM_USUARIO_VACIO);
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [mensaje, setMensaje] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [editandoId, setEditandoId] = useState<number | null>(null);

  async function cargarUsuarios() {
    try {
      const { data } = await api.get<UsuarioAdmin[]>("/usuarios");
      setUsuarios(data);
    } catch (err) {
      setMensaje({ tipo: "error", texto: mensajeError(err, "No se pudo cargar el listado de usuarios.") });
    }
  }

  useEffect(() => {
    cargarUsuarios();
  }, []);

  function editar(u: UsuarioAdmin) {
    setEditandoId(u.id);
    setForm({
      nombre_completo: u.nombre_completo,
      cedula: u.cedula ?? "",
      email: u.email ?? "",
      telefono: u.telefono ?? "",
      username: u.username,
      password: "",
      rol: u.rol,
    });
    setMensaje(null);
  }

  function cancelarEdicion() {
    setEditandoId(null);
    setForm(FORM_USUARIO_VACIO);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setGuardando(true);
    setMensaje(null);
    try {
      if (editandoId != null) {
        const payload: UsuarioUpdate = {
          nombre_completo: form.nombre_completo,
          cedula: form.cedula,
          email: form.email,
          telefono: form.telefono,
        };
        await api.put(`/usuarios/${editandoId}`, payload);
        setMensaje({ tipo: "exito", texto: `Usuario '${form.username}' actualizado.` });
        cancelarEdicion();
      } else {
        await api.post("/usuarios", form);
        setMensaje({ tipo: "exito", texto: `Usuario '${form.username}' creado con rol '${form.rol}'.` });
        setForm(FORM_USUARIO_VACIO);
      }
      cargarUsuarios();
      onUsuarioCreado();
    } catch (err) {
      setMensaje({
        tipo: "error",
        texto: mensajeError(err, editandoId != null ? "No se pudo actualizar el usuario." : "No se pudo crear el usuario."),
      });
    } finally {
      setGuardando(false);
    }
  }

  return (
    <section className="card">
      <h2>👤 Administración de usuarios</h2>
      <p className="texto-ayuda">Crea aquí las cuentas de los 27 docentes, el Director y el Secretario Académico.</p>

      <details open={editandoId != null || usuarios.length === 0}>
        <summary>{editandoId != null ? "✏️ Editar usuario" : "➕ Crear nuevo usuario"}</summary>
        <form className="formulario-grid" onSubmit={handleSubmit}>
          <label>
            Nombre completo
            <input
              value={form.nombre_completo}
              onChange={(e) => setForm({ ...form, nombre_completo: e.target.value })}
              required
            />
          </label>
          <label>
            Cédula
            <input value={form.cedula} onChange={(e) => setForm({ ...form, cedula: e.target.value })} required />
          </label>
          <label>
            Correo institucional
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </label>
          <label>
            Teléfono (opcional)
            <input value={form.telefono} onChange={(e) => setForm({ ...form, telefono: e.target.value })} />
          </label>
          {editandoId == null && (
            <>
              <label>
                Usuario (para iniciar sesión)
                <input
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  required
                />
              </label>
              <label>
                Contraseña temporal
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  required
                />
              </label>
              <label>
                Rol
                <select value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value })}>
                  <option value="docente">docente</option>
                  <option value="director">director</option>
                  <option value="secretario">secretario</option>
                  <option value="secretaria_programa">secretaria del programa</option>
                </select>
              </label>
            </>
          )}
          {mensaje && <p className={`mensaje mensaje--${mensaje.tipo === "exito" ? "exito" : "error"}`}>{mensaje.texto}</p>}
          <div>
            <button type="submit" className="btn btn--primario" disabled={guardando}>
              {guardando ? "Guardando…" : editandoId != null ? "Guardar cambios" : "Crear usuario"}
            </button>{" "}
            {editandoId != null && (
              <button type="button" className="btn btn--secondary" onClick={cancelarEdicion}>
                Cancelar
              </button>
            )}
          </div>
        </form>
      </details>

      <details>
        <summary>Ver usuarios registrados</summary>
        <div className="tabla-scroll">
          <table className="tabla">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Usuario</th>
                <th>Rol</th>
                <th>Activo</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id}>
                  <td>{u.nombre_completo}</td>
                  <td>{u.username}</td>
                  <td>{u.rol}</td>
                  <td>{u.activo ? "Sí" : "No"}</td>
                  <td>
                    <button className="btn btn--secondary" onClick={() => editar(u)}>
                      ✏️ Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

export default function AdministracionUsuariosPage() {
  return <AdministracionUsuarios onUsuarioCreado={() => {}} />;
}
