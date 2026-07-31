
La arquitectura propuesta utiliza un Docker Compose independiente por aplicación, una red pública compartida únicamente con un proxy Nginx central, redes internas aisladas, bases de datos y volúmenes separados. FastAPI recomienda construir una imagen propia desde una imagen oficial de Python y usar encabezados de proxy cuando se ejecuta detrás de Nginx; Nginx usa proxy_pass para enviar las solicitudes al servicio interno correspondiente


# =============================================================================
# GUÍA PROFESIONAL DE PRODUCCIÓN PARA EL PROYECTO "INFORME_DE_GESTION"
# Y PARA PUBLICAR VARIAS APLICACIONES EN EL MISMO VPS
#
# Tecnología identificada en el proyecto:
# - Backend: FastAPI + Python + SQLAlchemy.
# - Frontend: React + Vite.
# - Base de datos: PostgreSQL.
# - Migraciones: se recomienda Alembic.
# - Servidor web: Nginx.
# - Orquestación: Docker Compose.
#
# Estructura actual observada:
#
# informe_de_gestion/
# ├── backend/
# ├── frontend/
# ├── scripts/
# ├── tests/
# ├── assets/
# ├── agente_notas/
# ├── db/
# ├── documentos/
# ├── entregas_docentes/
# ├── evidencias_tareas/
# ├── repositorio_asignaturas/
# ├── vistas/
# ├── .env
# ├── .env.example
# ├── app.py
# ├── docker-compose.yml
# ├── requirements.txt
# ├── pytest.ini
# └── README.md
#
# IMPORTANTE:
# La estructura actual todavía debe complementarse para producción con:
#
# ├── backend/Dockerfile
# ├── frontend/Dockerfile
# ├── frontend/nginx.conf
# ├── compose.yaml
# ├── compose.prod.yaml
# ├── .dockerignore
# ├── alembic.ini
# ├── alembic/
# ├── scripts/init_db.py
# ├── scripts/backup_db.sh
# ├── scripts/restore_db.sh
# └── docs/DESPLIEGUE_VPS.md
#
# No copies literalmente todas las plantillas sin que Claude Code verifique:
# - El nombre real del objeto FastAPI: backend.main:app.
# - Las rutas reales de los modelos SQLAlchemy.
# - Los directorios que contienen archivos permanentes.
# - El comando real del script de inicialización.
# - Las variables reales utilizadas por el backend.
# =============================================================================


# =============================================================================
# PARTE 1. ARQUITECTURA FINAL PARA VARIOS PROYECTOS
# =============================================================================
#
# VPS
# └── /opt/apps/
#     ├── proxy/
#     │   ├── compose.yaml
#     │   ├── nginx/
#     │   │   └── conf.d/
#     │   ├── certbot/
#     │   └── letsencrypt/
#     │
#     ├── informe-de-gestion/
#     │   ├── compose.yaml
#     │   ├── compose.prod.yaml
#     │   ├── .env.production
#     │   ├── backend/
#     │   ├── frontend/
#     │   ├── scripts/
#     │   ├── alembic/
#     │   └── storage/
#     │
#     └── inventario/                     <- Ejemplo de segunda aplicación
#         ├── compose.yaml
#         ├── compose.prod.yaml
#         ├── .env.production
#         ├── backend/
#         ├── frontend/
#         ├── scripts/
#         ├── alembic/
#         └── storage/
#
# Internet
#    │
#    ▼
# Proxy Nginx central: puertos 80 y 443
#    │
#    ├── gestion.dominio.com
#    │       └── gateway del proyecto Informe de Gestión
#    │               ├── sirve React
#    │               └── /api → FastAPI
#    │
#    └── inventario.dominio.com
#            └── gateway del proyecto Inventario
#                    ├── sirve React
#                    └── /api → FastAPI
#
# Cada proyecto tendrá:
# - Un gateway Nginx propio.
# - Un backend propio.
# - Un PostgreSQL propio.
# - Una red interna propia.
# - Un volumen PostgreSQL propio.
# - Variables, usuarios, contraseñas y JWT independientes.
#
# Solo el proxy central publica:
# - 80/tcp
# - 443/tcp
#
# No se publican:
# - 5432 PostgreSQL.
# - 8000 FastAPI.
# - 5173 Vite.
# - 8080 pgAdmin.
# =============================================================================


