# Plan: edición de usuarios + cambio y recuperación de contraseña

## Contexto

Tras terminar el retrofit multi-programa, quedaron 3 pedidos pendientes del usuario:

1. **Bug ya corregido por separado** (fuera de este plan, ya autorizado): la cuenta `admin` quedó con `programa_id = NULL` tras la migración multi-programa y por eso no veía a wilman ni a ningún dato del programa piloto. Se corrige con un `UPDATE` de una sola fila antes/junto con este plan.
2. El Director y el Secretario Académico necesitan poder **editar** los datos de un usuario ya existente de su propio programa (nombre, cédula, correo — hoy solo se puede crear, nunca corregir un error de tipeo).
3. En el formulario de creación, la Cédula y el Correo dejan de ser opcionales (se les quita la palabra "opcional" y "Correo" pasa a llamarse "Correo institucional"). Esto se aplica igual en React y Streamlit, y se valida también en el backend (Pydantic), no solo en la UI.
4. Todos los roles deben poder **cambiar su contraseña** — obligatoriamente la primera vez que entren con una contraseña temporal (solo para cuentas creadas de ahora en adelante; admin y wilman no se ven afectados, ya confirmado), y libremente en cualquier momento después.
5. Todos los roles deben poder **recuperar su contraseña** (flujo "olvidé mi contraseña" por correo), implementado en React y en Streamlit por igual — así se ha construido cada funcionalidad anterior en este proyecto sin excepción.

Decisiones ya confirmadas con el usuario: no forzar el cambio de contraseña en las cuentas que ya existen hoy; sí corregir `admin.programa_id` de inmediato.

---

## Decisiones de diseño

- **El gate de "debes cambiar tu contraseña" se aplica en el servidor, no solo en la UI** — se agrega `requiere_password_actualizada` en `backend/api/deps.py`, con la misma forma que `requiere_consentimiento` (línea 45), y se agrega a la lista `_gate` en `backend/main.py` (línea 56): `_gate = [Depends(requiere_password_actualizada), Depends(requiere_consentimiento)]`. Igual que hoy, `auth` y `consentimiento` quedan fuera del gate para que `POST /api/auth/cambiar-password` siga funcionando mientras el gate está activo. Orden: primero contraseña temporal, después aviso de privacidad (una credencial temporal sin rotar es más urgente que una política sin aceptar). El frontend React (`InicioSegunRol` en `frontend/src/App.tsx:10`) y Streamlit (`app.py`) reproducen el mismo orden antes del chequeo de `acepto_tratamiento_datos`/`consentimiento.render(...)`.
- **Reutilizar el rate limiter existente para el flujo de recuperación** — `backend/core/rate_limit.py` ya recibe una `clave: str` arbitraria (no está atado al login). Para `solicitar-recuperacion` se usa `clave = f"reset:{hashlib.sha256(username_normalizado.encode()).hexdigest()[:16]}"` (cabe en el `VARCHAR(50)` de `IntentoLoginFallido.clave` sin importar el largo del username). No se crea tabla nueva para esto.
- **Token de recuperación**: se genera con `secrets.token_urlsafe(32)` (stdlib), y en BD solo se guarda su hash (`hashlib.sha256(token).hexdigest()`) — el token en texto plano solo existe en el correo enviado y en el POST de canje, nunca se persiste. Vence a los 30 minutos, uso único (al canjearlo se marca `usado_en`, y de paso se invalidan otros tokens vigentes del mismo usuario).
- **Validación de longitud mínima de contraseña** (8 caracteres) centralizada en una sola función (`db/auth.py::validar_longitud_password`), reutilizada por Pydantic (`field_validator`) en los 3 lugares donde se recibe una contraseña nueva: `UsuarioCreate.password`, `CambiarPasswordRequest.password_nueva`, `RestablecerPasswordRequest.password_nueva`.
- **`cambiar-password` responde 400, no 401, si la contraseña actual es incorrecta** — `frontend/src/api/client.ts` tiene un interceptor que fuerza logout+redirect en cualquier 401, y no queremos eso en este flujo.
- **Sin cambios retroactivos**: la migración agrega la columna `debe_cambiar_password` con `DEFAULT FALSE` y no actualiza ninguna fila existente. Solo `crear_usuario` (llamada tanto por `POST /api/usuarios` como por el formulario de Streamlit) fija `debe_cambiar_password = True` para las cuentas creadas de ahora en adelante, sin importar el rol.
- **Streamlit no tiene `BackgroundTasks`**: el envío de correo de recuperación ahí se hace de forma síncrona dentro del callback (igual que ya es síncrona la generación de PDF en `vistas/direccion.py`); en FastAPI sí se usa `background_tasks.add_task(...)` (mismo patrón que `_enviar_correo_aprobacion_en_segundo_plano` en `backend/api/routers/entregas.py`), con su propia sesión de BD nueva dentro de la tarea.

---

