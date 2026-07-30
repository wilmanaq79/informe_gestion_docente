# Plan: rediseño de navegación — una página por sesión, en React y Streamlit

> Estado: aprobado 2026-07-30, en implementación. Documento de referencia del plan ejecutado en
> esta iteración (no se actualiza retroactivamente si el diseño cambia después; ver el código y
> los commits como fuente de verdad una vez terminado).

## Contexto

Hasta ahora cada rol veía **una sola página larga** con todas sus "sesiones" apiladas una debajo
de otra (Calendario, Corte y plantilla, PDF de notas, Procesar, Entregas, Repositorio, etc.), con
una barra de anclas (`SeccionNav`) para saltar por scroll. El usuario pidió separar cada sesión en
su propia página, "para que los roles puedan manipular de mejor manera la aplicación" — es decir,
reemplazar el scroll-and-jump por navegación real (URL propia, menos scroll, más foco por tarea).
Se confirmó aplicar esto **en React y en Streamlit a la vez** (React es el que se publica en el
VPS; Streamlit se mantiene en paridad).

Mejor práctica elegida: **shell de navegación lateral (sidebar) persistente**, con cada sesión
como una ruta/página propia — es el patrón estándar para apps internas con 3–8 secciones por rol
(más escaneable que tabs horizontales cuando hay 6-8 ítems, y permite deep-link/back-forward en
React). En Streamlit esto ya existe nativo desde 1.36 (`st.navigation`/`st.Page`, confirmada
versión instalada 1.60) y dibuja su propio sidebar sin CSS adicional.

## Inventario de páginas por rol

**Docente** (hoy: `DocentePage.tsx` / `vistas/docente.py`):
1. Calendario académico — ya es un componente autocontenido (`CalendarioAcademico`)
2. Cargar notas (Corte y plantilla + PDF de notas + Procesar) — **se mantienen juntas**: son un
   flujo secuencial con estado compartido (corte, excel, PDFs, resultado), no sesiones
   independientes
3. Entrega de documentos
4. Repositorio de sílabos y programas

**Director / Secretario Académico** (hoy: `DireccionPage.tsx` / `vistas/direccion.py`):
1. Calendario académico
2. Periodo actual del sistema (activar/crear periodo)
3. Informes y seguimiento docente (Año/Semestre/Corte + Dashboard + tabla de docentes + detalle
   e informe PDF + informe consolidado) — **se mantienen juntas**: el filtro Año/Semestre/Corte
   alimenta tanto el dashboard como la tabla/detalle, están acopladas por diseño
4. Entrega de documentos
5. Administración de usuarios
6. Repositorio de sílabos y programas

**Secretaria del Programa** (hoy: `SecretariaProgramaPage.tsx` / bloque en `app.py`):
1. Calendario académico
2. Entrega de documentos
3. Repositorio de sílabos y programas

## Corrección previa necesaria: desacoplar "Entregas" de "Cargar notas"

