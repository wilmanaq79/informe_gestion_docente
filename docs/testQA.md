# Cómo ejecutar las pruebas (QA)

Este proyecto tiene dos suites de pruebas automatizadas, independientes entre sí:

1. **Backend / lógica de negocio / base de datos** — `pytest` (Python).
2. **Frontend React** — `vitest` (TypeScript).

Ambas quedan guardadas en el repositorio y se pueden volver a ejecutar en cualquier momento, tantas veces como quieras. Ninguna de las dos modifica datos reales: la suite de backend usa transacciones que siempre se revierten (más detalle en la sección 3.2).

---

## 1. Requisitos previos

Antes de correr cualquier prueba, verifica que tienes esto listo (es lo mismo que ya usas para trabajar en el proyecto normalmente):

- El entorno virtual de Python creado e instalado con `requirements.txt` (incluye `pytest`).
- El archivo `.env` en la raíz del proyecto, con `DATABASE_URL` apuntando a tu Postgres de desarrollo (el mismo que usa la app).
- **PostgreSQL corriendo** (el contenedor Docker, o el servicio que estés usando). Las pruebas de backend sí necesitan la base de datos real disponible — varias de ellas (las de ACID y las del agente de entregas) abren conexiones de verdad contra Postgres, aunque después revierten todo.
- Para las pruebas de frontend: Node.js y las dependencias de `frontend/` instaladas (`npm install` dentro de `frontend/`).

**No hace falta** tener el backend (`uvicorn`) ni el frontend (`vite`/Streamlit) corriendo para ejecutar las pruebas — se conectan directo a la base de datos o prueban funciones aisladas, no pasan por la API HTTP ni por un navegador real. La única excepción es `tests/test_api_smoke.py`, que se explica aparte en la sección 5 porque es un caso distinto (una prueba manual, no parte de la suite automática).

---

## 2. Pruebas de backend (pytest)

### 2.1 Cómo ejecutarlas

Desde la **raíz del proyecto** (`E:\informe_de_gestion`), con el entorno virtual activado:

```bash
python -m pytest
```

En Windows, si no tienes el venv activado en la terminal, usa la ruta completa al ejecutable en vez de `python`:

```bash
.venv/Scripts/python.exe -m pytest
```

Esto descubre y corre automáticamente todos los archivos `tests/test_*.py` (la configuración está en `pytest.ini`, en la raíz — ahí se define `testpaths = tests` y `pythonpath = .` para que las importaciones tipo `from db.database import get_session` funcionen sin configurar nada más).

Al terminar, deberías ver algo como:

```
......................................................................
67 passed, 44 warnings in 7.46s
```

Los "warnings" son avisos de que `datetime.utcnow()` está deprecado en versiones nuevas de Python (no son errores, no afectan el resultado de las pruebas — es una limpieza de código pendiente, no algo urgente).

### 2.2 Comandos útiles para el día a día

**Correr solo un archivo de pruebas:**
```bash
python -m pytest tests/test_agente_firmas.py
```

**Correr solo una clase o una prueba específica dentro de un archivo:**
```bash
python -m pytest tests/test_acid.py::TestAtomicidad
python -m pytest tests/test_acid.py::TestAtomicidad::test_lote_de_materias_no_deja_estado_parcial_si_una_falla
```

**Ver más detalle de cada prueba (nombre uno por uno, no solo un punto por prueba):**
```bash
python -m pytest -v
```

**Detenerse en la primera prueba que falle** (útil cuando estás arreglando algo y no quieres ver 20 fallos repetidos del mismo problema):
```bash
python -m pytest -x
```

**Ver el `print()` que haya dentro de una prueba** (por defecto pytest los oculta si la prueba pasa):
```bash
python -m pytest -s
```

**Buscar pruebas por nombre** (coincidencia parcial, sin tener que escribir la ruta completa):
```bash
python -m pytest -k "firma"        # corre todas las que tengan "firma" en el nombre
python -m pytest -k "not lento"    # corre todas MENOS las que tengan "lento" en el nombre
```

### 2.3 Qué prueba cada archivo

