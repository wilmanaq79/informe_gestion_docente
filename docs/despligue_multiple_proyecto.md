# =============================================================================
# DESPLIEGUE PROFESIONAL DE MÚLTIPLES PROYECTOS EN UN MISMO VPS (SIN DOCKER)
#
# Arquitectura recomendada
#
# VPS Ubuntu
# ├── PostgreSQL (Servicio único)
# ├── Nginx (Servicio único)
# ├── Certbot (Servicio único)
# ├── Proyecto 1
# │     ├── Python Virtual Environment
# │     ├── FastAPI
# │     ├── React
# │     └── BaseDatos_Proyecto1
# │
# ├── Proyecto 2
# │     ├── Python Virtual Environment
# │     ├── FastAPI
# │     ├── React
# │     └── BaseDatos_Proyecto2
# │
# ├── Proyecto 3
# │     ├── Python Virtual Environment
# │     ├── FastAPI
# │     ├── React
# │     └── BaseDatos_Proyecto3
# │
# └── Proyecto N
#
# TODOS comparten:
#
# ✔ PostgreSQL
# ✔ Nginx
# ✔ Certbot
#
# Cada proyecto tiene:
#
# ✔ su propia carpeta
# ✔ su propio entorno virtual
# ✔ su propia base de datos
# ✔ su propio usuario PostgreSQL
# ✔ su propio servicio systemd
# ✔ su propio dominio o subdominio
#
# NO comparten:
#
# ❌ Base de datos
# ❌ Usuario PostgreSQL
# ❌ Entorno virtual
# ❌ Variables .env
#
#==============================================================================
# 1. ESTRUCTURA DEL VPS
#==============================================================================

/var/www/

    proyecto1/
    proyecto2/
    proyecto3/
    proyecto4/

Cada proyecto contiene

backend/
frontend/
.venv/
.env.production
alembic/
scripts/

#==============================================================================
# 2. POSTGRESQL (UNA SOLA INSTANCIA)
#==============================================================================

sudo systemctl enable postgresql

sudo systemctl start postgresql

###############################################################################
# Crear una base independiente por proyecto
###############################################################################

sudo -u postgres psql

CREATE USER proyecto1_user
WITH PASSWORD 'PASSWORD_SEGURA_1';

CREATE DATABASE proyecto1_db
OWNER proyecto1_user;

GRANT ALL PRIVILEGES
ON DATABASE proyecto1_db
TO proyecto1_user;

CREATE USER proyecto2_user
WITH PASSWORD 'PASSWORD_SEGURA_2';

CREATE DATABASE proyecto2_db
OWNER proyecto2_user;

GRANT ALL PRIVILEGES
ON DATABASE proyecto2_db
TO proyecto2_user;

CREATE USER proyecto3_user
WITH PASSWORD 'PASSWORD_SEGURA_3';

CREATE DATABASE proyecto3_db
OWNER proyecto3_user;

GRANT ALL PRIVILEGES
ON DATABASE proyecto3_db
TO proyecto3_user;

\q

###############################################################################
# Resultado
###############################################################################

Servidor PostgreSQL

├── proyecto1_db
├── proyecto2_db
├── proyecto3_db

Cada uno con

✔ usuario diferente

✔ contraseña diferente

###############################################################################
# 3. CLONAR CADA PROYECTO
###############################################################################

cd /var/www

git clone REPOSITORIO_PROYECTO1 proyecto1

git clone REPOSITORIO_PROYECTO2 proyecto2

git clone REPOSITORIO_PROYECTO3 proyecto3

###############################################################################
# 4. CREAR ENTORNO VIRTUAL PARA CADA PROYECTO
###############################################################################

cd /var/www/proyecto1

python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

deactivate

cd /var/www/proyecto2

python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

deactivate

...

###############################################################################
# 5. VARIABLES DE PRODUCCIÓN
###############################################################################

Proyecto 1

/var/www/proyecto1/.env.production

DATABASE_URL=postgresql+psycopg://proyecto1_user:CLAVE@127.0.0.1:5432/proyecto1_db

Proyecto 2

DATABASE_URL=postgresql+psycopg://proyecto2_user:CLAVE@127.0.0.1:5432/proyecto2_db

Proyecto 3

DATABASE_URL=postgresql+psycopg://proyecto3_user:CLAVE@127.0.0.1:5432/proyecto3_db

Cada proyecto tiene

JWT diferente

SMTP diferente

SECRET_KEY diferente

###############################################################################
# 6. MIGRACIONES
###############################################################################

Proyecto1

cd /var/www/proyecto1

source .venv/bin/activate

alembic upgrade head

python scripts/init_db.py

Proyecto2

cd /var/www/proyecto2

source .venv/bin/activate

alembic upgrade head

python scripts/init_db.py

...

###############################################################################
# 7. PUERTOS DEL BACKEND
###############################################################################

Proyecto1

127.0.0.1:8001

Proyecto2

127.0.0.1:8002

Proyecto3

127.0.0.1:8003

Proyecto4

127.0.0.1:8004

Nunca usar

0.0.0.0

Nunca repetir puertos.

###############################################################################
# 8. CREAR UN SERVICIO SYSTEMD POR PROYECTO
###############################################################################

sudo nano /etc/systemd/system/proyecto1.service

ExecStart=

/var/www/proyecto1/.venv/bin/gunicorn \
backend.main:app \
-k uvicorn.workers.UvicornWorker \
-w 4 \
-b 127.0.0.1:8001

