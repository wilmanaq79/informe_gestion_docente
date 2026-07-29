# Cómo ejecutar el proyecto con Streamlit

Interfaz alternativa del sistema, con la misma información y funciones que la
versión en React, pero construida enteramente en Python. Sirve como respaldo o
como interfaz de trabajo más simple.

Todos los comandos se ejecutan desde la terminal integrada de VS Code
(PowerShell en Windows), con la carpeta raíz del proyecto (`E:\informe_de_gestion`)
abierta.

---

## Requisito previo: PostgreSQL corriendo

```bash
docker compose up -d
docker ps
```
`docker ps` debe mostrar el contenedor de Postgres con estado `Up`. Si Docker
Desktop no está abierto, ábrelo primero.

También debe existir un archivo `.env` en la raíz del proyecto con
`DATABASE_URL`, etc. (copia `.env.example` a `.env` si es la primera vez en
esta máquina).

A diferencia de React, **Streamlit no necesita el backend FastAPI corriendo**
— accede directamente a la base de datos, así que basta con una sola terminal.

---

## Paso único — Streamlit

Abre una terminal y activa el entorno virtual:
```bash
.venv\Scripts\Activate.ps1
```
Confirma que aparece `(.venv)` al inicio del prompt. Si `streamlit` no está
instalado en el venv:
```bash
pip install -r requirements.txt
```
Levanta la aplicación:
```bash
streamlit run app.py --server.port 8501
```
Streamlit normalmente abre el navegador solo; si no, entra a
`http://localhost:8501`.

---

## Para detener

`Ctrl+C` en la terminal.

---

## Cómo funciona esta arquitectura

Streamlit funciona muy distinto a React — es **un solo proceso Python** que
genera la interfaz y ejecuta la lógica de negocio al mismo tiempo, sin
separación entre "frontend" y "backend":

- Cada archivo en `vistas/` (`docente.py`, `direccion.py`, `entregas.py`,
  `calendario.py`, `repositorio_asignaturas.py`, etc.) es una función de
  Python que llama **directamente** a `db/repository.py` para leer y escribir
  en PostgreSQL — **no hay una capa de API HTTP intermedia**, ni JWT.
- El control de acceso se maneja con `st.session_state`: al iniciar sesión
  (`vistas/login.py`), se guarda el id, nombre y rol del usuario en la sesión
  de esa pestaña del navegador, y cada vista decide qué mostrar según ese rol
  (por ejemplo, `puede_editar = usuario.rol in ("director", "secretario")`).
- Cada vez que el usuario interactúa (un clic, un `st.button`, cambiar un
  `st.selectbox`, escribir en un campo), Streamlit **vuelve a ejecutar todo el
  script de arriba a abajo** y redibuja la pantalla con el resultado — es un
  modelo de **"rerun completo"**, muy distinto al de React (que solo actualiza
  la parte de la pantalla que cambió).
- Por eso Streamlit es más simple de escribir (todo en un solo lenguaje, sin
  separar interfaz y lógica), pero menos flexible visualmente y algo más
  lento en interacciones frecuentes, ya que cada clic reprocesa la vista
  completa, incluyendo las consultas a la base de datos que esa vista necesite.
- Al no pasar por una API HTTP, el "gate" de consentimiento aquí se aplica
  directamente dentro de `app.py` (una función que revisa
  `usuario.acepto_tratamiento_datos` y llama a `st.stop()` si no ha aceptado la
  versión vigente), en vez de a nivel de cada endpoint como en el backend de
  FastAPI.

```
Navegador  <--HTML/WebSocket-->  Streamlit (un solo proceso Python)  --SQL-->  PostgreSQL
                                        puerto 8501
```

---

## Solución de problemas comunes

**`ModuleNotFoundError: No module named 'streamlit'` (o cualquier otro paquete)**
El entorno virtual no está activado en esa terminal. Verifica que el prompt
muestre `(.venv)`; si no, corre `.venv\Scripts\Activate.ps1` y confirma con:
```bash
python -c "import sys; print(sys.executable)"
```
Debe apuntar a `...\.venv\Scripts\python.exe`. Si sigue fallando después de
activar, instala las dependencias: `pip install -r requirements.txt`.

**Error de conexión a la base de datos**
Confirma `docker ps`: si el contenedor de Postgres no aparece o dice `Exited`,
corre de nuevo `docker compose up -d` y revisa que `DATABASE_URL` en `.env`
tenga las credenciales correctas.

**La página queda "cargando" o en blanco**
Revisa la terminal donde corre `streamlit run` — cualquier error de Python en
una vista aparece ahí como traceback, y usualmente también se refleja en la
página misma (Streamlit muestra el error directamente en el navegador).
