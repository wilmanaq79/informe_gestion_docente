# Entendiendo la lógica del proyecto (guía para quien no programa)

Este documento explica **cómo está armado el proyecto por dentro**: qué hace
cada pieza, cómo se conectan entre sí, y qué pasa exactamente cuando un
docente sube un PDF de notas o cuando alguien inicia sesión. Está escrito
asumiendo que no tienes experiencia previa desarrollando software — cada
término técnico se explica la primera vez que aparece.

---

## 1. La idea general, con una analogía

Piensa en el sistema como un **restaurante**:

- La **base de datos (PostgreSQL)** es la despensa/bodega: ahí se guarda todo
  de forma permanente y ordenada (usuarios, notas, documentos, calendario).
- El **backend (FastAPI)** es la cocina: recibe pedidos, va a la despensa a
  buscar o guardar ingredientes, los prepara según reglas fijas, y entrega el
  plato listo. Nadie de afuera entra a la cocina directamente.
- El **frontend (React)** es el salón y los meseros: es lo que el usuario ve
  y toca (botones, formularios, tablas). Cuando el usuario pide algo, el
  mesero va a la cocina (backend), nunca a la despensa directamente.
- El **"agente"** (`agente_notas/`) es el chef especializado dentro de la
  cocina: sabe leer un PDF de calificaciones y una plantilla de Excel, hacer
  los cálculos exactos que pide el reglamento académico, y escribir el
  resultado.
- **Docker** es el edificio prefabricado donde vive la despensa (la base de
  datos): en vez de instalar PostgreSQL directamente en tu computador, corre
  dentro de un "contenedor" — un entorno aislado y reproducible — para que
  sea idéntico en cualquier máquina donde se use.
- **Streamlit** es un segundo salón de atención, más sencillo, que atiende a
  los mismos clientes pero sin pasar por los mismos meseros (ver sección 8).

Con esa imagen en la cabeza, vamos por cada pieza en detalle.

---

## 2. Mapa de carpetas: qué vive dónde

```
E:\informe_de_gestion\
├── db/                 <- La despensa: modelos de datos y acceso a PostgreSQL
├── agente_notas/       <- El chef especializado: lógica de negocio, PDF/Excel, archivos, correo
├── backend/            <- La cocina: API que expone esa lógica por internet (para React)
├── frontend/            <- El salón: interfaz web en React
├── vistas/ + app.py      <- El segundo salón: interfaz alternativa en Streamlit
├── scripts/             <- Herramientas de un solo uso (crear tablas, arreglar datos)
├── docker-compose.yml   <- La receta para levantar el contenedor de PostgreSQL
└── docs/                <- Esta documentación
```

Una regla de oro de este proyecto: **`db/` y `agente_notas/` son el único
lugar donde vive la lógica real** (cómo se calculan las notas, cómo se
guardan los datos). Tanto el backend (para React) como `vistas/` (para
Streamlit) son solo dos "puertas de entrada" distintas a esa misma lógica —
así que un docente ve exactamente el mismo comportamiento sin importar cuál
interfaz use.

---

## 3. La base de datos (PostgreSQL + Docker)

### ¿Qué es una base de datos?

Un programa especializado en guardar información de forma organizada en
**tablas** (como hojas de Excel, pero con reglas estrictas de qué se puede
guardar en cada columna, y capacidad de relacionar una tabla con otra). Este
proyecto usa **PostgreSQL**, una de las bases de datos más usadas en el
mundo.

### ¿Qué es Docker y por qué se usa?

Docker permite empaquetar un programa (aquí, PostgreSQL) junto con todo lo
que necesita para funcionar, en una caja aislada llamada **contenedor**. Ese
contenedor se comporta igual sin importar en qué computador corra. La
"receta" para construir ese contenedor está en `docker-compose.yml`, en la
raíz del proyecto — ahí se definen cosas como el usuario, la contraseña, el
nombre de la base de datos, y el **puerto** (la "puerta" numerada por la que
otros programas se conectan a ella; aquí, el `5432`, el puerto de fábrica de
PostgreSQL).

