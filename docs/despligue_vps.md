# =============================================================================
# DESPLIEGUE PROFESIONAL EN VPS (SIN DOCKER)
# React + Vite + FastAPI + PostgreSQL + Nginx + HTTPS
#
# Arquitectura:
#
# Internet
#      │
#      ▼
#  Nginx + HTTPS
#      │
#      ├────────────► Frontend React (dist)
#      │
#      └────────────► FastAPI (Gunicorn + Uvicorn)
#                           │
#                           ▼
#                     PostgreSQL Local
#
# =============================================================================

###############################################################################
# 1. CONECTARSE AL VPS
###############################################################################

ssh wilman@IP_PUBLICA_DEL_VPS

###############################################################################
# 2. ACTUALIZAR EL SISTEMA
###############################################################################

sudo apt update
sudo apt upgrade -y

sudo apt install -y \
git \
curl \
wget \
nano \
unzip \
build-essential \
python3 \
python3-pip \
python3-venv \
postgresql \
postgresql-contrib \
nginx \
certbot \
python3-certbot-nginx \
ufw \
fail2ban \
nodejs \
npm

sudo timedatectl set-timezone America/Bogota

###############################################################################
# 3. CONFIGURAR FIREWALL
###############################################################################

sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

sudo ufw default deny incoming
sudo ufw default allow outgoing

sudo ufw enable

sudo ufw status

###############################################################################
# 4. CREAR BASE DE DATOS
###############################################################################

sudo systemctl enable postgresql
sudo systemctl start postgresql

sudo -u postgres psql

CREATE USER gestion_docente_app
WITH PASSWORD 'CAMBIAR_POR_UNA_CLAVE_SEGURA';

CREATE DATABASE gestion_docente
OWNER gestion_docente_app;

GRANT ALL PRIVILEGES
ON DATABASE gestion_docente
TO gestion_docente_app;

\q

###############################################################################
# 5. CREAR DIRECTORIO DE LA APLICACIÓN
###############################################################################

sudo mkdir -p /var/www/informe-de-gestion

sudo chown -R $USER:$USER /var/www/informe-de-gestion

cd /var/www/informe-de-gestion

###############################################################################
# 6. DESCARGAR EL PROYECTO
###############################################################################

git clone URL_DEL_REPOSITORIO .

# o

git pull origin main

###############################################################################
# 7. CREAR ENTORNO VIRTUAL
###############################################################################

python3 -m venv .venv

source .venv/bin/activate

pip install --upgrade pip

pip install -r requirements.txt

###############################################################################
# 8. CREAR VARIABLES DE PRODUCCIÓN
###############################################################################

nano .env.production

###############################################################################
# Ejemplo
###############################################################################

APP_ENV=production

DATABASE_URL=postgresql+psycopg://gestion_docente_app:CLAVE_SEGURA@127.0.0.1:5432/gestion_docente

JWT_SECRET_KEY=GENERAR_CLAVE_DE_64_CARACTERES

JWT_ALGORITHM=HS256

JWT_EXPIRE_MINUTES=480

FRONTEND_URL=https://gestion.midominio.com

CORS_ORIGINS=https://gestion.midominio.com

SMTP_HOST=

SMTP_PORT=587

SMTP_USER=

SMTP_PASSWORD=

SMTP_FROM=

SMTP_USE_TLS=true

###############################################################################
# 9. CREAR TABLAS
###############################################################################

source .venv/bin/activate

alembic upgrade head

###############################################################################
# 10. CREAR ROLES Y USUARIOS
###############################################################################

python scripts/init_db.py

###############################################################################
# 11. PROBAR BACKEND
###############################################################################

uvicorn backend.main:app \
--host 127.0.0.1 \
--port 8000

Abrir:

http://IP_DEL_SERVIDOR:8000/docs

Si todo funciona detener con CTRL+C.

###############################################################################
# 12. CREAR SERVICIO SYSTEMD
###############################################################################

sudo nano /etc/systemd/system/informe-gestion.service

###############################################################################
# Contenido
###############################################################################

[Unit]
Description=Informe de Gestión
After=network.target postgresql.service

[Service]

User=wilman

Group=www-data

WorkingDirectory=/var/www/informe-de-gestion