# =============================================================================
# PARTE 2. PREPARAR EL PROYECTO ANTES DE SUBIRLO
# ESTOS CAMBIOS DEBEN SER REALIZADOS Y PROBADOS POR CLAUDE CODE
# =============================================================================


# -----------------------------------------------------------------------------
# 2.1. CREAR backend/Dockerfile
# -----------------------------------------------------------------------------
#
# Debe construirse desde la raíz del repositorio porque requirements.txt
# está actualmente en la raíz y el backend se encuentra en backend/.
#
# Archivo: backend/Dockerfile
#
cat > backend/Dockerfile <<'EOF'
# Imagen oficial y versión fija.
# Claude debe escoger una versión compatible con el proyecto.
FROM python:3.13-slim

# Evita archivos .pyc y habilita logs inmediatos.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Crear primero un usuario sin privilegios.
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --create-home appuser

# Instalar únicamente bibliotecas del sistema realmente necesarias.
# Claude debe revisar si psycopg usa binarios o requiere libpq-dev/gcc.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar primero dependencias para aprovechar la caché de Docker.
COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copiar el código requerido por FastAPI, migraciones y scripts.
COPY backend /app/backend
COPY scripts /app/scripts
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

# Si app.py contiene lógica necesaria, Claude debe determinar si se copia.
# COPY app.py /app/app.py

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Producción:
# - Sin --reload.
# - Escucha en 0.0.0.0 dentro del contenedor.
# - Interpreta encabezados enviados por Nginx.
# - Los workers deben ajustarse a la RAM y CPU del VPS.
CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", \
     "--forwarded-allow-ips=*"]
EOF


# -----------------------------------------------------------------------------
# 2.2. CREAR frontend/Dockerfile
# -----------------------------------------------------------------------------
#
# Este Dockerfile realiza una compilación multietapa:
#
# Etapa 1:
# - Instala dependencias con npm ci.
# - Compila React.
#
# Etapa 2:
# - Sirve el resultado con Nginx.
# - Envía /api al backend.
#
# Archivo: frontend/Dockerfile
#
cat > frontend/Dockerfile <<'EOF'
# -------------------------- ETAPA DE COMPILACIÓN -----------------------------
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./

# npm ci es reproducible y utiliza exactamente package-lock.json.
RUN npm ci

COPY . .

# El frontend debe usar rutas relativas /api en producción.
# No debe apuntar a localhost:8000.
RUN npm run build


# -------------------------- ETAPA DE EJECUCIÓN -------------------------------
FROM nginx:1.28-alpine

# Eliminar configuración predeterminada.
RUN rm -f /etc/nginx/conf.d/default.conf

# Copiar configuración específica de la aplicación.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar solamente los archivos compilados.
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -q --spider http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
EOF