Antes del rediseño, `EntregasDocumentos` recibía `materiasDisponibles` como prop calculada de
forma transitoria en `DocentePage`/`docente.py` (parseada del Excel subido en la sección "Cargar
notas"). Si se navegaba a "Entrega de documentos" sin haber pasado por "Cargar notas" en la misma
sesión de navegador, la lista quedaba vacía — el mismo patrón de bug ya corregido dos veces antes
en este proyecto (repositorio de asignaturas, materias que desaparecían al refrescar). Antes de
separar páginas, se corrige igual: usar la fuente persistida en BD.

- Se reutiliza `db.repository.materias_del_docente(session, docente_id, periodo_id)` (ya existía,
  usado para las sugerencias del repositorio).
- Backend: nuevo `GET /api/entregas/materias-docente` en `backend/api/routers/entregas.py`,
  registrado junto a `/tipos-documento` (antes de `/{entrega_id}`), solo rol docente, resuelve
  `periodo_activo(db)` y devuelve `materias_del_docente(db, usuario.id, periodo.id)`.
- `EntregasDocumentos.tsx`: quita el prop `materiasDisponibles`; lo reemplaza por un fetch propio
  (mismo patrón que `materias-sugeridas` en `RepositorioAsignaturas.tsx`) solo cuando el rol es
  docente.
- `vistas/entregas.py::render()`: quita el parámetro `materias_disponibles`; calcula la lista
  internamente igual que el backend.
- Esto hace que "Entregas" sea 100% autocontenido en ambos stacks — requisito para que viva en su
  propia página/ruta sin perder la sugerencia de materia.

## React: shell de navegación

- **`frontend/src/components/ui/Sidebar.tsx`** (nuevo, sustituye a `SeccionNav` para las áreas
  autenticadas): recibe `secciones: {to, etiqueta}[]`, usa `<NavLink>` de react-router-dom (ya en
  `package.json`, v6.28) con estado activo (`aria-current="page"`); en desktop es una columna fija
  a la izquierda; en viewports angostos colapsa a un panel off-canvas abierto con un botón ☰
  agregado a `Header.tsx`, con overlay y cierre al elegir una opción — reutiliza los tokens ya
  definidos en `index.css` (`--surface`, `--border`, `--sombra`, etc.), sin nuevos colores.
  `SeccionNav.tsx` se elimina una vez migradas las 3 páginas de rol.
- **`frontend/src/layouts/DocenteLayout.tsx` / `DireccionLayout.tsx` / `SecretariaLayout.tsx`**
  (nuevos): cada uno renderiza `<Header/>` + `<Sidebar secciones={...}/>` + `<main
  className="page"><Outlet/></main>`. Layouts separados (no uno genérico parametrizado) porque
  cada rol tiene su propia lista de secciones y esto evita una capa de indirección innecesaria.
- **`frontend/src/App.tsx`**: `InicioSegunRol` se simplifica a solo los gates existentes
  (password temporal, aviso de privacidad — sin tocar ese orden) y al pasar redirige con
  `<Navigate to="/docente" | "/secretaria" | "/direccion" replace />` según el rol. Rutas anidadas
  nuevas:
  ```
  /docente     (ProtectedRoute rolesPermitidos=["docente"])            -> DocenteLayout
    index -> Navigate a "calendario"
    calendario   -> <CalendarioAcademico/>
    notas        -> <CargarNotasPage/>
    entregas     -> <EntregasDocumentos/>
    repositorio  -> <RepositorioAsignaturas/>
  /direccion   (rolesPermitidos=["director","secretario"])             -> DireccionLayout
    index -> Navigate a "calendario"
    calendario, periodo, informes, entregas, usuarios, repositorio (mismo patrón)
  /secretaria  (rolesPermitidos=["secretaria_programa"])                -> SecretariaLayout
    index -> Navigate a "calendario"
    calendario, entregas, repositorio
  ```
- **Extracción de páginas** (misma lógica, solo mueve código, sin reescribir):
  - `frontend/src/pages/docente/CargarNotasPage.tsx`: todo el estado y JSX de las secciones
    "Corte y plantilla" + "PDF de notas" + "Procesar" (antes en `DocentePage.tsx`).
  - `frontend/src/pages/direccion/PeriodoActualPage.tsx`: sección "Periodo actual" (con su
    estado `periodos/activarPeriodo/crearPeriodo`).
  - `frontend/src/pages/direccion/InformesDocentesPage.tsx`: "Alcance" + `DashboardInstitucional`
    + tabla de docentes + detalle/PDF + consolidado.
  - `frontend/src/pages/direccion/AdministracionUsuariosPage.tsx`: mueve el componente
    `AdministracionUsuarios` ya exportado tal cual.
  - `DocentePage.tsx`, `DireccionPage.tsx`, `SecretariaProgramaPage.tsx` se eliminan (superados
    por los layouts + páginas nuevas).
  - `CalendarioAcademico`, `EntregasDocumentos`, `RepositorioAsignaturas` no cambian (ya son
    autocontenidos) — se usan directamente como elemento de ruta.
- **Tests**: `DireccionPage.test.tsx` se mueve a
  `pages/direccion/AdministracionUsuariosPage.test.tsx` actualizando el import de
  `AdministracionUsuarios`. `RepositorioAsignaturas.test.tsx` / `Header.test.tsx` no cambian.

## Streamlit: `st.navigation` / `st.Page`

- **`vistas/direccion.py`**: se extraen del `render()` monolítico 3 funciones de nivel superior
  ya casi aisladas: `render_periodo(session)` (antes `_seccion_periodo_actual`),
  `render_informes()` (alcance + tabla + detalle + PDF), `render_administracion_usuarios()`
  (bloque ya delimitado). Sin cambios de lógica, solo de límites de función.
- **`vistas/docente.py`**: se extrae el bloque de notas a `render_cargar_notas(usuario_id)`;
  calendario/entregas/repositorio ya son llamadas directas reusables tal cual.
- **`app.py`**: tras los gates existentes (contraseña temporal, aviso de privacidad — sin tocar
  ese orden ni `render_forzado`/`render_opcional`), en vez de las llamadas in-line anteriores se
  arma `paginas = [st.Page(fn, title=..., icon=...), ...]` según el rol y se llama
  `st.navigation(paginas).run()`. `st.navigation` dibuja su propio sidebar nativo (sustituye a la
  necesidad de un `SeccionNav` en Streamlit) — no requiere CSS nuevo. El encabezado
  (`mostrar_encabezado`/`mostrar_barra_usuario`) y `notificaciones.render(...)` se mantienen antes
  de `st.navigation(...)`, igual que antes.
- Cada `st.Page(fn, ...)` envuelve las funciones de `vistas/*.py` en un lambda sin argumentos que
  captura `usuario_id`/`rol` de `st.session_state` (los `st.Page` no reciben argumentos).

## Verificación

1. `npm run build` (o `tsc --noEmit`) para confirmar que no quedan imports rotos tras mover/borrar
   `DocentePage.tsx`/`DireccionPage.tsx`/`SecretariaProgramaPage.tsx`.
2. `npm test` — todo verde, con el import corregido en el test movido.
3. `pytest` — sin cambios de lógica de negocio salvo el nuevo endpoint
   `/entregas/materias-docente` y la limpieza del parámetro `materias_disponibles`; confirmar que
   la suite completa sigue en verde.
4. Navegador, con los distintos roles (login real o inyección de JWT):
   - Confirmar que cada sección tiene su propia URL (`/docente/notas`, `/direccion/usuarios`,
     etc.), que el sidebar marca la sección activa, y que recargar la página en una sub-ruta no
     rompe nada.
   - Redimensionar a mobile y confirmar que el sidebar colapsa a drawer con el botón ☰ y cierra al
     elegir una sección.
   - Confirmar en "Entrega de documentos" que la materia aparece en el desplegable sin haber
     visitado antes "Cargar notas" en esa sesión (prueba directa de la corrección de
     acoplamiento).
5. Streamlit (`streamlit run app.py`): confirmar que el sidebar nativo lista las páginas correctas
   por rol, que cada una carga sin errores, y que el mismo caso de "Entregas sin pasar por Cargar
   notas" también funciona ahí.
