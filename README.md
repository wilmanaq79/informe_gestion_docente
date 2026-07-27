# Sistema de Gestión y Autoevaluación Docente (MI-DO-FO16)
### Programa de Ingeniería de Sistemas — Universidad del Pacífico

Sistema multiusuario (300 docentes + 20 Directores de Programa + 20
Secretarios Académicos) que lee los PDF de notas (reporte "Ver
Calificaciones" de Academusoft) y, opcionalmente, planillas de asistencia
por semanas, para calcular automáticamente **Matriculados, Asistencia
regular, Evaluados y Aprobaron** de cada materia, escribirlos en el Excel
oficial del formato de gestión docente, y guardarlos en una base de datos
PostgreSQL normalizada para que Dirección y Secretaría Académica puedan
consultar un dashboard institucional y generar informes PDF (por docente o
consolidado de todos).

Los campos **Inasistencia, Reprobados y los dos porcentajes** ya son fórmulas
del Excel: el agente nunca los sobrescribe, solo los 4 valores base.

## Arquitectura

El proyecto tiene **dos frontends que comparten la misma lógica de negocio y
la misma base de datos** (`db/` y `agente_notas/`):

| | Uso recomendado |
|---|---|
| **Streamlit** (`app.py`) | Uso individual/rápido en un solo equipo, sin instalar Node.js. |
| **API (FastAPI) + Frontend (React)** | Uso real de producción con muchos usuarios concurrentes (100 docentes conectados a la vez, 340 cuentas en total). Es la arquitectura recomendada para esa escala. |

```
informe_de_gestion/
├── app.py                     # Punto de entrada Streamlit
├── agente_llenado_notas.py    # CLI (una materia a la vez, sin base de datos)
├── requirements.txt           # Dependencias de Python (Streamlit + backend + agente)
├── docker-compose.yml         # Postgres + pgAdmin
├── .env                       # DATABASE_URL, JWT_SECRET_KEY, etc. (NO se versiona)
│
├── vistas/                    # Paginas de Streamlit (una por rol)
│   ├── login.py
│   ├── docente.py
│   └── direccion.py
│
├── backend/                    # API REST (FastAPI) -- arquitectura nueva
│   ├── main.py                   # Ensambla la app, CORS, routers
│   ├── core/
│   │   ├── config.py               # Settings (.env) -- JWT, CORS, periodo actual
│   │   └── security.py             # Emision/verificacion de JWT
│   ├── api/
│   │   ├── deps.py                  # get_db, get_current_user, requiere_roles(...)
│   │   └── routers/
│   │       ├── auth.py               # POST /api/auth/login, GET /api/auth/me
│   │       ├── informes.py           # Carga/procesamiento de notas (rol docente)
│   │       ├── docentes.py           # Resumen/detalle de docentes (director/secretario)
│   │       ├── usuarios.py           # Alta y listado de usuarios (director/secretario)
│   │       ├── reportes.py           # Informe PDF individual y consolidado
│   │       └── dashboard.py          # Agregados institucionales (director/secretario)
│   ├── schemas/                 # Contratos Pydantic (request/response)
│   └── services/
│       └── informe_service.py     # Orquesta agente_notas + db.repository para la API
│
├── frontend/                    # SPA en React + Vite + TypeScript -- arquitectura nueva
│   ├── src/
│   │   ├── api/client.ts           # Cliente axios (adjunta el JWT, maneja 401)
│   │   ├── context/AuthContext.tsx # Estado de sesion (localStorage)
│   │   ├── pages/                  # LoginPage, DocentePage, DireccionPage
│   │   └── components/
│   │       ├── Header.tsx            # Branding institucional
│   │       ├── DashboardInstitucional.tsx
│   │       └── charts/                # Graficas (Recharts)
│   └── package.json
│
├── agente_notas/               # Logica de dominio (compartida por ambos frontends)
│   ├── core.py                  # Lectura de PDF/asistencia, calculo y escritura en Excel
│   ├── estadisticas.py           # Calculos para el dashboard (promedios, dispersion, ranking)
│   └── reporte_pdf.py            # Informe PDF individual y consolidado (reportlab)
│
├── db/                         # Capa de datos (PostgreSQL vía SQLAlchemy, compartida)
│   ├── models.py                 # Modelos ORM (marco de referencia normalizado)
│   ├── database.py               # Motor/sesion (pool configurable por entorno)
│   ├── repository.py              # Funciones de acceso a datos y agregaciones
│   ├── auth.py                    # Hash/verificacion de contrasenas, login
│   ├── seed.py                    # Crea tablas + siembra roles/cortes/cuenta inicial
│   └── schema.sql                 # DDL de referencia (documentacion, generado con pg_dump)
│
├── assets/                     # Branding institucional (escudo UNPA, logo del programa)
├── scripts/                    # Utilidades de soporte (recalculo de Excel, datos de ejemplo)
├── tests/                      # Smoke test de la API
├── ejemplos/                   # Datos de prueba (no reales)
└── documentos/                  # Tus archivos reales de gestión docente (no versionados)
```

## Base de datos

PostgreSQL 16 en Docker (`postgres_db`, puerto 5432) + pgAdmin (`pgadmin_ui`,
puerto 8080). Ver `docker-compose.yml`.

**Modelo normalizado** (marco de referencia — ver `db/models.py` y
`db/schema.sql`):

- `roles`, `cortes`, `periodos_academicos` — catálogos de referencia.
- `usuarios` — los docentes, directores y secretarios, con rol y contraseña
  (hash bcrypt).
- `asignaciones_academicas` — qué materia/grupo dicta cada docente en cada
  periodo.
- `informes_corte` — Matriculados/Asistencia/Evaluados/Aprobados/promedio/
  desviación por asignación y corte (upsert: reprocesar un corte lo
  actualiza, no lo duplica).
- `notas_estudiantes` — detalle por estudiante (Corte 1/2/3, Def. Pond, nota
  necesaria, estado) que respalda cada informe.

### Primer arranque (una sola vez, para ambos frontends)

```bash
docker compose up -d          # si los contenedores no existen aun
python -m db.seed             # crea las tablas y siembra roles/cortes/cuenta inicial
```

Esto imprime una cuenta inicial (`admin` / contraseña temporal) con rol
**director**. Con ella entras la primera vez y, desde "Administración de
usuarios", creas las cuentas reales de los Directores, los Secretarios
Académicos y los docentes.

## Instalación

```bash
pip install -r requirements.txt
```

---

## Opción A — Streamlit (uso individual, sin Node.js)

```bash
streamlit run app.py
```

**Rol docente:**
1. Elige el corte (Corte 1, Corte 2 o Corte 3/Final).
2. Sube la plantilla Excel y uno o varios PDF de notas (uno por materia).
3. Confirma la materia de cada PDF y sube (opcional) su planilla de
   asistencia de ese corte.
4. Presiona **"Procesar todas las materias y generar un solo Excel"**:
   genera el Excel y guarda el informe en la base de datos.
5. Revisa el **dashboard de rendimiento** (promedios, dispersión, ranking,
   interpretación automática, proyección de aprobación).

**Rol director / secretario:**
1. Ve el **dashboard institucional** (KPIs de todo el programa, promedio por
   asignatura, comparación por docente, evolución por corte, proyección de
   riesgo agregada).
2. Ve el resumen de todos los docentes y entra al detalle de uno por corte.
3. Genera y descarga su **informe PDF** individual.
4. (Solo Director) Genera el **informe PDF consolidado de todos los
   docentes** en un clic.
5. Administra usuarios (altas de docentes, directores, secretarios) y borra
   informes (solo Director).

---

## Opción B — API (FastAPI) + Frontend (React) — recomendada para producción

Requiere además **Node.js 18+** para el frontend.

### 1. Backend

```bash
# Desarrollo (recarga automatica, un solo proceso):
uvicorn backend.main:app --reload --port 8000

# Produccion (varios workers, sin recarga -- ver "Escalamiento" mas abajo):
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Documentación interactiva de la API: `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend
npm install

# Desarrollo:
npm run dev              # http://localhost:5173 (proxy /api -> localhost:8000)

# Produccion:
npm run build            # genera frontend/dist -- sirvelo con nginx/Caddy/etc.
```

El flujo de uso (login, carga de notas, dashboard, informes PDF,
administración de usuarios) es el mismo que en Streamlit — es la misma
lógica de negocio, solo que separada en API + SPA.

---

## Escalamiento (100 docentes concurrentes, 340 cuentas en total)

La arquitectura API + React es la pensada para este volumen. Puntos a
ajustar cuando se despliegue así:

1. **Backend con varios workers**, no `--reload`:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```
   Cada worker es un proceso independiente con su propio pool de conexiones
   a la base de datos.

2. **Pool de conexiones** (`db/database.py`, configurable por variables de
   entorno `DB_POOL_SIZE` / `DB_MAX_OVERFLOW`, por defecto 10/10 = 20
   conexiones máx. por worker). Con **W** workers, el máximo teórico de
   conexiones simultáneas es `W × (DB_POOL_SIZE + DB_MAX_OVERFLOW)`. Con 4
   workers y los valores por defecto: `4 × 20 = 80` conexiones — deja
   margen frente al `max_connections` de Postgres (ver punto siguiente).

3. **`max_connections` de PostgreSQL**: el contenedor ya viene configurado
   en `docker-compose.yml` con `max_connections=200` (el valor por defecto
   de Postgres, 100, se queda corto en cuanto el backend corre con varios
   workers). Si el contenedor de Postgres **ya existe** (creado antes de
   este cambio), hay que aplicarlo a mano:
   ```sql
   ALTER SYSTEM SET max_connections = 200;
   ```
   y reiniciar el contenedor (`docker restart postgres_db`) para que tome
   efecto — un `ALTER SYSTEM` de este parámetro no aplica en caliente.

4. **Frontend**: en producción, `npm run build` + servir `frontend/dist`
   con un servidor de archivos estáticos (nginx, Caddy, o un CDN) — el
   servidor de desarrollo de Vite (`npm run dev`) no está pensado para
   tráfico real de muchos usuarios a la vez.

5. **CORS**: agregar el dominio real donde quede publicado el frontend a
   `CORS_ORIGINS` en `backend/core/config.py` (o por variable de entorno),
   además de `localhost:5173` usado en desarrollo.

6. **Altas masivas de cuentas**: con 340 cuentas (300 docentes + 20
   directores + 20 secretarios), crearlas una por una desde "Administración
   de usuarios" es viable pero tedioso. Si se necesita crear varias de
   golpe, lo más práctico hoy es un pequeño script en `scripts/` que llame
   a `db.repository.crear_usuario` en bucle a partir de un CSV
   (nombre, cédula, correo, usuario, contraseña temporal, rol) — no
   implementado todavía; ver "Roadmap".

## Uso — línea de comandos (una materia, sin base de datos)

```bash
python agente_llenado_notas.py \
    --pdf ejemplos/Notas_sistemas_opertivo_corte_2.pdf \
    --excel "documentos/MI-DO-FO16 Formato Gestión y Autoevaluación Docente-....xlsx" \
    --out salida.xlsx \
    --corte 2 \
    --asistencia-excel ejemplos/Asistencia_sistemas_operativo_corte_2_PRUEBA.xlsx
```

Después de generar el archivo, recalcula sus fórmulas con:

```bash
python scripts/recalc_excel_com.py salida.xlsx
```

(Requiere Microsoft Excel instalado; es la alternativa a LibreOffice en
Windows, que no está disponible en todos los equipos.)

## Pruebas

```bash
# Smoke test de la API (requiere el backend corriendo y un docente/director
# de prueba ya creados -- ver tests/test_api_smoke.py para los detalles):
python tests/test_api_smoke.py
```

## Reglas de negocio

Ver la pestaña **INSTRUCTIVO** de la propia plantilla, y los docstrings de
`agente_notas/core.py`:

- **Matriculados**: número de estudiantes en el PDF.
- **Asistencia regular**: estudiantes con 0 faltas en el corte (100% de
  asistencia). No viene en el PDF de notas — se toma de una planilla de
  asistencia por semanas (columnas `Semana 1`…`Semana N`, valores `P`/`A`).
- **Evaluados**: estudiantes con al menos una nota registrada en los cortes
  ya corridos.
- **Aprobaron**: nota definitiva ≥ 60.
  - Corte 3 / Final: cálculo exacto con los 3 cortes.
  - Corte 1 o 2: **estimación** proyectando el acumulado sobre 100 puntos
    (se marca con un comentario en la celda de Excel / en el PDF).
- **Def. Pond / Nota necesaria**: acumulado ponderado real (Corte 1 = 30%,
  Corte 2 = 30%, Corte 3 = 40%) y lo que falta para llegar a 60, con estado
  (asegurado / en riesgo / matemáticamente reprobado / aprobó / reprobó).

## Roles y permisos

| Acción | Docente | Secretario | Director |
|---|---|---|---|
| Cargar notas y generar su propio Excel | ✅ | — | — |
| Ver dashboard institucional | — | ✅ | ✅ |
| Ver/descargar informe PDF de un docente | — | ✅ | ✅ |
| Generar informe PDF **consolidado** de todos | — | — | ✅ |
| Administrar usuarios (crear cuentas) | — | ✅ | ✅ |
| **Borrar** un informe cargado | — | — | ✅ |

## Roadmap

- [x] API backend (FastAPI) reutilizando `db/` y `agente_notas/`.
- [x] Frontend React consumiendo la API (Streamlit se mantiene en paralelo).
- [x] Dashboard institucional agregado (director/secretario).
- [x] Informe PDF consolidado de todos los docentes (solo director).
- [ ] Alta masiva de usuarios desde un CSV (para las 340 cuentas iniciales).
- [ ] Despliegue de referencia (nginx/Caddy + systemd o Docker para el
      backend con varios workers) para el entorno de 100 docentes
      concurrentes.