Cuando corres `docker compose up -d`, Docker lee esa receta y levanta el
contenedor. El backend y Streamlit se conectan a `localhost:5432` como si
PostgreSQL estuviera instalado directamente en tu máquina — Docker hace esa
parte transparente.

### Las tablas del proyecto (`db/models.py`)

Este archivo define, en Python, cada tabla de la base de datos como una
**clase**. SQLAlchemy (la librería que se usa) es lo que se llama un **ORM**
(*Object-Relational Mapper*): traduce esas clases de Python a tablas SQL de
verdad, para que el resto del código pueda decir `Usuario(...)` en vez de
escribir sentencias SQL a mano.

Las tablas principales, agrupadas por tema:

| Tabla | Para qué sirve |
|---|---|
| `roles` | Los 4 roles del sistema: docente, director, secretario, secretaria_programa |
| `usuarios` | Cuentas de acceso (nombre, usuario, contraseña encriptada, rol) |
| `periodos_academicos` | Los semestres (2026-1, 2026-2...), con año/semestre y cuál está "activo" |
| `cortes` | Corte 1, Corte 2, Corte 3/Final — fijos, no cambian |
| `asignaciones_academicas` | Qué materia dicta cada docente, en qué periodo |
| `informes_corte` | El resumen (matriculados, evaluados, aprobados, promedio...) de una materia en un corte |
| `notas_estudiantes` | El detalle nota por nota de cada estudiante, que respalda a `informes_corte` |
| `eventos_calendario` | Las fechas oficiales del semestre (inicio de clases, parciales, límites de reporte) |
| `entregas` / `documentos_entrega` | Los documentos que el docente sube por corte (listas de asistencia, notas firmadas, etc.) y su estado (pendiente/aprobado/rechazado) |
| `notificaciones` | La campanita de avisos in-app de los 4 roles |
| `repositorio_asignaturas` | Sílabos y programas de asignatura de cada materia |
| `aceptaciones_politica_tratamiento` | Registro de cada vez que un usuario acepta el Aviso de Privacidad |

Cómo se relacionan (simplificado):

```
roles ──< usuarios ──< asignaciones_academicas >── periodos_academicos
                              │
                              ├──< informes_corte >── cortes
                              │         │
                              │         └──< notas_estudiantes
                              │
usuarios ──< entregas >── periodos_academicos           usuarios ──< notificaciones
       │         │
       │         └──< documentos_entrega
       │
usuarios ──< repositorio_asignaturas          usuarios ──< aceptaciones_politica_tratamiento
```
(la flecha `──<` se lee "tiene muchos": un docente tiene muchas asignaciones,
una asignación tiene muchos informes, etc.)

### Cómo se conecta el código a la base de datos

- `db/database.py` lee la variable `DATABASE_URL` del archivo `.env` (host,
  puerto, usuario, contraseña, nombre de la base) y crea la conexión.
  `get_session()` abre una "sesión" de trabajo con la base de datos — como
  abrir una pestaña de conversación con la despensa.
- `db/repository.py` es donde viven **todas** las consultas (leer, guardar,
  actualizar, borrar) escritas una sola vez, para que nadie más en el
  proyecto tenga que escribir SQL a mano. Por ejemplo,
  `guardar_informe_corte(...)` guarda el resultado de procesar un PDF.
  Tanto el backend como Streamlit llaman a estas mismas funciones.

---

## 4. El backend (FastAPI): la cocina

El backend es un programa que queda corriendo, escuchando peticiones por
internet (en desarrollo, en `http://localhost:8000`). Es una **API** —
*Application Programming Interface*: un conjunto de "puertas" (llamadas
**endpoints**) que otros programas (como el frontend de React) pueden tocar
para pedir o enviar datos, usando el protocolo **HTTP** (el mismo que usa
cualquier página web).

### El recorrido de una petición, paso a paso

