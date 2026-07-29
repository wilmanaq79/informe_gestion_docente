# Revisión integral del sistema — Gestión y Autoevaluación Docente

**Fecha:** 29 de julio de 2026
**Alcance:** todo el sistema — backend FastAPI, frontend React, frontend Streamlit, base de datos PostgreSQL y agentes de dominio (`agente_notas/`).
**Modalidad acordada con el usuario:** informe de hallazgos + corrección directa de todo lo clasificado como **crítico** o **alto**; lo de severidad media/baja queda documentado para que el usuario decida cuándo abordarlo. Se agregó además una suite de pruebas unitarias permanente (pytest + vitest) y se ejecutaron pruebas ACID reales contra la base de datos de desarrollo.

---

## 1. Metodología general

La revisión se organizó en 7 frentes, tal como los pidió el usuario. Para los 4 primeros (los de mayor volumen de código a leer) se usaron **agentes de exploración en paralelo** (de solo lectura, sin permiso de editar) para poder cubrir backend, base de datos, React y Streamlit simultáneamente sin que uno bloqueara a los demás. La matriz de permisos por rol y la aplicación de los fixes se hicieron directamente, no delegados, porque requerían ir y venir entre hallazgo → código real → verificación en vivo.

Cada corrección aplicada se verificó de una de estas formas antes de darla por terminada:
- Compilación (`py_compile` / `tsc -b`) para descartar errores de sintaxis.
- Una prueba **en vivo** contra el backend real corriendo (`uvicorn --reload`), con datos de prueba creados y borrados en la misma sesión.
- Una prueba unitaria nueva que quedó en la suite permanente (`tests/`, `frontend/src/**/*.test.ts(x)`).

Ninguna prueba contra la base de datos de desarrollo dejó datos huérfanos: las pruebas ACID usan una transacción que siempre se revierte (`tests/conftest.py`), y las pruebas manuales en vivo durante la sesión limpiaron explícitamente cualquier usuario/entrega de prueba creado.

---

## 2. Hallazgo por hallazgo

Cada hallazgo indica: severidad, dónde se encontró, qué significa en la práctica, y qué se hizo (corregido / documentado para decisión posterior).

### 2.1 Seguridad del backend (FastAPI)

| Severidad | Hallazgo | Estado |
|---|---|---|
| 🔴 Crítica | Sin whitelist de extensiones al subir archivos (`agente_notas/almacenamiento.py`) + descarga con `Content-Disposition: inline` adivinando el tipo por `mimetypes.guess_type()`. Un docente podía subir un `.html`/`.svg` con JavaScript embebido, y al abrirlo un Director/Secretario/Secretaria del Programa vía el botón "Ver", el navegador lo **ejecutaría** en el origen de la API (XSS almacenado, con robo de sesión de un rol privilegiado como consecuencia realista). | ✅ Corregido |
| 🟠 Alta | `/api/auth/login` sin límite de intentos: fuerza bruta/credential stuffing ilimitado contra cualquier cuenta, incluidas `director`/`secretario`. | ✅ Corregido |
| 🟠 Alta | Sin límite de tamaño de archivo/request en ningún endpoint de subida (`entregas`, `repositorio_asignaturas`, `informes`): un archivo arbitrariamente grande podía agotar memoria/disco (DoS). | ✅ Corregido |
| 🟡 Media | Mensajes de error que exponen el texto crudo de excepciones internas de SQLAlchemy/psycopg (`usuarios.py`, `repositorio_asignaturas.py`, `informes.py`). | 📋 Documentado |
| 🟡 Media | Sin validación de longitud/complejidad de contraseña al crear usuarios. | 📋 Documentado |
| 🟡 Media | `nombre_archivo` (tal como lo escribió el usuario) se interpola sin sanitizar en la cabecera `Content-Disposition`. | ✅ Corregido de paso (junto con el fix crítico de descarga) |
| 🟢 Baja | Credenciales por defecto débiles en `docker-compose.yml` si no se configura `.env` en el despliegue. | 📋 Documentado |
| 🟢 Baja | JWT sin mecanismo de revocación (8h de validez, logout no invalida nada del lado servidor). | 📋 Documentado |