EnvironmentFile=/var/www/informe-de-gestion/.env.production

ExecStart=/var/www/informe-de-gestion/.venv/bin/gunicorn \
backend.main:app \
-k uvicorn.workers.UvicornWorker \
-w 4 \
-b 127.0.0.1:8000

Restart=always

RestartSec=5

[Install]
WantedBy=multi-user.target

###############################################################################
# 13. ACTIVAR SERVICIO
###############################################################################

sudo systemctl daemon-reload

sudo systemctl enable informe-gestion

sudo systemctl start informe-gestion

sudo systemctl status informe-gestion

###############################################################################
# Logs
###############################################################################

sudo journalctl -u informe-gestion -f

###############################################################################
# 14. INSTALAR FRONTEND
###############################################################################

cd frontend

npm install

npm run build

###############################################################################
# Resultado
###############################################################################

frontend/dist/

###############################################################################
# 15. CONFIGURAR NGINX
###############################################################################

sudo nano /etc/nginx/sites-available/informe-gestion

###############################################################################
# Configuración
###############################################################################

server {

listen 80;

server_name gestion.midominio.com;

root /var/www/informe-de-gestion/frontend/dist;

index index.html;

client_max_body_size 20M;

location / {

try_files $uri $uri/ /index.html;

}

location /api/ {

proxy_pass http://127.0.0.1:8000;

proxy_http_version 1.1;

proxy_set_header Host $host;

proxy_set_header X-Real-IP $remote_addr;

proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

proxy_set_header X-Forwarded-Proto $scheme;

}

}

###############################################################################
# Activar sitio
###############################################################################

sudo ln -s \
/etc/nginx/sites-available/informe-gestion \
/etc/nginx/sites-enabled/

sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t

sudo systemctl restart nginx

###############################################################################
# 16. INSTALAR HTTPS
###############################################################################

sudo certbot --nginx \
-d gestion.midominio.com \
--agree-tos \
--redirect \
-m TU_CORREO \
--no-eff-email

###############################################################################
# Verificar renovación
###############################################################################

sudo certbot renew --dry-run

###############################################################################
# 17. PROBAR LA APLICACIÓN
###############################################################################

https://gestion.midominio.com

Probar:

✓ Login

✓ Roles

✓ CRUD

✓ Recuperación contraseña

✓ API

###############################################################################
# 18. BACKUP
###############################################################################

mkdir -p /backups/postgres

pg_dump \
-U gestion_docente_app \
-Fc \
gestion_docente \
> /backups/postgres/gestion_$(date +%Y%m%d).backup

###############################################################################
# Restaurar
###############################################################################

pg_restore \
-U gestion_docente_app \
-d gestion_docente \
backup.backup

###############################################################################
# 19. ACTUALIZAR EL PROYECTO
###############################################################################

cd /var/www/informe-de-gestion

git pull origin main

source .venv/bin/activate

pip install -r requirements.txt

alembic upgrade head

python scripts/init_db.py

cd frontend

npm install

npm run build

sudo systemctl restart informe-gestion

sudo systemctl reload nginx

###############################################################################
# 20. VERIFICAR SERVICIOS
###############################################################################

sudo systemctl status postgresql

sudo systemctl status nginx

sudo systemctl status informe-gestion

###############################################################################
# 21. VERIFICAR PUERTOS
###############################################################################

sudo ss -tulpn

Solo deben estar abiertos:

22
80
443

###############################################################################
# 22. REGLAS DE PRODUCCIÓN
###############################################################################

✔ Nunca usar localhost en FRONTEND_URL

✔ Nunca subir .env.production a Git

✔ Nunca usar uvicorn --reload

✔ Siempre usar Gunicorn + Uvicorn

✔ Siempre ejecutar Alembic antes de iniciar

✔ Siempre crear backup antes de actualizar

✔ Siempre probar login después del despliegue

✔ Mantener PostgreSQL escuchando únicamente en localhost

✔ Renovar certificados automáticamente

✔ Monitorear logs con journalctl

✔ Utilizar HTTPS obligatorio

✔ Mantener el sistema actualizado

✔ Cambiar inmediatamente las contraseñas iniciales

###############################################################################
# FIN
###############################################################################