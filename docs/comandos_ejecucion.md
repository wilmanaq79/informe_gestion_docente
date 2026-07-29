1. Abre el proyecto en VS Code
File > Open Folder... → selecciona E:\informe_de_gestion.

2. Abre una terminal integrada
Terminal > New Terminal (o Ctrl + ñ / Ctrl + backtick). Por defecto en Windows suele abrir PowerShell — los comandos de abajo son para PowerShell.

3. Levanta PostgreSQL (Docker)
Asegúrate de que Docker Desktop esté abierto y corriendo, luego en la terminal:
docker compose up -d

Verifica que el contenedor quedó arriba:
docker ps

4. Activa el entorno virtual de Python
En esa misma terminal (la usarás para el backend):

.venv\Scripts\Activate.ps1
Si PowerShell bloquea el script por política de ejecución, corre una vez:
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

5. Levanta el backend (FastAPI)
Con el venv activado:

uvicorn backend.main:app --reload --port 8000
Déjala corriendo. Verifica en el navegador: http://localhost:8000/api/health debe responder {"status":"ok"}.

6. Abre una segunda terminal para Streamlit
Ícono + en el panel de terminal (o Ctrl+Shift+ñ). Activa el venv otra vez y corre:

.venv\Scripts\Activate.ps1
streamlit run app.py --server.port 8501
7. Abre una tercera terminal para el frontend React

cd frontend
npm install
npm run dev
(el npm install solo hace falta la primera vez o si cambiaron dependencias).

8. Abre la app en el navegador

React (interfaz principal): http://localhost:5173
Streamlit (interfaz alternativa): http://localhost:8501
Documentación interactiva de la API: http://localhost:8000/docs
Para detener todo: Ctrl+C en cada una de las 3 terminales.

¿Quieres que además prepare un único script (.ps1 o tasks.json de VS Code) para levantar los 3 con un solo comando/atajo?


# ---------
gestion_docente_app. 

2. Inicia sesión en pgAdmin (esto es un login propio de la herramienta, distinto al de Postgres):
http://localhost:8080
Correo: wilmantecno@gmail.com
Contraseña: admin123

3. Una vez adentro, en el panel izquierdo busca "Servers" en el árbol:

Si ya hay un servidor guardado (probablemente sí, porque llevas tiempo usándolo), haz clic en él y te pedirá la contraseña de Postgres (no la de pgAdmin) — ahí sí usa la del usuario con el que te quieras conectar:
gestion_docente_app / GtDocente2026SeguroXk7Qp (el nuevo, recomendado para este proyecto)
o admin / secret123 (el superusuario compartido, ya no recomendado para uso diario)

postgres
port: 5432
mydatabase
user: gestion_docente_app
password: GtDocente2026SeguroXk7Qp

Si no hay ninguno guardado, dime y te doy los pasos para crear la conexión desde cero (Host, Puerto, usuario, etc.).

# -----
Paso 2 — Backend
En VS Code, abre una terminal nueva y ejecuta:
.venv\Scripts\Activate.ps1
Confirma que aparece (.venv) al inicio del prompt, y luego:
uvicorn backend.main:app --reload --port 8000

Paso 2 — Frontend (React)

Abre una segunda terminal en VS Code (ícono + en el panel de terminal, para no cerrar la del backend) y ejecuta:

cd frontend
npm install
npm run dev
(el npm install solo la primera vez o si cambiaron las dependencias).

Cuando termine, debe mostrarte algo como Local: http://localhost:5173/. Avísame cuando lo veas.