**Verificado sano, sin hallazgo:** JWT con HS256 + expiración + secreto por variable de entorno; contraseñas con bcrypt (salt aleatorio); **todos** los endpoints sensibles usan `requiere_roles(...)`; **ningún** SQL crudo con datos de usuario (100% ORM parametrizado); protección contra path traversal ya existente (`ruta_absoluta_segura`); CORS con orígenes explícitos (no `"*"`); `_verificar_acceso_entrega` aplicado consistentemente (sin IDOR).

#### Qué se implementó

- **`agente_notas/almacenamiento.py`**: `EXTENSIONES_PERMITIDAS = {"pdf","xlsx","jpg","jpeg","png"}`, `TAMANO_MAXIMO_BYTES = 15 MB`, función `validar_archivo_subido()` que se ejecuta al inicio de `guardar_archivo_entrega()` y `guardar_archivo_repositorio()` — **antes** de tocar disco. Nueva excepción `ArchivoInvalido`.
- **`tipo_y_disposicion(nombre_archivo)`**: solo `pdf/jpg/jpeg/png` se sirven `inline`; cualquier otra cosa se fuerza a `attachment` + `application/octet-stream` — una segunda barrera independiente de la whitelist de subida, útil incluso para archivos guardados antes de este fix.
- **`nombre_seguro_para_header()`**: quita comillas dobles del nombre antes de ponerlo en `Content-Disposition`.
- **`backend/api/routers/entregas.py` y `repositorio_asignaturas.py`**: usan las 3 funciones anteriores; capturan `ArchivoInvalido` → HTTP 400.
- **`backend/core/rate_limit.py`** (nuevo): limitador de intentos de login en memoria por proceso — 5 intentos fallidos por usuario en 15 minutos → HTTP 429. Sin dependencias nuevas (no Redis). Documentado como limitación aceptada si el backend llegara a correr en varias réplicas (cada una llevaría su propio contador).
- **`backend/core/limite_tamano.py`** (nuevo): middleware ASGI que rechaza (HTTP 413) cualquier request con `Content-Length > 20 MB`, protegiendo también `informes.py` (que procesa Excel/PDF en memoria sin pasar por `almacenamiento.py`).

#### Verificación en vivo

```
1) subir .html malicioso        -> 400 "Tipo de archivo '.html' no permitido..."
2) subir archivo de 16 MB        -> 400 "El archivo pesa 16.0 MB; el máximo permitido es 15 MB."
3) 6 logins fallidos seguidos    -> el 6.º devuelve 429 "Demasiados intentos fallidos..."
```

---

### 2.2 Esquema de base de datos y propiedades ACID

