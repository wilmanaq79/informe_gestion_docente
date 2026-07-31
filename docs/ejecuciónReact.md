# Cómo ejecutar el proyecto con React

Interfaz principal del sistema, pensada para el uso final de los docentes,
Director, Secretario Académico y Secretaria del Programa durante el piloto.

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
`DATABASE_URL`, `JWT_SECRET_KEY`, etc. (copia `.env.example` a `.env` si es la
primera vez en esta máquina, y usa credenciales propias — nunca un usuario
"admin" genérico compartido con otros proyectos).

---

## Paso 1 — Backend (FastAPI)
deactivate

Abre una terminal y activa el entorno virtual:
```bash
.venv\Scripts\Activate.ps1
```
Confirma que aparece `(.venv)` al inicio del prompt. Si `fastapi` no está
instalado en el venv:
```bash
pip install -r requirements.txt
```
Levanta el backend:
```bash
uvicorn backend.main:app --reload --port 8000
```
Verifica en el navegador: `http://localhost:8000/api/health` → debe responder
`{"status":"ok"}`. Deja esta terminal corriendo.

---

## Paso 2 — Frontend (React)

Abre una **segunda terminal** (ícono `+` en el panel de terminal, para no
cerrar la del backend):
```bash
cd frontend
npm install
npm run dev
```
(`npm install` solo hace falta la primera vez, o si cambiaron las dependencias
del `package.json`). Debe mostrar `Local: http://localhost:5173/`.

---

## Paso 3 — Abre la aplicación

`http://localhost:5173` → ahí está el login de React. Inicia sesión con tu
usuario y contraseña reales.

---

## Para detener

`Ctrl+C` en ambas terminales (backend y frontend).

---

## Cómo funciona esta arquitectura

Es una arquitectura **cliente-servidor clásica, en dos procesos separados**
que se comunican por HTTP:

- **El backend (FastAPI, puerto 8000)** expone una API REST (`/api/...`):
  recibe peticiones HTTP, valida quién es el usuario y qué rol tiene (mediante
  un token **JWT** que se genera al iniciar sesión), consulta o escribe en
  PostgreSQL a través de `db/repository.py`, y devuelve la respuesta en JSON.
  Cada endpoint decide, por su cuenta, qué roles pueden usarlo
  (`requiere_roles()` en `backend/api/deps.py`) — el control de acceso vive
  en el servidor, nunca confiando en lo que diga el navegador.
- **El frontend (React, puerto 5173 en desarrollo)** es una aplicación de una
  sola página (**SPA**, *Single Page Application*) que corre por completo en
  el navegador del usuario. Cuando el usuario hace clic o llena un formulario,
  React llama a la API (por ejemplo `axios.get("/api/notificaciones")`) y
  actualiza solo la parte de la pantalla que cambió, sin recargar la página
  completa.
- El navegador **nunca toca la base de datos directamente** — todo pasa por
  el backend. Esto es justo lo que hace posible el "gate" de consentimiento a
  nivel de API: como toda petición pasa por el backend, ahí es donde se puede
  bloquear con un 403 a cualquiera que no haya aceptado el Aviso de Privacidad,
  sin importar por dónde intente entrar (la interfaz web, o directamente por
  `curl`/Postman).
- En **producción**, el paso `npm run dev` se reemplaza por `npm run build`:
  eso genera archivos estáticos (HTML/CSS/JS) que un servidor web (Nginx) sirve
  directamente, sin que Node siga corriendo — ver `docs/DESPLIEGUE_VPS.md`
  para el detalle completo de ese proceso.

```
Navegador (React, SPA)  --HTTP/JSON-->  Backend (FastAPI)  --SQL-->  PostgreSQL
     puerto 5173              /api/...       puerto 8000
```

---

## Solución de problemas comunes

**`ModuleNotFoundError: No module named 'fastapi'` (o cualquier otro paquete)**
El entorno virtual no está activado en esa terminal. Verifica que el prompt
muestre `(.venv)`; si no, corre `.venv\Scripts\Activate.ps1` y confirma con:
```bash
python -c "import sys; print(sys.executable)"
```
Debe apuntar a `...\.venv\Scripts\python.exe`. Si sigue fallando después de
activar, instala las dependencias: `pip install -r requirements.txt`.

**El navegador no carga nada en `localhost:5173` o da error de conexión**
Confirma que la terminal del backend (puerto 8000) sigue corriendo — React
depende de que el backend esté arriba.

**Error de conexión a la base de datos**
Confirma `docker ps`: si el contenedor de Postgres no aparece o dice `Exited`,
corre de nuevo `docker compose up -d` y revisa que `DATABASE_URL` en `.env`
tenga las mismas credenciales que el usuario/base de datos dedicados de este
proyecto.