Cuando el navegador pide, por ejemplo, la lista de notificaciones:

1. **`backend/main.py`** es el punto de arranque: crea la aplicación FastAPI
   y le "conecta" cada grupo de endpoints (los **routers**, uno por tema:
   `auth`, `informes`, `docentes`, `entregas`, `notificaciones`, etc., cada
   uno en su propio archivo dentro de `backend/api/routers/`).
2. La petición llega a la ruta correspondiente, por ejemplo
   `GET /api/notificaciones` (definida en
   `backend/api/routers/notificaciones.py`).
3. Antes de ejecutar ese código, FastAPI corre las **dependencias**
   (`backend/api/deps.py`) declaradas en esa ruta:
   - `get_current_user`: lee el token JWT que viene en la petición (ver
     sección de autenticación más abajo) y busca al usuario dueño de ese
     token.
   - `requiere_roles("director", "secretario")` (cuando aplica): revisa que
     el rol del usuario esté en la lista permitida; si no, corta la petición
     con un error 403 (Prohibido) antes de tocar la base de datos.
   - `requiere_consentimiento`: revisa que el usuario ya haya aceptado el
     Aviso de Privacidad vigente; si no, también corta con 403. Esta
     dependencia se aplica a **todos los routers** excepto `auth` y
     `consentimiento` (ver `backend/main.py`), porque esos dos deben seguir
     funcionando incluso antes de aceptar.
4. Si todo lo anterior pasa, el código del endpoint llama a una función de
   `db/repository.py` para leer/escribir en la base de datos.
5. El resultado se convierte a JSON (un formato de texto estándar para
   intercambiar datos) usando un **schema** de Pydantic (carpeta
   `backend/schemas/`) — son "moldes" que definen exactamente qué campos
   debe tener la respuesta, y validan automáticamente los datos que llegan.
6. FastAPI devuelve esa respuesta al navegador.

```
Navegador ──HTTP──> main.py ──> router ──> deps.py (JWT, rol, consentimiento)
                                    │
                                    └──> db/repository.py ──> PostgreSQL
                                              │
                                    <── (dato) ──┘
                                    │
                              schema (JSON) ──HTTP──> Navegador
```

### Autenticación: cómo sabe el backend quién eres (JWT)

1. Cuando inicias sesión (`POST /api/auth/login` con usuario/contraseña),
   `db/auth.py` verifica la contraseña (guardada siempre **encriptada** con
   `bcrypt`, nunca en texto plano) contra la base de datos.
2. Si es correcta, `backend/core/security.py` genera un **token JWT** — una
   cadena de texto larga, firmada digitalmente, que dice "soy el usuario X,
   con el rol Y, válido hasta tal hora" sin que nadie pueda falsificarlo sin
   conocer la clave secreta del servidor (`JWT_SECRET_KEY` en `.env`).
3. Ese token se lo lleva el navegador y lo reenvía en **cada** petición
   siguiente (en la cabecera `Authorization: Bearer <token>`). Así el
   backend no tiene que recordar sesiones — cada petición trae su propia
   "credencial" verificable.

### Los "servicios": donde vive la lógica compartida más compleja

Algunos flujos son más largos que "leer/guardar un dato simple" — por
ejemplo, procesar un PDF de notas involucra leer el archivo, calcular
estadísticas, escribir un Excel Y guardar en la base de datos, todo en un
solo paso. Esa lógica no vive directamente en el router (para no repetirla),
sino en `backend/services/informe_service.py`, que a su vez llama al
**agente** (siguiente sección) y a `db/repository.py`.

---

## 5. El "agente" (`agente_notas/`): el chef especializado