| Severidad | Hallazgo | Estado |
|---|---|---|
| 🔴 Crítica | Al procesar un lote de varias materias en un mismo corte (`backend/services/informe_service.py` y `vistas/docente.py`), cada materia se guardaba con su **propio commit**. Si la materia 3 de 5 fallaba, las materias 1 y 2 quedaban comprometidas en la BD sin que el usuario supiera que la carga quedó a medias — violación directa de atomicidad. | ✅ Corregido |
| 🟠 Alta | En `RepositorioAsignatura`, 5 funciones (`adjuntar_silabo/programa`, `quitar_silabo/programa`, `eliminar_repositorio_asignatura`) borraban el archivo físico **antes** del `commit()`. Si el commit fallaba después, el archivo quedaba irrecuperable mientras la fila en BD seguía apuntando a él. | ✅ Corregido |
| 🟠 Alta | Ningún mecanismo a nivel de BD garantizaba "un solo periodo activo" — solo una convención en `db.repository.activar_periodo()`. Dos requests concurrentes podían dejar dos periodos activos a la vez. | ✅ Corregido |
| 🟠 Alta | `informes_corte.asignacion_id` sin `ON DELETE CASCADE` en la BD real, pese a que el ORM ya declara esa cascada (`cascade="all, delete-orphan"`). Un borrado por SQL directo fuera del grafo de sesión de SQLAlchemy fallaría con violación de FK. | ✅ Corregido |
| 🟠 Alta | 3 columnas FK de alto tráfico sin índice explícito (`notas_estudiantes.informe_corte_id`, `documentos_entrega.entrega_id`, `notificaciones.usuario_id`) — en Postgres una FK **no** crea índice automático. Consultas cada vez más lentas a medida que crecen esas tablas. | ✅ Corregido |
| 🟡 Media | `Usuario.email` sin `unique=True` (a diferencia de `username`/`cedula`). | 📋 Documentado |
| 🟡 Media | `NotaEstudiante` sin `UniqueConstraint(informe_corte_id, documento)`: un reprocesamiento con datos duplicados podría inflar los conteos del dashboard. | 📋 Documentado |
| 🟡 Media | `eliminar_informe_corte`/`eliminar_documento_entrega`: doble commit secuencial (borra hijo, luego borra padre si quedó vacío) — una interrupción entre ambos deja un padre "fantasma" vacío. | 📋 Documentado |
| 🟡 Media | `db/schema.sql` (documentación del esquema) desactualizado frente a `db/models.py` — le faltan varias tablas recientes. | 📋 Documentado |
| 🟢 Baja | `Usuario.cedula` nullable pese a `unique=True`. | 📋 Documentado |
| 🟢 Baja | Timestamps con `default=datetime.utcnow` (lado Python, no `server_default`), sin zona horaria. | 📋 Documentado |

**Verificado sano, sin hallazgo:** las combinaciones de negocio clave (docente+periodo+asignatura+grupo, asignación+corte, docente+periodo+corte, año+semestre) sí tienen `UniqueConstraint`; `guardar_informe_corte` ya era un buen ejemplo de atomicidad (un solo commit); las migraciones manuales existentes coinciden con `db/models.py` actual.

#### Qué se implementó

- **`db/repository.py`**: `obtener_o_crear_asignacion()` y `guardar_informe_corte()` reciben un parámetro `commit: bool = True`. Con `commit=False` hacen `flush()` en vez de `commit()`, dejando la escritura pendiente en la transacción actual.
- **`backend/services/informe_service.py`** y **`vistas/docente.py`**: dentro del bucle de materias llaman ambas funciones con `commit=False`; si el bucle completo termina sin error, **un solo** `db_session.commit()` al final; si cualquier materia falla, `db_session.rollback()` antes de propagar el error — todo o nada, real.
- **`db/repository.py`**: las 5 funciones de `RepositorioAsignatura` ahora guardan la ruta del archivo viejo en una variable local, hacen `commit()` primero, y **solo después** llaman `eliminar_archivo()`.
- **`db/models.py`**: índice único parcial `uq_un_solo_periodo_activo` (`ON (activo) WHERE activo`), y `index=True` en las 3 columnas FK mencionadas.
- **`scripts/migrar_indices_acid.py`** (nuevo, idempotente): crea los 3 índices, el índice único parcial, y recrea la FK de `informes_corte.asignacion_id` con `ON DELETE CASCADE`. **Ya ejecutado** contra la base de datos de desarrollo.

#### Verificación

Se confirmó contra Postgres real (no solo el código) que:
```sql
informes_corte_asignacion_id_fkey | FOREIGN KEY (asignacion_id) REFERENCES asignaciones_academicas(id) ON DELETE CASCADE
uq_un_solo_periodo_activo         | CREATE UNIQUE INDEX ... ON periodos_academicos (activo) WHERE activo
ix_notas_estudiantes_informe_corte_id, ix_documentos_entrega_entrega_id, ix_notificaciones_usuario_id  | creados
```
Y con pruebas automatizadas reales (ver sección 4 — Pruebas ACID) que la atomicidad del lote y la unicidad del periodo activo se cumplen en la práctica, no solo en el DDL.