## Fase 1 — Migración de datos (`scripts/migrar_password_recuperacion.py`)

Script idempotente, mismo patrón que `scripts/migrar_rate_limit.py`:
```sql
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS debe_cambiar_password BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS tokens_recuperacion_password (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    creado_en TIMESTAMP NOT NULL DEFAULT now(),
    expira_en TIMESTAMP NOT NULL,
    usado_en TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_tokens_recuperacion_usuario_id ON tokens_recuperacion_password (usuario_id);
```

**Estado: ejecutado** (columna y tabla ya creadas en la base de datos de desarrollo, verificado idempotente corriéndolo dos veces).

## Fase 2 — Modelos y esquemas backend

- **`db/models.py`**: `Usuario` gana `debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)`. Nueva clase `TokenRecuperacionPassword` (estilo `AceptacionPoliticaTratamiento`): `id`, `usuario_id` (FK `ondelete="CASCADE"`, indexado), `token_hash` (String(64), unique), `creado_en`, `expira_en`, `usado_en` (nullable).
- **`backend/schemas/usuario.py`** (21 líneas): `UsuarioCreate.cedula`/`.email` pasan de `str | None = None` a `str` (obligatorios); se agrega `telefono: str | None = None` (el modelo `Usuario` ya tiene esta columna, pero nunca se expuso en ningún formulario — se aprovecha para exponerla ahora); `field_validator("password")` llamando a `validar_longitud_password`. `UsuarioOut` gana `telefono`. Nuevo `UsuarioUpdate(BaseModel)`: `nombre_completo`, `cedula`, `email`, `telefono`, todos `str | None = None` (sin username/password/rol — no pedidos).
- **`backend/schemas/auth.py`**: `UsuarioOut` gana `debe_cambiar_password: bool`. Nuevos `CambiarPasswordRequest{password_actual, password_nueva}`, `SolicitarRecuperacionRequest{username}`, `RestablecerPasswordRequest{token, password_nueva}`.
- **`db/auth.py`**: `MIN_PASSWORD_LENGTH = 8` + `validar_longitud_password(password: str) -> None`.
- **`backend/core/config.py`**: nuevo `FRONTEND_URL: str = "http://localhost:5173"` en `Settings`, más su entrada en `.env.example`.

## Fase 3 — Repositorio (`db/repository.py`)

- `crear_usuario(...)`: agrega parámetro `telefono`, fija `debe_cambiar_password=True` siempre en usuarios nuevos.
- `actualizar_usuario(session, usuario_id, **campos) -> Usuario | None`: mismo patrón fetch→setattr→commit→refresh que `actualizar_evento_calendario` (línea ~504).
- `crear_token_recuperacion(session, usuario_id) -> str`: genera el token crudo, persiste solo su hash + `expira_en` a 30 minutos, retorna el token crudo (única vez que existe en texto plano del lado del servidor).
- `consumir_token_recuperacion(session, token) -> Usuario | None`: hashea el token entrante, busca por `token_hash`, valida `usado_en is None` y no vencido; si es válido marca ese token (y cualquier otro vigente del mismo usuario) como usado y retorna el `Usuario`; si no, `None`.

## Fase 4 — Routers backend

- **`backend/api/deps.py`**: `requiere_password_actualizada(usuario: Usuario = Depends(get_current_user)) -> Usuario` — 403 si `usuario.debe_cambiar_password`.
- **`backend/main.py`**: `_gate` (línea 56) pasa a incluir `Depends(requiere_password_actualizada)` antes que `Depends(requiere_consentimiento)`.
- **`backend/api/routers/auth.py`**:
  - `_usuario_out`: agrega `debe_cambiar_password`.
  - `POST /api/auth/cambiar-password` (`Depends(get_current_user)`): verifica `password_actual`, 400 si no coincide; si coincide, actualiza hash + `debe_cambiar_password=False`.
  - `POST /api/auth/solicitar-recuperacion` (sin auth): rate-limit vía `bloqueado`/`registrar_intento_fallido` (clave hasheada); respuesta **siempre genérica** exista o no el usuario (anti-enumeración); si existe y tiene correo, genera token y encola el envío con `BackgroundTasks` (mismo patrón que `entregas.py`).
  - `POST /api/auth/restablecer-password` (sin auth): `consumir_token_recuperacion`; 400 genérico si inválido/vencido; si válido, nueva contraseña + `debe_cambiar_password=False`.
- **`backend/api/routers/usuarios.py`**: `_out` agrega `telefono`; `crear` pasa `telefono`; nuevo `PUT /api/usuarios/{id}` (roles `director`,`secretario`): fetch → 404 si no existe → `verificar_pertenece_a_programa` → `actualizar_usuario` con los campos enviados → mismo try/except de `IntegrityError` que `crear` (cédula duplicada).
- **`agente_notas/notificaciones.py`**: nueva `notificar_recuperacion_password(destinatario_email, destinatario_nombre, enlace) -> tuple[bool, str | None]`, mismo patrón que `notificar_entrega_aprobada` (nunca lanza, loggea advertencia si falla).