# -----------------------------------------------------------------------------
# 2.3. CREAR frontend/nginx.conf
# -----------------------------------------------------------------------------
#
# Este Nginx funciona como gateway interno del proyecto:
# - Sirve React.
# - Resuelve rutas SPA.
# - Envía /api al backend.
#
cat > frontend/nginx.conf <<'EOF'
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # No revelar versión de Nginx.
    server_tokens off;

    # Ajustar según los archivos que maneje la aplicación.
    client_max_body_size 50M;

    # Endpoint interno de salud del gateway.
    location = /health {
        access_log off;
        add_header Content-Type text/plain;
        return 200 "ok";
    }

    # API FastAPI.
    # Al no incluir una URI al final de proxy_pass, se conserva /api/...
    location /api/ {
        proxy_pass http://backend:8000;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 30s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # Archivos estáticos versionados.
    location ~* \.(?:css|js|jpg|jpeg|png|gif|svg|ico|woff2?)$ {
        try_files $uri =404;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # React Router: rutas desconocidas regresan a index.html.
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Bloquear archivos ocultos.
    location ~ /\. {
        deny all;
    }
}
EOF


# -----------------------------------------------------------------------------
# 2.4. CREAR .dockerignore EN LA RAÍZ
# -----------------------------------------------------------------------------
#
# Evita enviar secretos, caché y archivos innecesarios al contexto de build.
#
cat > .dockerignore <<'EOF'
.git
.gitignore
.env
.env.*
!.env.example

.venv
venv
__pycache__
*.py[cod]
.pytest_cache
.coverage
htmlcov

frontend/node_modules
frontend/dist

*.log
*.tmp

backups
certbot
letsencrypt

# Si estos directorios contienen datos reales de usuarios,
# no deben incorporarse a las imágenes:
entregas_docentes
evidencias_tareas
repositorio_asignaturas
documentos
EOF


# -----------------------------------------------------------------------------
# 2.5. REVISAR LOS DIRECTORIOS PERSISTENTES
# -----------------------------------------------------------------------------
#
# En la imagen aparecen:
#
# - documentos/
# - entregas_docentes/
# - evidencias_tareas/
# - repositorio_asignaturas/
# - agente_notas/
# - assets/
# - db/
#
# Claude Code debe determinar cuáles son:
#
# A. Código o archivos estáticos del proyecto.
# B. Datos generados en tiempo de ejecución.
#
# Todo dato generado por usuarios debe persistir fuera del contenedor.
#
# Recomendación de almacenamiento en producción:
#
# /opt/apps/informe-de-gestion/storage/
# ├── documentos/
# ├── entregas_docentes/
# ├── evidencias_tareas/
# └── repositorio_asignaturas/
#
# Esos directorios pueden montarse como bind mounts o volúmenes.
#
# No montar automáticamente assets/, db/ o agente_notas/ sin revisar primero
# qué contienen y qué rutas espera el código.
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# 2.6. CONFIGURAR ALEMBIC
# -----------------------------------------------------------------------------
#
# La base vacía debe poder reconstruirse con:
#
# alembic upgrade head
#
# No se deben crear tablas manualmente desde pgAdmin.
#
# Claude Code debe:
# - Configurar alembic.ini.
# - Importar correctamente Base.metadata.
# - Generar la migración inicial.
# - Verificar todas las tablas.
# - Añadir nuevas migraciones por cada cambio futuro.
#
# Comandos de desarrollo:
#
# alembic revision --autogenerate -m "migracion inicial"
# alembic upgrade head
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# 2.7. CREAR scripts/init_db.py
# -----------------------------------------------------------------------------
#
# El script debe ser idempotente:
#
# - Crear roles si no existen.
# - Crear permisos si no existen.
# - Crear Administrador si no existe.
# - Crear Director si no existe.
# - Utilizar el mismo hash del endpoint de login.
# - No insertar contraseñas en texto plano.
# - No imprimir secretos.
# - Obtener credenciales desde variables de entorno.
#
# Comando esperado:
#
# python scripts/init_db.py
#
# Variables sugeridas:
#
# INITIAL_ADMIN_USERNAME
# INITIAL_ADMIN_EMAIL
# INITIAL_ADMIN_PASSWORD
# INITIAL_DIRECTOR_USERNAME
# INITIAL_DIRECTOR_EMAIL
# INITIAL_DIRECTOR_PASSWORD
# -----------------------------------------------------------------------------


# =============================================================================
# PARTE 3. COMPOSE COMÚN DEL PROYECTO
# =============================================================================
#
# Archivo: compose.yaml
#
cat > compose.yaml <<'EOF'
services:
  postgres_db:
    image: postgres:16.10-alpine
    restart: unless-stopped

    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}

    volumes:
      - postgres_data:/var/lib/postgresql/data

    networks:
      - internal

    healthcheck:
      test:
        [
          "CMD-SHELL",
          "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
        ]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 20s

    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"


  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile

    restart: unless-stopped

    env_file:
      - .env.production

    depends_on:
      postgres_db:
        condition: service_healthy

    networks:
      - internal

    expose:
      - "8000"

    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
        ]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 30s

    volumes:
      # Estos directorios deben existir en el VPS.
      - ./storage/documentos:/app/documentos
      - ./storage/entregas_docentes:/app/entregas_docentes
      - ./storage/evidencias_tareas:/app/evidencias_tareas
      - ./storage/repositorio_asignaturas:/app/repositorio_asignaturas

    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"


  gateway:
    build:
      context: ./frontend
      dockerfile: Dockerfile

    restart: unless-stopped

    depends_on:
      backend:
        condition: service_healthy

    networks:
      internal:
      proxy_public:
        aliases:
          # Alias único en la red compartida.
          - gestion_gateway

    expose:
      - "80"

    healthcheck:
      test:
        ["CMD-SHELL", "wget -q --spider http://127.0.0.1/health || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 5

    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"


volumes:
  postgres_data:


networks:
  # Red privada: solo servicios de esta aplicación.
  internal:
    internal: true

  # Red compartida exclusivamente con el proxy central.
  proxy_public:
    external: true
EOF


# =============================================================================
# PARTE 4. CONFIGURACIÓN ESPECÍFICA DE PRODUCCIÓN
# =============================================================================
#
# Archivo: compose.prod.yaml
#
# Se utiliza como complemento de compose.yaml.
#
cat > compose.prod.yaml <<'EOF'
services:
  postgres_db:
    # PostgreSQL NO publica 5432.
    mem_limit: 1536m
    cpus: 1.0

  backend:
    mem_limit: 1024m
    cpus: 1.5

    # Protección básica del sistema de archivos.
    read_only: true

    # Directorios temporales escribibles.
    tmpfs:
      - /tmp

  gateway:
    mem_limit: 256m
    cpus: 0.5
EOF


# =============================================================================
# PARTE 5. ARCHIVO .env.example SEGURO
# =============================================================================
#
# No contiene secretos reales.
#
cat > .env.example <<'EOF'
APP_ENV=production
APP_DOMAIN=gestion.dominio.com

POSTGRES_USER=gestion_docente_app
POSTGRES_PASSWORD=CAMBIAR_CLAVE
POSTGRES_DB=gestion_docente

# Dentro de Docker se usa postgres_db, nunca localhost.
DATABASE_URL=postgresql+psycopg://gestion_docente_app:CAMBIAR_CLAVE@postgres_db:5432/gestion_docente

JWT_SECRET_KEY=GENERAR_CLAVE
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

FRONTEND_URL=https://gestion.dominio.com
CORS_ORIGINS=https://gestion.dominio.com

INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_EMAIL=admin@dominio.com
INITIAL_ADMIN_PASSWORD=CAMBIAR_CLAVE_TEMPORAL

INITIAL_DIRECTOR_USERNAME=wilman
INITIAL_DIRECTOR_EMAIL=director@dominio.com
INITIAL_DIRECTOR_PASSWORD=CAMBIAR_CLAVE_TEMPORAL

SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=true
EOF


# =============================================================================
# PARTE 6. PREPARAR EL VPS
# =============================================================================

# Sustituir:
#
# IP_VPS
# URL_REPOSITORIO
# gestion.dominio.com
# CORREO_SSL

ssh wilman@IP_VPS

sudo apt update
sudo apt upgrade -y

sudo apt install -y \
  ca-certificates \
  curl \
  git \
  gnupg \
  ufw \
  fail2ban \
  nano

sudo timedatectl set-timezone America/Bogota


# -----------------------------------------------------------------------------
# 6.1. FIREWALL
# -----------------------------------------------------------------------------

sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

sudo ufw default deny incoming
sudo ufw default allow outgoing

sudo ufw enable
sudo ufw status verbose


# -----------------------------------------------------------------------------
# 6.2. INSTALAR DOCKER
# -----------------------------------------------------------------------------

sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL \
  https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update

sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

sudo systemctl enable --now docker

sudo usermod -aG docker "$USER"

# Cerrar sesión para aplicar el grupo.
exit


# -----------------------------------------------------------------------------
# 6.3. REGRESAR AL VPS
# -----------------------------------------------------------------------------

ssh wilman@IP_VPS

docker version
docker compose version


# =============================================================================
# PARTE 7. CREAR ESTRUCTURA PARA MÚLTIPLES APLICACIONES
# =============================================================================

sudo mkdir -p /opt/apps/proxy
sudo mkdir -p /opt/apps/informe-de-gestion
sudo mkdir -p /opt/apps/inventario
sudo mkdir -p /var/backups/apps

sudo chown -R "$USER":"$USER" /opt/apps
sudo chmod -R 750 /opt/apps

sudo chmod 700 /var/backups/apps


# -----------------------------------------------------------------------------
# 7.1. CREAR RED COMPARTIDA DEL PROXY
# -----------------------------------------------------------------------------

docker network inspect proxy_public >/dev/null 2>&1 \
  || docker network create proxy_public


# =============================================================================
# PARTE 8. DESPLEGAR EL PROXY NGINX CENTRAL
# =============================================================================

cd /opt/apps/proxy

mkdir -p nginx/conf.d
mkdir -p certbot/www
mkdir -p letsencrypt

cat > compose.yaml <<'EOF'
services:
  nginx:
    image: nginx:1.28-alpine
    container_name: central_proxy
    restart: unless-stopped

    ports:
      - "80:80"
      - "443:443"

    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./certbot/www:/var/www/certbot:ro
      - ./letsencrypt:/etc/letsencrypt:ro

    networks:
      - proxy_public

    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"


  certbot:
    image: certbot/certbot:v5.0.0

    volumes:
      - ./certbot/www:/var/www/certbot
      - ./letsencrypt:/etc/letsencrypt

    networks:
      - proxy_public


networks:
  proxy_public:
    external: true
EOF


# -----------------------------------------------------------------------------
# 8.1. CONFIGURACIÓN HTTP INICIAL DE INFORME DE GESTIÓN
# -----------------------------------------------------------------------------

cat > nginx/conf.d/gestion.conf <<'EOF'
server {
    listen 80;
    server_name gestion.dominio.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://gestion_gateway:80;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

docker compose up -d nginx
docker compose ps


# =============================================================================
# PARTE 9. SUBIR INFORME DE GESTIÓN
# =============================================================================

cd /opt/apps/informe-de-gestion

git clone URL_REPOSITORIO .

git fetch --all --tags
git checkout main

ls -la


# -----------------------------------------------------------------------------
# 9.1. CREAR DIRECTORIOS PERSISTENTES
# -----------------------------------------------------------------------------

mkdir -p storage/documentos
mkdir -p storage/entregas_docentes
mkdir -p storage/evidencias_tareas
mkdir -p storage/repositorio_asignaturas

chmod -R 750 storage


# -----------------------------------------------------------------------------
# 9.2. CREAR .env.production
# -----------------------------------------------------------------------------

umask 077
touch .env.production
chmod 600 .env.production

# Generar nuevas claves.
# No reutilizar las credenciales publicadas previamente.
openssl rand -hex 32
openssl rand -base64 36

nano .env.production

# Ejemplo:
#
# APP_ENV=production
# APP_DOMAIN=gestion.dominio.com
#
# POSTGRES_USER=gestion_docente_app
# POSTGRES_PASSWORD=CLAVE_POSTGRES_NUEVA
# POSTGRES_DB=gestion_docente
#
# DATABASE_URL=postgresql+psycopg://gestion_docente_app:CLAVE_POSTGRES_NUEVA@postgres_db:5432/gestion_docente
#
# JWT_SECRET_KEY=CLAVE_JWT_NUEVA
# JWT_ALGORITHM=HS256
# JWT_EXPIRE_MINUTES=480
#
# FRONTEND_URL=https://gestion.dominio.com
# CORS_ORIGINS=https://gestion.dominio.com
#
# INITIAL_ADMIN_USERNAME=admin
# INITIAL_ADMIN_EMAIL=admin@dominio.com
# INITIAL_ADMIN_PASSWORD=CLAVE_TEMPORAL_SEGURA
#
# INITIAL_DIRECTOR_USERNAME=wilman
# INITIAL_DIRECTOR_EMAIL=director@dominio.com
# INITIAL_DIRECTOR_PASSWORD=CLAVE_TEMPORAL_SEGURA
#
# SMTP_HOST=
# SMTP_PORT=587
# SMTP_USER=
# SMTP_PASSWORD=
# SMTP_FROM=
# SMTP_USE_TLS=true


# -----------------------------------------------------------------------------
# 9.3. VALIDAR COMPOSE
# -----------------------------------------------------------------------------

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  config --quiet

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  config > /tmp/informe-gestion-compose.yaml

# Revisar puertos.
grep -nE 'ports:|5432:|8000:|5173:|8080:' \
  /tmp/informe-gestion-compose.yaml

# No deben aparecer puertos públicos en esta aplicación.


# -----------------------------------------------------------------------------
# 9.4. CONSTRUIR IMÁGENES
# -----------------------------------------------------------------------------

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  build --pull


# -----------------------------------------------------------------------------
# 9.5. LEVANTAR POSTGRESQL
# -----------------------------------------------------------------------------

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d postgres_db

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps


# -----------------------------------------------------------------------------
# 9.6. EJECUTAR MIGRACIONES
# -----------------------------------------------------------------------------

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend alembic upgrade head

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend alembic current


# -----------------------------------------------------------------------------
# 9.7. CREAR DATOS INICIALES
# -----------------------------------------------------------------------------

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend python scripts/init_db.py


# -----------------------------------------------------------------------------
# 9.8. LEVANTAR TODA LA APLICACIÓN
# -----------------------------------------------------------------------------

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d --build --remove-orphans

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps


# -----------------------------------------------------------------------------
# 9.9. REVISAR LOGS
# -----------------------------------------------------------------------------

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs --tail=150 postgres_db backend gateway


# =============================================================================
# PARTE 10. CONFIGURAR HTTPS
# =============================================================================

cd /opt/apps/proxy

docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email CORREO_SSL \
  --agree-tos \
  --no-eff-email \
  -d gestion.dominio.com


# -----------------------------------------------------------------------------
# 10.1. REEMPLAZAR CONFIGURACIÓN HTTP POR HTTPS
# -----------------------------------------------------------------------------

cat > nginx/conf.d/gestion.conf <<'EOF'
server {
    listen 80;
    server_name gestion.dominio.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}


server {
    listen 443 ssl;
    http2 on;

    server_name gestion.dominio.com;

    ssl_certificate \
        /etc/letsencrypt/live/gestion.dominio.com/fullchain.pem;

    ssl_certificate_key \
        /etc/letsencrypt/live/gestion.dominio.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;

    server_tokens off;

    client_max_body_size 50M;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location / {
        proxy_pass http://gestion_gateway:80;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        proxy_connect_timeout 30s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
EOF

docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload

curl -I https://gestion.dominio.com
curl -fsS https://gestion.dominio.com/api/health


# =============================================================================
# PARTE 11. RENOVACIÓN DE CERTIFICADOS
# =============================================================================

docker compose run --rm certbot renew --dry-run

sudo crontab -e

# Agregar:
#
# 17 3 * * * cd /opt/apps/proxy && /usr/bin/docker compose run --rm certbot renew --quiet && /usr/bin/docker compose exec -T nginx nginx -s reload


# =============================================================================
# PARTE 12. BACKUP DE INFORME DE GESTIÓN
# =============================================================================

sudo mkdir -p /var/backups/apps/informe-de-gestion
sudo chmod 700 /var/backups/apps/informe-de-gestion

cd /opt/apps/informe-de-gestion

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T postgres_db \
  pg_dump \
  -U gestion_docente_app \
  -d gestion_docente \
  -Fc \
  > "/var/backups/apps/informe-de-gestion/gestion_$(date +%Y%m%d_%H%M%S).dump"

ls -lh /var/backups/apps/informe-de-gestion


# =============================================================================
# PARTE 13. EJEMPLO DE UNA SEGUNDA APLICACIÓN: INVENTARIO
# =============================================================================
#
# Suposiciones:
#
# Dominio:
# inventario.dominio.com
#
# Nombre Compose:
# inventario
#
# Alias del gateway:
# inventario_gateway
#
# Base:
# inventario_db
#
# Usuario PostgreSQL:
# inventario_app
#
# Directorio:
# /opt/apps/inventario
#
# El compose del segundo proyecto debe usar:
#
# gateway:
#   networks:
#     proxy_public:
#       aliases:
#         - inventario_gateway
#
# Nunca debe reutilizar gestion_gateway.


# -----------------------------------------------------------------------------
# 13.1. CLONAR SEGUNDO PROYECTO
# -----------------------------------------------------------------------------

cd /opt/apps/inventario

git clone URL_REPOSITORIO_INVENTARIO .


# -----------------------------------------------------------------------------
# 13.2. CREAR SU PROPIO .env.production
# -----------------------------------------------------------------------------

umask 077
touch .env.production
chmod 600 .env.production

nano .env.production

# Ejemplo:
#
# APP_ENV=production
# APP_DOMAIN=inventario.dominio.com
#
# POSTGRES_USER=inventario_app
# POSTGRES_PASSWORD=CLAVE_DISTINTA
# POSTGRES_DB=inventario_db
#
# DATABASE_URL=postgresql+psycopg://inventario_app:CLAVE_DISTINTA@postgres_db:5432/inventario_db
#
# JWT_SECRET_KEY=JWT_COMPLETAMENTE_DISTINTO
#
# FRONTEND_URL=https://inventario.dominio.com
# CORS_ORIGINS=https://inventario.dominio.com


# -----------------------------------------------------------------------------
# 13.3. VALIDAR Y DESPLEGAR INVENTARIO
# -----------------------------------------------------------------------------

docker compose \
  -p inventario \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  config --quiet

docker compose \
  -p inventario \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  build --pull

docker compose \
  -p inventario \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d postgres_db

docker compose \
  -p inventario \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend alembic upgrade head

docker compose \
  -p inventario \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend python scripts/init_db.py

docker compose \
  -p inventario \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d --build --remove-orphans

docker compose \
  -p inventario \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps


# -----------------------------------------------------------------------------
# 13.4. AÑADIR INVENTARIO AL PROXY CENTRAL
# -----------------------------------------------------------------------------

cd /opt/apps/proxy

cat > nginx/conf.d/inventario.conf <<'EOF'
server {
    listen 80;
    server_name inventario.dominio.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://inventario_gateway:80;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload

docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email CORREO_SSL \
  --agree-tos \
  --no-eff-email \
  -d inventario.dominio.com

# Después de obtener el certificado, actualizar inventario.conf con:
#
# ssl_certificate:
# /etc/letsencrypt/live/inventario.dominio.com/fullchain.pem
#
# ssl_certificate_key:
# /etc/letsencrypt/live/inventario.dominio.com/privkey.pem
#
# Y redirigir HTTP a HTTPS igual que en gestion.conf.


# =============================================================================
# PARTE 14. ACTUALIZACIÓN SEGURA DE INFORME DE GESTIÓN
# =============================================================================

cd /opt/apps/informe-de-gestion

# 1. Backup antes de actualizar.
docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T postgres_db \
  pg_dump \
  -U gestion_docente_app \
  -d gestion_docente \
  -Fc \
  > "/var/backups/apps/informe-de-gestion/predeploy_$(date +%Y%m%d_%H%M%S).dump"

# 2. Descargar únicamente cambios confirmados.
git fetch --all --tags
git pull --ff-only origin main

# Preferiblemente desplegar etiquetas:
# git checkout v1.0.1

# 3. Validar Compose.
docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  config --quiet

# 4. Construir imágenes.
docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  build --pull

# 5. Migrar base.
docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend alembic upgrade head

# 6. Seed idempotente.
docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend python scripts/init_db.py

# 7. Recrear únicamente esta aplicación.
docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d --build --remove-orphans

# 8. Verificar.
docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs --tail=100 backend gateway

curl -fsS https://gestion.dominio.com/api/health

# El proyecto Inventario permanece funcionando durante esta actualización.


# =============================================================================
# PARTE 15. MONITOREO
# =============================================================================

docker ps
docker stats
docker system df

df -h
free -h

# Logs de Informe de Gestión:
cd /opt/apps/informe-de-gestion

docker compose \
  -p informe-gestion \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs -f

# Ctrl+C sale de los logs; no detiene los contenedores.


# =============================================================================
# PARTE 16. REGLAS CRÍTICAS DE PRODUCCIÓN
# =============================================================================
#
# 1. Nunca ejecutar en producción:
#
#    docker compose down -v
#
# El parámetro -v puede eliminar la base de datos.
#
#
# 2. Nunca publicar estos puertos:
#
#    5432 PostgreSQL
#    8000 FastAPI
#    5173 Vite
#    8080 pgAdmin
#
#
# 3. Nunca usar:
#
#    npm run dev
#    uvicorn --reload
#
#
# 4. Nunca subir a Git:
#
#    .env
#    .env.production
#    contraseñas
#    claves JWT
#    certificados
#    respaldos
#    claves SSH
#
#
# 5. Nunca usar la misma contraseña o JWT en dos proyectos.
#
#
# 6. No utilizar imágenes con :latest en producción.
#    Fijar versiones y actualizarlas de forma controlada.
#
#
# 7. Cada proyecto debe tener:
#
#    - Nombre Compose diferente.
#    - Alias de gateway diferente.
#    - Base de datos diferente.
#    - Usuario PostgreSQL diferente.
#    - Volumen diferente.
#    - Red interna diferente.
#    - JWT diferente.
#    - Backup diferente.
#
#
# 8. Solo el proxy central publica 80 y 443.
#
#
# 9. Siempre hacer backup antes de migrar o actualizar.
#
#
# 10. Siempre probar:
#
#    - /api/health
#    - Login
#    - Roles
#    - Permisos
#    - Carga y descarga de archivos
#    - Persistencia después de reiniciar
#    - Restauración de backup
#
#
# 11. Los directorios:
#
#    documentos/
#    entregas_docentes/
#    evidencias_tareas/
#    repositorio_asignaturas/
#
# deben persistir fuera de la imagen si contienen archivos cargados por usuarios.
#
#
# 12. Rotar las contraseñas y JWT que hayan sido compartidos anteriormente.
#
#
# 13. Verificar después de cada despliegue:
#
#    docker compose ps
#    docker compose logs
#    docker stats
#    df -h
#    curl https://DOMINIO/api/health
#
#
# =============================================================================
# RESULTADO FINAL
# =============================================================================
#
# Proyecto 1:
#
# /opt/apps/informe-de-gestion
# Compose: informe-gestion
# Dominio: gestion.dominio.com
# Gateway: gestion_gateway
# Base: gestion_docente
# Usuario DB: gestion_docente_app
#
#
# Proyecto 2:
#
# /opt/apps/inventario
# Compose: inventario
# Dominio: inventario.dominio.com
# Gateway: inventario_gateway
# Base: inventario_db
# Usuario DB: inventario_app
#
#
# Infraestructura compartida:
#
# /opt/apps/proxy
# Red externa: proxy_public
# Puertos públicos: 80 y 443
#
# Esta separación permite actualizar, reiniciar, respaldar o restaurar una
# aplicación sin afectar las demás aplicaciones alojadas en el VPS.
# =============================================================================