---

### 2.3 Frontend React (calidad y seguridad)

Sin hallazgos críticos ni altos. Resumen de lo revisado (todo documentado, nada bloqueante):

- **Token JWT en `localStorage`** (no `httpOnly` cookie): patrón estándar en SPAs con axios, pero riesgo estructural ante un XSS futuro — mitigado en la práctica porque **no existe ningún** `dangerouslySetInnerHTML`/`innerHTML` en todo `frontend/src` (confirmado por grep exhaustivo). Logout automático en 401 ya implementado correctamente.
- **`AuthContext.tsx`**: `JSON.parse(localStorage.getItem("usuario"))` sin `try/catch` — un valor corrupto en `localStorage` tumbaría la app entera al arrancar. (Baja, documentado.)
- **`axios: "^1.7.9"`** en `package.json` incluye en su rango versiones con una CVE de SSRF ya corregida en 1.8.0; la versión **realmente instalada hoy** (`package-lock.json`) es 1.18.1, ya parcheada — el riesgo es solo para una instalación futura sin lockfile. (Media, documentado — recomendación: subir el piso del rango.)
- **Hallazgo adicional durante esta revisión (no parte de la lista original):** al instalar las herramientas de prueba, `npm audit` reveló que `react-router-dom` (dependencia de producción, no de prueba) tiene 2 CVEs moderados (open redirect + inyección en hidratación SSR — esta última no aplica, la app es un SPA puro sin SSR). El fix requiere saltar de la rama 6.x a 7.x, un cambio mayor con riesgo de romper el enrutamiento; **no se aplicó automáticamente** — queda documentado para que el usuario decida cuándo migrar y probar.
- Sin uso de índice como key en listas con estado propio, salvo un caso aceptable (celdas de gráfico sin identidad). Un caso de key por nombre de estudiante (`DocentePage.tsx`) en vez de documento — bajo impacto, documentado.
- `DireccionPage.tsx`/`DocentePage.tsx` son "god components" (varias secciones no relacionadas en un solo archivo) — deuda técnica de mantenibilidad, no un bug.
- Manejo de blobs (`URL.createObjectURL`/`revokeObjectURL`) correcto en todos los casos revisados.

---

### 2.4 Frontend Streamlit (calidad y seguridad)

| Severidad | Hallazgo | Estado |
|---|---|---|
| 🔴 Crítica | `vistas/docente.py`: el Excel de gestión docente se escribía siempre en el **mismo nombre de archivo fijo y global** (`__salida_temp_informe_gestion_docente.xlsx`, en el directorio del proceso). Si dos docentes generaban su informe al mismo tiempo (escenario realista: 27 docentes con la misma fecha límite), podían pisarse el archivo entre sí, o peor: uno podía terminar **descargando las notas de otro docente**. Además, si no había periodo activo, el archivo temporal quedaba huérfano en disco (el `st.stop()` ocurría antes de la limpieza). | ✅ Corregido |
| 🟠 Alta | `vistas/entregas.py`: `_aprobar()`/`_rechazar()` no verifican el rol de quien llama — dependen 100% de que `app.py` solo las alcance para roles revisores. Si cualquier cambio futuro de navegación las invocara desde otro camino, no habría una segunda barrera. | ✅ Corregido |
| 🟠 Alta | `vistas/direccion.py`: la creación de usuarios (con hash de contraseña) tiene la misma brecha — sin verificación de rol a nivel de función. | ✅ Corregido |
| 🟡 Media | `vistas/calendario.py`: `puede_editar` se recibe como parámetro del llamador, sin re-validarse contra el rol real de la sesión. | 📋 Documentado |
| 🟡 Media | `vistas/direccion.py`: el PDF temporal de informe por docente sí incluye el `docente_id` en el nombre (menor riesgo), pero dos administradores generando el informe del mismo docente a la vez aún podrían pisarse el archivo. | 📋 Documentado |
| 🟢 Baja | `db/seed.py`: cuenta de arranque `admin`/`cambiar123` hardcodeada (con recordatorio de cambiarla impreso en consola). | 📋 Documentado |