## Fase 5 — Pruebas backend (pytest)

- `requiere_password_actualizada`: pruebas unitarias estilo `TestRequiereRoles` en `tests/test_deps_rbac.py`.
- Token de recuperación: nueva `tests/test_password_recuperacion.py` (fixture `db_session`) — solo se persiste el hash, uso único, expiración, segunda solicitud invalida el token anterior.
- `actualizar_usuario` respeta el aislamiento por programa (extensión de `tests/test_multi_programa.py`).
- `UsuarioCreate` rechaza cédula/correo vacíos; `validar_longitud_password` rechaza <8 caracteres.

## Fase 6 — Frontend React

- **`frontend/src/types/index.ts`**: `Usuario` gana `debe_cambiar_password`; `UsuarioCreate.cedula`/`.email` pasan a obligatorios + `telefono?`; `UsuarioAdmin` gana `telefono`; nuevo tipo `UsuarioUpdate`.
- **`frontend/src/pages/DireccionPage.tsx`**, componente `AdministracionUsuarios` (líneas 459-582): quita "(opcional)", renombra a "Correo institucional", agrega campo `telefono`; agrega edición inline con `editandoId: number | null` + botón "✏️ Editar" por fila, exactamente como ya lo hace `frontend/src/components/CalendarioAcademico.tsx` (mismo componente `<details>` que se auto-expande, mismo submit que alterna `PUT`/`POST`).
- **`frontend/src/pages/CambiarPasswordPage.tsx`** (nueva): formulario contraseña actual/nueva, llama `POST /auth/cambiar-password`; al tener éxito actualiza `usuario.debe_cambiar_password` vía `actualizarUsuario` del `AuthContext`.
- **`frontend/src/pages/RecuperarPasswordPage.tsx`** (nueva): campo username, llama `POST /auth/solicitar-recuperacion`, siempre muestra el mensaje genérico.
- **`frontend/src/pages/RestablecerPasswordPage.tsx`** (nueva): lee `token` de la URL (`useSearchParams`), formulario de contraseña nueva, llama `POST /auth/restablecer-password`.
- **`frontend/src/App.tsx`**: rutas nuevas `/recuperar-password` y `/restablecer-password` (públicas, junto a `/login`); en `InicioSegunRol` (línea 10) se agrega el chequeo de `debe_cambiar_password` ANTES del chequeo de `acepto_tratamiento_datos`.
- **`frontend/src/pages/LoginPage.tsx`**: enlace "¿Olvidaste tu contraseña?".

## Fase 7 — Streamlit

- **`vistas/direccion.py`**: quita "(opcional)", renombra a "Correo institucional", agrega `telefono`, valida ambos como obligatorios en el submit; nuevo `st.expander("✏️ Editar datos de un usuario")` con el mismo patrón selectbox+formulario prellenado que ya usa `vistas/calendario.py` (líneas 79-113), llamando a `actualizar_usuario(...)`.
- **`vistas/cambiar_password.py`** (nuevo): mismo formato de gate que `vistas/consentimiento.py` (`render(session, usuario_id) -> bool`), más una variante no forzada reutilizable como acción libre en cualquier momento.
- **`app.py`**: gate de contraseña insertado antes del gate de consentimiento; entrada siempre visible "🔑 Cambiar mi contraseña".
- **`vistas/login.py`**: lee `st.query_params` — si trae `token`, muestra el formulario de restablecimiento en vez del login; agrega un expander "¿Olvidaste tu contraseña?" (solo pide username, mismo rate-limit y mensaje genérico que en React).

## Fase 8 — Pruebas frontend (vitest)

- Nueva prueba para el flujo de edición en `AdministracionUsuarios` (render tabla → clic Editar → formulario prellenado → submit llama `PUT`).
- Pruebas ligeras de `RecuperarPasswordPage`/`RestablecerPasswordPage` confirmando el mensaje genérico.

---

## Verificación

1. Correr la migración dos veces (confirmar idempotencia).
2. `pytest` completo (82 actuales + nuevas) en verde.
3. `npm test` (16 actuales + nuevas) en verde.
4. Prueba manual React: crear usuario (cédula/correo ahora obligatorios) → login → gate de cambio de contraseña forzado → cambiar → resto de la app accesible → logout → "¿Olvidaste tu contraseña?" → correo/log → reset por link → login con la nueva.
5. Prueba manual Streamlit: mismo flujo, incluida la pantalla de reset vía `?token=...`.
6. Confirmar que admin/wilman NO quedan con `debe_cambiar_password=True` (sin regresión sobre las cuentas ya existentes).
7. Confirmar que un Director del Programa A editando un usuario del Programa B recibe 403 (aislamiento multi-programa intacto).
8. Confirmar que `solicitar-recuperacion` bloquea tras 5 intentos por username y responde igual exista o no el usuario.