Esta es la parte más "de negocio" del proyecto — las reglas particulares del
formato de la Universidad (`MI-DO-FO16`, el "Formato de Gestión y
Autoevaluación Docente"). Vive separada del backend y de Streamlit a
propósito, para que **ambas interfaces usen exactamente el mismo cálculo**.

### `agente_notas/core.py` — el corazón

- **`leer_pdf_notas(pdf)`**: abre el PDF que el docente descarga de
  Academusoft (el sistema académico de la Universidad) con la librería
  `pdfplumber`, y usa una expresión regular (un patrón de texto,
  `FILA_PATRON`) para reconocer cada fila de estudiante: documento, nombre,
  nota de Corte 1, Corte 2, Corte 3 (si existe), y el acumulado ponderado que
  ya trae el PDF.
- **`leer_asistencia_excel(...)`**: lee una planilla de asistencia semana a
  semana y cuenta cuántos estudiantes tuvieron asistencia perfecta (0
  faltas) — el valor de "Asistencia regular", que el PDF de Academusoft no
  trae.
- **`analizar_progreso(estudiante, corte)`**: el cálculo académico central.
  Con los pesos reales del acuerdo pedagógico (Corte 1 = 30%, Corte 2 = 30%,
  Corte 3 = 40%), calcula:
  - el acumulado ponderado real que el estudiante ya tiene asegurado
    (`Def. Pond`);
  - si aún faltan cortes por calificar, la nota que le falta sacar en lo
    que resta para llegar a 60 puntos (`nota_necesaria`);
  - un estado: `asegurado` (ya no puede perder aunque saque 0 en lo que
    falta), `en_riesgo` (todavía puede ganar o perder), `matematicamente_
    reprobado` (ya no puede llegar a 60 ni sacando 100), o — en Corte 3 —
    simplemente `aprobado`/`reprobado`, definitivo.
- **`calcular_resumen(...)`**: junta todo lo anterior en los 4 números que
  pide el formato oficial: Matriculados, Asistencia regular, Evaluados,
  Aprobaron.
- **`escribir_bloque(...)` / `escribir_en_excel(...)`**: localiza el bloque
  de esa materia dentro de la plantilla Excel oficial (buscando el nombre en
  la hoja "INFORME FINAL") y escribe esos 4 valores en las celdas exactas —
  dejando intactas las fórmulas que ya trae el Excel (Inasistencia,
  Reprobados, los dos porcentajes se recalculan solas).

### `agente_notas/estadisticas.py`

Calcula las estadísticas adicionales que se muestran en los dashboards:
promedio, mediana, desviación estándar, coeficiente de variación, quién sacó
la mejor nota, y arma la interpretación en texto ("el grupo tiene un
rendimiento parejo/disperso...").

### `agente_notas/almacenamiento.py`, `notificaciones.py`, `reporte_pdf.py`, `aviso_privacidad.py`

- **`almacenamiento.py`**: guarda en disco (no en la base de datos, los
  archivos serían demasiado pesados para eso) los documentos que suben los
  docentes (entregas, sílabos), en carpetas organizadas por
  periodo/docente/corte. Solo la **ruta** del archivo y sus metadatos
  (nombre, tamaño, fecha) quedan en la base de datos. Incluye una función de
  seguridad (`ruta_absoluta_segura`) que verifica que ninguna ruta guardada
  pueda "escaparse" fuera de las carpetas permitidas — una protección contra
  ataques de manipulación de rutas.
- **`notificaciones.py`**: envío de correos (cuando el SMTP institucional
  esté configurado) al aprobar/rechazar una entrega.
- **`reporte_pdf.py`**: genera el informe PDF de gestión docente (el que se
  descarga desde la vista de Dirección).
- **`aviso_privacidad.py`**: el texto legal del Aviso de Privacidad y la
  función `acepto_politica_vigente()` que usan tanto el backend como
  Streamlit para decidir si hay que bloquear al usuario hasta que acepte.

---

## 6. El frontend (React): el salón

React es una librería de JavaScript para construir interfaces que reaccionan
a los datos sin recargar la página completa (por eso "React"). Este proyecto
es una **SPA** (*Single Page Application*, aplicación de una sola página): el
navegador carga una sola vez un HTML casi vacío, y React se encarga de ir
mostrando distintas pantallas dentro de él.

### Punto de entrada: `frontend/src/main.tsx`

Es lo primero que se ejecuta. Envuelve toda la aplicación en:
- `BrowserRouter`: habilita la navegación entre "páginas" sin recargar el
  navegador.
- `AuthProvider`: hace disponible, en cualquier parte de la app, quién es el
  usuario logueado (ver más abajo).

### `App.tsx`: el enrutador

Decide qué página mostrar según la URL y el rol del usuario logueado:
`DocentePage`, `DireccionPage` (Director/Secretario Académico), o
`SecretariaProgramaPage`. `ProtectedRoute` es el guardia que redirige a
`/login` si no hay sesión iniciada.

### `context/AuthContext.tsx`: quién soy y mi sesión

Guarda el token JWT y los datos del usuario en `localStorage` (memoria
persistente del navegador) para que la sesión sobreviva si recargas la
página. Expone `login()`, `logout()` y el objeto `usuario` a toda la app.

### `api/client.ts`: el "cartero" hacia el backend

Configura `axios` (la librería que hace las peticiones HTTP) para que:
- **Siempre** agregue el token JWT guardado a cada petición
  (`Authorization: Bearer <token>`) — así el usuario no tiene que
  "reautenticarse" en cada clic.
- Si el backend responde `401` (sesión inválida o expirada), borra la
  sesión guardada y manda al usuario de vuelta al login automáticamente.

### `pages/` y `components/`

- **`pages/`**: una por rol (`DocentePage`, `DireccionPage`,
  `SecretariaProgramaPage`) y el login. Son las que arman qué componentes
  mostrar y en qué orden.
- **`components/`**: piezas reutilizables, cada una dueña de su propio
  pedazo de lógica y de sus propias llamadas a la API — por ejemplo,
  `CalendarioAcademico.tsx` pide y muestra el calendario, sin que la página
  que lo contiene necesite saber cómo funciona por dentro.
- **`components/ui/`**: piezas puramente visuales y genéricas (`Spinner`,
  `EstadoVacio`, `SeccionNav`), sin lógica de negocio — se usan en varias
  partes de la app tal cual.

### Cómo fluye una acción en React (ejemplo real)

Cuando el Director hace clic en "Generar informe de todos los docentes"
(`DireccionPage.tsx`):
1. Se llama `api.get("/reportes/consolidado", { responseType: "blob", params: ... })`.
2. `axios` agrega el token JWT automáticamente (paso invisible, gracias al
   interceptor de `client.ts`) y hace la petición HTTP real al backend.
3. El backend valida el token y el rol, genera el PDF (usando
   `agente_notas/reporte_pdf.py`) y lo devuelve como archivo binario.
4. React recibe ese archivo, crea una URL temporal en el navegador
   (`URL.createObjectURL`) y dispara la descarga — sin que la página se
   recargue en ningún momento.

### Producción vs. desarrollo

En desarrollo (`npm run dev`), Vite (la herramienta que compila y sirve el
código de React) corre su propio servidor en el puerto `5173` y redirige
`/api` hacia el backend en el `8000` (configurado en `frontend/vite.config.ts`).
En producción, `npm run build` genera archivos estáticos que Nginx sirve
directamente (ver `docs/DESPLIEGUE_VPS.md`).

---

## 7. Un recorrido completo, de punta a punta

Para atar todo, así es el camino real cuando **un docente sube un PDF de
notas** desde React:

```
1. React (DocentePage.tsx)
   El docente selecciona el corte, sube el Excel de plantilla y los PDF.
   axios.post("/api/informes/procesar", formData)  --con el token JWT--

2. backend/api/routers/informes.py  →  procesar()
   FastAPI recibe los archivos. Las dependencias verifican: ¿token válido?
   ¿rol "docente"? ¿aceptó el Aviso de Privacidad?

3. backend/services/informe_service.py  →  procesar_materias()
   Llama al agente:
     agente_notas.core.leer_pdf_notas()      -> extrae estudiantes del PDF
     agente_notas.core.calcular_resumen()    -> Matriculados/Evaluados/Aprobaron
     agente_notas.core.escribir_bloque()     -> escribe el Excel de salida
     agente_notas.estadisticas.*             -> promedio, mediana, interpretación

4. db/repository.py
   obtener_o_crear_asignacion()   -> guarda/reutiliza la materia del docente
   guardar_informe_corte()        -> INSERT/UPDATE en informes_corte + notas_estudiantes

5. PostgreSQL (contenedor Docker)
   Los datos quedan guardados de forma permanente.

6. La respuesta (JSON + el Excel en base64) vuelve por el mismo camino
   hasta React, que muestra los resultados y ofrece el botón de descarga.
```

Si el mismo docente hiciera esto **desde Streamlit** en vez de React, el
camino sería mucho más corto: `vistas/docente.py` llamaría **directamente**
a `informe_service` (o a las mismas funciones de `agente_notas`/
`db.repository`) sin pasar por HTTP ni por JWT — pero el resultado guardado
en PostgreSQL sería idéntico, porque es la misma lógica de fondo.

---

## 8. Streamlit: el segundo salón

Streamlit (`app.py` + `vistas/`) es la interfaz alternativa. La diferencia
clave frente a React/FastAPI:

- **No hay una API HTTP en el medio.** Cada archivo de `vistas/` importa y
  llama directamente a `db/repository.py` y a `agente_notas/*` — todo corre
  en un solo proceso de Python.
- **No hay JWT.** La sesión se guarda en `st.session_state` (una memoria
  propia de Streamlit, atada a esa pestaña del navegador).
- **Modelo de "rerun completo"**: cada clic o cambio de un campo hace que
  Streamlit vuelva a ejecutar el archivo de arriba a abajo y redibuje toda la
  pantalla — muy distinto al modelo de React, que solo actualiza lo que
  cambió.

El detalle completo de arquitectura y pasos para ejecutarlo está en
`docs/ejecucionStreamlit.md`; el de React en `docs/ejecuciónReact.md`.

---

## 9. Glosario rápido

| Término | Qué significa aquí |
|---|---|
| **API** | Conjunto de "puertas" (endpoints) que un programa expone para que otros programas le pidan o envíen datos |
| **Endpoint** | Una URL específica de la API que hace una sola cosa (p. ej. `POST /api/auth/login`) |
| **Backend** | El programa que corre en el servidor, con la lógica y el acceso a la base de datos |
| **Frontend** | El programa que corre en el navegador del usuario, la interfaz visual |
| **ORM** | Una librería (SQLAlchemy) que traduce clases de Python a tablas SQL, para no escribir SQL a mano |
| **JWT** | Un token firmado digitalmente que prueba quién eres y qué rol tienes, sin que el servidor tenga que "recordarte" |
| **RBAC** | *Role-Based Access Control*: controlar qué puede hacer cada quien según su rol |
| **Contenedor (Docker)** | Un entorno aislado y reproducible donde corre un programa (aquí, PostgreSQL) |
| **SPA** | *Single Page Application*: una app web que no recarga la página completa al navegar |
| **Schema (Pydantic)** | Un "molde" que define y valida qué forma deben tener los datos que entran o salen de la API |
| **Migración** | Un script que actualiza la estructura de la base de datos (agregar una columna, una tabla nueva) sin borrar lo que ya existía |
| **`.env`** | Archivo con las credenciales/configuración secreta de esta máquina (nunca se sube a GitHub) |

---

## 10. ¿Por dónde seguir leyendo?

- `docs/ejecuciónReact.md` — cómo levantar React + backend, paso a paso.
- `docs/ejecucionStreamlit.md` — cómo levantar Streamlit, paso a paso.
- `docs/DESPLIEGUE_VPS.md` — cómo publicar todo esto en un servidor real.
- `README.md` (raíz del proyecto) — resumen general y decisiones de diseño.