**Verificado sano, sin hallazgo:** el único uso real de `unsafe_allow_html=True` con datos "de usuario" es el PDF embebido en base64 en `vistas/entregas.py` — el alfabeto base64 no puede romper el atributo `src` ni inyectar HTML, así que no es explotable; todas las sesiones de BD (`get_session()`) se cierran correctamente en `try/finally`.

#### Qué se implementó

- **`vistas/docente.py`**: el nombre del archivo temporal ahora incluye `usuario_id` + un `uuid4().hex` único por invocación (`__salida_temp_informe_gestion_docente_{usuario_id}_{uuid}.xlsx`) — dos docentes nunca vuelven a compartir archivo. Además, la validación de "periodo activo" se movió **antes** de crear cualquier archivo en disco, así que un `st.stop()` por falta de periodo ya no deja huérfanos.
- **`vistas/entregas.py`**: `_aprobar()` y `_rechazar()` verifican explícitamente `st.session_state["usuario_rol"] in ("director","secretario","secretaria_programa")` antes de tocar la base de datos — igual que `requiere_roles(...)` en el backend FastAPI para el endpoint equivalente.
- **`vistas/direccion.py`**: el mismo tipo de verificación explícita antes de llamar `crear_usuario()`.

---

### 2.5 Matriz de permisos por rol

Se comparó, endpoint por endpoint, `requiere_roles(...)` en cada router de FastAPI contra lo que cada página de React y cada rama de Streamlit realmente muestra/llama para cada uno de los 4 roles (`docente`, `director`, `secretario`, `secretaria_programa`).

| Hallazgo | Severidad | Estado |
|---|---|---|
| `GET /api/calendario` (`backend/api/routers/calendario.py`) no incluía `secretaria_programa` entre los roles permitidos, pero `SecretariaProgramaPage.tsx` (React) sí le muestra la sección "🗓️ Calendario académico" — al cargar, su llamada a la API habría fallado con 403. En Streamlit este bug **no existe** porque esa app bypasa la API y llama directo a `db.repository`, sin `requiere_roles`. | 🟠 Alta (funcional, rompe una función visible para un rol real) | ✅ Corregido |

**Resto de la matriz, verificado consistente:** `usuarios.py` (secretaria_programa puede *listar* pero no *crear* usuarios — coincide con que su página de React no incluye el formulario de administración de usuarios); `repositorio_asignaturas.py` (`ROLES_TODOS` incluye a los 4 roles, coincide con que las 3 páginas la muestran); `entregas.py` (`ROLES_REVISORES` = director/secretario/secretaria_programa en los 3 frentes); `periodos.py`, `dashboard.py`, `docentes.py`, `informes.py`, `reportes.py` — todos consistentes con qué página/rama los usa.

#### Qué se implementó

`backend/api/routers/calendario.py`: se agregó `"secretaria_programa"` a los roles permitidos del endpoint `GET` (solo lectura — el diseño de que solo Director/Secretario editan el calendario se mantiene intacto).

---

## 3. Integridad funcional

Cubierta transversalmente por las secciones anteriores (los hallazgos "críticos" y "altos" de Streamlit y de la matriz de roles son, en esencia, bugs de integridad funcional: un docente podía recibir las notas de otro, y una Secretaria del Programa no podía ver el calendario). Adicionalmente:

- El flujo completo de "revisión manual obligatoria antes de aprobar" (construido en la sesión anterior, tarea previa a esta auditoría) se re-verificó con pruebas automatizadas nuevas (ver `tests/test_entregas_gate.py`): no se puede confirmar la revisión sin haber abierto el archivo, y no se puede aprobar la entrega sin haber confirmado todos los documentos que lo requieren.
- El agente de verificación de firmas (`agente_notas/agente_firmas.py`) se cubrió con 15 pruebas unitarias nuevas, incluyendo una reproducción exacta del falso positivo real reportado por el usuario en la sesión anterior (nombre de pila común "Andrés" coincidiendo con un estudiante).