| Archivo | Qué verifica | ¿Toca la base de datos real? |
|---|---|---|
| `tests/conftest.py` | No es una prueba en sí — define la fixture `db_session` que usan las demás (ver 3.2 abajo). | — |
| `tests/test_agente_firmas.py` | El agente que detecta si un docente firmó un documento (PDF/Excel): los distintos niveles de confianza, que "firma" no se confunda con "confirma", que un nombre de pila común no dispare un falso positivo, el campo "Docente: \_\_\_\_" sin la palabra "firma". | No — genera los PDF/Excel de prueba en memoria. |
| `tests/test_auth.py` | Que las contraseñas se guarden hasheadas (bcrypt) y nunca en texto plano, y que los tokens JWT se emitan/decodifiquen correctamente (y que uno manipulado falle). | No |
| `tests/test_rate_limit.py` | El bloqueo de intentos de login: que se bloquee al 5.º intento fallido, que usuarios distintos no se mezclen entre sí, y que el bloqueo expire pasada la ventana de 15 minutos. | No |
| `tests/test_almacenamiento.py` | Que solo se acepten archivos `.pdf/.xlsx/.jpg/.jpeg/.png`, que se rechacen archivos más pesados de 15 MB, que un nombre de archivo con `../../` no pueda escapar la carpeta de almacenamiento, y que solo pdf/imagen se muestren "inline" (lo demás se fuerza a descarga). | No |
| `tests/test_deps_rbac.py` | La función que verifica el rol del usuario en cada endpoint del backend (`requiere_roles`). | No |
| `tests/test_acid.py` | Las 4 propiedades ACID contra Postgres real: atomicidad, consistencia, aislamiento y durabilidad (ver detalle en la sección 3). | **Sí**, real |
| `tests/test_entregas_gate.py` | Que no se pueda confirmar la revisión de un documento sin haberlo abierto antes, y que no se pueda aprobar una entrega sin confirmar todos los documentos que lo necesitan. | **Sí**, real |

---

## 3. Cómo funcionan las pruebas que usan la base de datos real

### 3.1 Por qué es seguro correrlas contra tu base de datos de desarrollo

La mayoría de las pruebas (`test_acid.py`, `test_entregas_gate.py`) usan una fixture llamada `db_session`, definida en `tests/conftest.py`. Funciona así:

1. Abre una conexión nueva a Postgres.
2. Empieza una transacción.
3. Le entrega esa sesión a la prueba.
4. Cuando la prueba termina (haya pasado o fallado), **revierte la transacción completa** y cierra la conexión.

Lo importante: aunque el código bajo prueba llame `session.commit()` por dentro (por ejemplo, `crear_usuario()` o `aprobar_entrega()` normalmente hacen su propio commit), ese commit **no llega a confirmarse de verdad** — SQLAlchemy lo convierte en un punto de guardado (`SAVEPOINT`) dentro de la transacción externa, que se descarta entera al final. Por eso puedes correr `test_acid.py` y `test_entregas_gate.py` cuantas veces quieras sin preocuparte de ensuciar tu base de datos: nunca queda nada.

Los usuarios/entregas que se crean durante estas pruebas usan nombres con el prefijo `__pytest_...` para que sean fáciles de identificar si alguna vez necesitas revisarlos manualmente mientras una prueba está corriendo (con un cliente de BD conectado en paralelo, por ejemplo) — pero al terminar la prueba, desaparecen solos.

### 3.2 La excepción: aislamiento y durabilidad

Dos pruebas dentro de `test_acid.py` **no** usan la fixture `db_session`, a propósito:

- `TestAislamiento`: necesita **dos conexiones genuinamente distintas** a la vez (para probar que lo que una no ha confirmado, la otra no lo ve). Usa `engine.connect()` directamente, revierte su propia transacción al final.
- `TestDurabilidad`: necesita probar que un commit **real** sobrevive incluso cerrando la sesión y reconectando desde cero — así que sí hace un commit de verdad. Esta prueba es la única que borra explícitamente su propio dato de prueba al final (`DELETE ... WHERE username = ...` + commit), como red de seguridad.

Si alguna vez interrumpes la ejecución de pytest a la fuerza (Ctrl+C) justo durante estas dos pruebas específicas, es buena idea revisar manualmente que no haya quedado un usuario `__pytest_aislamiento_...` o `__pytest_durabilidad_...` colgado, y borrarlo si es así. En el resto de las pruebas (las que sí usan `db_session`) esto no puede pasar, porque el rollback ocurre incluso si la prueba se interrumpe con una excepción.

---

## 4. Pruebas de frontend (vitest)

### 4.1 Cómo ejecutarlas

Desde la carpeta `frontend/`:

```bash
cd frontend
npm test
```