------------------------------------------------------------------------------

sudo nano /etc/systemd/system/proyecto2.service

ExecStart=

/var/www/proyecto2/.venv/bin/gunicorn \
backend.main:app \
-k uvicorn.workers.UvicornWorker \
-w 4 \
-b 127.0.0.1:8002

------------------------------------------------------------------------------

sudo nano /etc/systemd/system/proyecto3.service

ExecStart=

/var/www/proyecto3/.venv/bin/gunicorn \
backend.main:app \
-k uvicorn.workers.UvicornWorker \
-w 4 \
-b 127.0.0.1:8003

###############################################################################
# 9. ACTIVAR LOS SERVICIOS
###############################################################################

sudo systemctl daemon-reload

sudo systemctl enable proyecto1

sudo systemctl enable proyecto2

sudo systemctl enable proyecto3

sudo systemctl start proyecto1

sudo systemctl start proyecto2

sudo systemctl start proyecto3

###############################################################################
# 10. COMPILAR REACT
###############################################################################

Proyecto1

cd frontend

npm install

npm run build

Proyecto2

npm install

npm run build

...

###############################################################################
# 11. CONFIGURAR NGINX
###############################################################################

Proyecto1

server {

server_name proyecto1.midominio.com;

root /var/www/proyecto1/frontend/dist;

location / {

try_files $uri /index.html;

}

location /api/ {

proxy_pass http://127.0.0.1:8001;

}

}

------------------------------------------------------------------------------

Proyecto2

server {

server_name proyecto2.midominio.com;

root /var/www/proyecto2/frontend/dist;

location / {

try_files $uri /index.html;

}

location /api/ {

proxy_pass http://127.0.0.1:8002;

}

}

------------------------------------------------------------------------------

Proyecto3

server {

server_name proyecto3.midominio.com;

root /var/www/proyecto3/frontend/dist;

location / {

try_files $uri /index.html;

}

location /api/ {

proxy_pass http://127.0.0.1:8003;

}

}

###############################################################################
# 12. ACTIVAR NGINX
###############################################################################

sudo nginx -t

sudo systemctl reload nginx

###############################################################################
# 13. HTTPS
###############################################################################

sudo certbot --nginx \
-d proyecto1.midominio.com

sudo certbot --nginx \
-d proyecto2.midominio.com

sudo certbot --nginx \
-d proyecto3.midominio.com

###############################################################################
# 14. BACKUPS
###############################################################################

Cada proyecto

pg_dump proyecto1_db

pg_dump proyecto2_db

pg_dump proyecto3_db

Nunca mezclar bases.

###############################################################################
# 15. ACTUALIZAR UN SOLO PROYECTO
###############################################################################

cd /var/www/proyecto2

git pull

source .venv/bin/activate

pip install -r requirements.txt

alembic upgrade head

python scripts/init_db.py

cd frontend

npm install

npm run build

sudo systemctl restart proyecto2

sudo systemctl reload nginx

###############################################################################
# El resto de proyectos siguen funcionando.
###############################################################################

###############################################################################
# 16. MONITOREO
###############################################################################

Proyecto1

sudo journalctl -u proyecto1 -f

Proyecto2

sudo journalctl -u proyecto2 -f

Proyecto3

sudo journalctl -u proyecto3 -f

###############################################################################
# 17. VERIFICAR PUERTOS
###############################################################################

sudo ss -tulpn

Solo abiertos

22

80

443

Internamente

8001

8002

8003

###############################################################################
# 18. BUENAS PRÁCTICAS
###############################################################################

✔ Un solo PostgreSQL.

✔ Un solo Nginx.

✔ Un solo Certbot.

✔ Una base por proyecto.

✔ Un usuario PostgreSQL por proyecto.

✔ Un Virtual Environment por proyecto.

✔ Un archivo .env.production por proyecto.

✔ Un servicio systemd por proyecto.

✔ Un subdominio por proyecto.

✔ Un puerto interno diferente por proyecto.

✔ Nunca usar localhost en el Frontend.

✔ Nunca subir .env.production al repositorio.

✔ Siempre ejecutar Alembic antes de iniciar.

✔ Siempre hacer backup antes de actualizar.

✔ Nunca reiniciar el VPS para actualizar un proyecto.

✔ Nunca detener PostgreSQL para actualizar un proyecto.

✔ Nunca mezclar dependencias Python entre proyectos.

✔ Nunca compartir bases de datos entre proyectos.

✔ Documentar cada despliegue y mantener un registro de versiones.

#==============================================================================
# EJEMPLO FINAL
#==============================================================================

VPS Ubuntu

├── PostgreSQL
│      ├── gestion_docente_db
│      ├── crm_db
│      ├── inventario_db
│      └── analitica_db
│
├── Nginx
│      ├── gestion.midominio.com
│      ├── crm.midominio.com
│      ├── inventario.midominio.com
│      └── analitica.midominio.com
│
├── /var/www/
│      ├── gestion_docente/
│      ├── crm/
│      ├── inventario/
│      └── analitica/
│
└── systemd
       ├── gestion_docente.service
       ├── crm.service
       ├── inventario.service
       └── analitica.service

# Esta arquitectura es la recomendada para alojar múltiples aplicaciones
# independientes en un mismo VPS sin Docker, manteniendo aislamiento entre
# proyectos, facilidad de mantenimiento y buenas prácticas de producción.
#============================================================================== 