---

## 4. Pruebas ACID reales contra la base de datos

Con datos de prueba claramente identificados y aislados (prefijo `__pytest_...`), usando siempre transacciones que se revierten al final (ver metodología en `tests/conftest.py`):

| Propiedad | Qué se probó | Resultado |
|---|---|---|
| **Atomicidad** | Reproduce el bug crítico encontrado: procesar un lote de 2 materias donde la segunda "falla" a mitad de camino. Con el fix (`commit=False` + un solo commit/rollback), la materia 1 **no** queda guardada tras el rollback del lote. | ✅ Pasa |
| **Consistencia** | (a) Crear dos usuarios con el mismo `username` → el segundo viola el `UniqueConstraint` (`IntegrityError`). (b) Activar un segundo periodo académico mientras otro ya está activo, vía `UPDATE` directo (sin pasar por `activar_periodo()`) → choca con el índice único parcial nuevo `uq_un_solo_periodo_activo`. | ✅ Pasa |
| **Aislamiento** | Una fila insertada por una conexión, sin `commit()`, **no** es visible desde una segunda conexión completamente distinta — confirma el nivel READ COMMITTED de Postgres. | ✅ Pasa |
| **Durabilidad** | Un `commit()` real, hecho en una sesión que luego se cierra, sigue siendo visible al reconectar con una sesión y conexión totalmente nuevas (no la misma). Esta prueba limpia su propio dato de prueba explícitamente al final (es la única que hace un commit real). | ✅ Pasa |

Las 4 pruebas viven en `tests/test_acid.py` (clases `TestAtomicidad`, `TestConsistencia`, `TestAislamiento`, `TestDurabilidad`) y quedan en la suite permanente — se pueden volver a correr en cualquier momento.

---

## 5. Buenas prácticas de un proyecto full-stack

Aplicadas como parte de las correcciones anteriores, en vez de como una lista aparte:

- **Defensa en profundidad**: cada control de acceso relevante ahora existe en **dos capas** independientes donde antes solo había una (backend `requiere_roles` + Streamlit revalida el rol también a nivel de función).
- **Fail-safe por defecto**: la whitelist de extensiones y el límite de tamaño rechazan explícitamente lo no reconocido, en vez de intentar adivinar qué es seguro.
- **Idempotencia**: las migraciones (`scripts/migrar_*.py`) usan `IF NOT EXISTS`/`DROP ... IF EXISTS` — se pueden re-ejecutar sin romper nada.
- **Un solo commit por operación de negocio**: el patrón `commit=False` + commit/rollback único en el caller, en vez de que cada función interna decida por su cuenta.
- **Nombres de archivo únicos por invocación** en vez de rutas fijas compartidas entre usuarios concurrentes.
- **Gestión de dependencias**: se detectó y documentó una dependencia de producción (`react-router-dom`) con CVEs conocidos — decisión de actualizar dejada al usuario por implicar un cambio de versión mayor.

---

## 6. Pruebas unitarias — suite permanente agregada

### Backend (pytest)

```bash
python -m pytest          # desde la raíz del proyecto, con el venv activado
```

| Archivo | Qué cubre |
|---|---|
| `tests/conftest.py` | Fixture `db_session`: transacción aislada con rollback automático (SQLAlchemy `join_transaction_mode="create_savepoint"`) — ningún test toca datos reales. |
| `tests/test_agente_firmas.py` | 15 pruebas del agente de firmas: normalización, coincidencia de palabra completa (no substring), exigencia de 2 partes del nombre, los 2 contextos de firma (PDF/Excel), y el falso positivo real ya corregido. |
| `tests/test_auth.py` | Hash de contraseñas (bcrypt) y JWT (emisión/decodificación/token manipulado). |
| `tests/test_rate_limit.py` | El limitador de intentos de login: bloqueo al 5.º intento, aislamiento entre usuarios, expiración de la ventana de 15 min. |
| `tests/test_almacenamiento.py` | Whitelist de extensiones, límite de tamaño, sanitización de nombres, protección contra path traversal, tipo/disposición seguros para descarga. |
| `tests/test_deps_rbac.py` | La dependencia `requiere_roles()` de FastAPI. |
| `tests/test_acid.py` | Las 4 pruebas ACID descritas en la sección 4. |
| `tests/test_entregas_gate.py` | El bloqueo de aprobación sin revisión manual confirmada (feature de la sesión anterior), contra la BD real con rollback. |