Esto corre `vitest run` (definido en `package.json`), que ejecuta toda la suite una vez y termina — a diferencia del modo por defecto de vitest, que se queda escuchando cambios.

Deberías ver:

```
 Test Files  3 passed (3)
      Tests  13 passed (13)
```

### 4.2 Modo "watch" (recomendado mientras editas código)

Si estás modificando componentes y quieres que las pruebas se vuelvan a correr solas cada vez que guardas un archivo:

```bash
cd frontend
npx vitest
```

(sin el `run` al final). Déjalo corriendo en una terminal aparte mientras trabajas.

### 4.3 Correr solo un archivo

```bash
cd frontend
npx vitest run src/api/client.test.ts
```

### 4.4 Qué prueba cada archivo

| Archivo | Qué verifica |
|---|---|
| `src/test/setup.ts` | Configuración compartida (no es una prueba) — carga los matchers de `@testing-library/jest-dom` (`toBeInTheDocument()`, etc.). |
| `src/api/client.test.ts` | La función `mensajeError()`, que decide qué mensaje de error mostrarle al usuario cuando falla una llamada a la API. |
| `src/components/ui/EstadoVacio.test.tsx` | Que el componente de "no hay nada que mostrar" renderice el texto y el ícono correctos. |
| `src/components/EntregasDocumentos.test.ts` | La misma lógica de bloqueo de aprobación que se prueba en Python (`test_entregas_gate.py`), pero del lado del cliente: qué documentos necesitan revisión manual y cuáles bloquean el botón "Aprobar entrega". |

### 4.5 Requisito de instalación (solo la primera vez, o si `node_modules` no existe)

```bash
cd frontend
npm install
```

Esto instala tanto las dependencias normales de la app como las de prueba (`vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`), que ya están declaradas en `package.json`.

---

## 5. La prueba de humo manual (`tests/test_api_smoke.py`) — un caso aparte

Este archivo es distinto a todos los anteriores: **no** es parte de la suite automática de pytest en el sentido normal (aunque pytest también puede descubrirlo y correrlo). Es un script que simula un flujo completo de un docente real usando la API HTTP de verdad, así que **sí necesita**:

- El backend corriendo: `uvicorn backend.main:app --reload --port 8000`
- Usuarios de prueba ya existentes en la base de datos (`wquinonez`/`docente123` y `admin`/`cambiar123`, ver `db/seed.py`)
- Los archivos de ejemplo reales en `documentos/` y `ejemplos/` (no se generan solos como en las demás pruebas)

Se ejecuta aparte, no con `python -m pytest` sino directamente:

```bash
python tests/test_api_smoke.py
```

Si esos usuarios/archivos de ejemplo no existen en tu máquina, este script fallará — es esperado, no significa que algo esté roto en el código. Para el día a día de "¿mis cambios rompieron algo?", la suite de pytest (sección 2) es la que debes correr; esta prueba de humo es más bien para una verificación manual puntual end-to-end cuando quieras confirmar que el flujo completo funciona con el servidor real levantado.

---

## 6. Resumen rápido — los dos comandos que más vas a usar

```bash
# Backend: desde la raíz del proyecto, con la BD de desarrollo disponible
python -m pytest

# Frontend: desde la carpeta frontend/
cd frontend && npm test
```

Si ambos terminan en verde ("X passed", sin ningún "failed"), tus cambios no rompieron nada de lo que ya está cubierto por pruebas.

---

## 7. Si algo falla

- **`ModuleNotFoundError` al correr pytest**: seguramente no estás usando el Python del entorno virtual del proyecto. Usa `.venv/Scripts/python.exe -m pytest` en vez de `python -m pytest`.
- **Errores de conexión a la base de datos** (`OperationalError`, `could not connect`): verifica que Postgres esté corriendo y que `DATABASE_URL` en `.env` sea correcto — las pruebas de `test_acid.py` y `test_entregas_gate.py` necesitan la base de datos real disponible.
- **Falla justo una prueba después de cambiar algo en `db/repository.py` o `agente_notas/agente_firmas.py`**: es la suite haciendo su trabajo — antes de asumir que la prueba está mal, revisa si tu cambio alteró un comportamiento que la prueba documenta a propósito (por ejemplo, si cambias la exigencia de "2 partes del nombre" en el agente de firmas a "1 parte", `test_agente_firmas.py` te lo va a señalar).
- **`npm test` no encuentra ningún archivo**: confirma que estás parado dentro de la carpeta `frontend/`, no en la raíz del proyecto.