**Resultado actual: 67 pruebas, todas en verde.**

### Frontend (vitest + React Testing Library)

```bash
cd frontend && npm test
```

| Archivo | Qué cubre |
|---|---|
| `frontend/vite.config.ts` / `src/test/setup.ts` | Configuración de vitest (entorno jsdom) — nuevas devDependencies: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`. |
| `src/api/client.test.ts` | `mensajeError()`: extrae el mensaje del backend o cae al fallback. |
| `src/components/ui/EstadoVacio.test.tsx` | Render del componente compartido de estado vacío. |
| `src/components/EntregasDocumentos.test.ts` | La lógica del bloqueo de aprobación (`documentoNecesitaRevision`, `pendientesRevisionManual`) — el mismo comportamiento que se probó en Python, ahora también del lado del cliente. |

**Resultado actual: 13 pruebas, todas en verde.** El build de producción (`npm run build`) se verificó que sigue funcionando después de agregar las pruebas.

---

## 7. Resumen de archivos modificados o creados

**Backend / seguridad:**
`agente_notas/almacenamiento.py`, `backend/api/routers/entregas.py`, `backend/api/routers/repositorio_asignaturas.py`, `backend/api/routers/auth.py`, `backend/main.py` · nuevos: `backend/core/rate_limit.py`, `backend/core/limite_tamano.py`

**Base de datos / ACID:**
`db/models.py`, `db/repository.py`, `backend/services/informe_service.py`, `vistas/docente.py` · nuevo: `scripts/migrar_indices_acid.py` (ya ejecutado contra la BD)

**Roles:**
`backend/api/routers/calendario.py`

**Streamlit:**
`vistas/docente.py`, `vistas/entregas.py`, `vistas/direccion.py`

**Pruebas (nuevas):**
`pytest.ini`, `tests/conftest.py`, `tests/test_agente_firmas.py`, `tests/test_auth.py`, `tests/test_rate_limit.py`, `tests/test_almacenamiento.py`, `tests/test_deps_rbac.py`, `tests/test_acid.py`, `tests/test_entregas_gate.py`, `frontend/vite.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/api/client.test.ts`, `frontend/src/components/ui/EstadoVacio.test.tsx`, `frontend/src/components/EntregasDocumentos.test.ts`

**Dependencias:**
`requirements.txt` (+ `pytest`), `frontend/package.json` (+ vitest y RTL como devDependencies, script `test`)

---

## 8. Pendientes documentados (severidad media/baja — decisión del usuario)

1. Actualizar `react-router-dom` de 6.x a 7.x (2 CVEs moderados) — requiere probar todo el enrutamiento tras el cambio mayor.
2. Sanitizar mensajes de error que exponen excepciones internas crudas (`usuarios.py`, `repositorio_asignaturas.py`, `informes.py`).
3. Validar longitud/complejidad mínima de contraseña al crear usuarios.
4. `Usuario.email` sin `unique=True`; `NotaEstudiante` sin constraint anti-duplicados por estudiante+corte.
5. Cambiar la cuenta de arranque `admin`/`cambiar123` (`db/seed.py`) en cualquier despliegue real, si aún no se hizo.
6. Revalidar `puede_editar` contra el rol de sesión dentro de `vistas/calendario.py` (defensa en profundidad adicional).
7. Actualizar `docker-compose.yml` para no tener contraseñas por defecto débiles si falta `.env`.
8. Actualizar `db/schema.sql` (documentación) para reflejar las tablas agregadas en los últimos meses.
