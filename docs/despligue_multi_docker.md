# =============================================================================
# RECOMENDACIÓN Y ARQUITECTURA PROFESIONAL
# VARIOS PROYECTOS EN UN MISMO VPS CON DOCKER COMPOSE
#
# Recomendación:
# - Usar Docker Compose en producción.
# - Un proyecto Compose independiente por aplicación.
# - Un proxy inverso central para todos los dominios.
# - Una base de datos separada por proyecto.
# - Volúmenes, redes, secretos y backups independientes.
# - Solo exponer públicamente los puertos 80 y 443.
# =============================================================================


# -----------------------------------------------------------------------------
# 1. ESTRUCTURA RECOMENDADA EN EL VPS
# -----------------------------------------------------------------------------

/opt/apps/
├── proxy/
│   ├── compose.yaml
│   ├── nginx/
│   ├── letsencrypt/
│   └── .env
│
├── gestion-docente/
│   ├── compose.yaml
│   ├── compose.prod.yaml
│   ├── .env.production
│   ├── backend/
│   ├── frontend/
│   ├── scripts/
│   ├── alembic/
│   └── backups/
│
├── inventario/
│   ├── compose.yaml
│   ├── compose.prod.yaml
│   ├── .env.production
│   ├── backend/
│   ├── frontend/
│   ├── scripts/
│   ├── alembic/
│   └── backups/
│
└── analitica/
    ├── compose.yaml
    ├── compose.prod.yaml
    ├── .env.production
    ├── backend/
    ├── frontend/
    ├── scripts/
    ├── alembic/
    └── backups/


# -----------------------------------------------------------------------------
# 2. PRINCIPIO DE AISLAMIENTO
# -----------------------------------------------------------------------------
#
# Cada proyecto debe tener:
#
# - Nombre Compose independiente.
# - Red Docker independiente.
# - Volúmenes independientes.
# - Base de datos independiente.
# - Usuario PostgreSQL independiente.
# - Contraseña independiente.
# - JWT_SECRET_KEY independiente.
# - Archivo .env.production independiente.
# - Migraciones independientes.
# - Backups independientes.
# - Healthchecks independientes.
# - Límites de CPU y memoria propios.
#
# No compartir:
#
# - Base de datos.
# - Usuario de base de datos.
# - Contraseñas.
# - Volúmenes.
# - Redes internas.
# - Variables de entorno.
# - Claves JWT.


# -----------------------------------------------------------------------------
# 3. ARQUITECTURA GENERAL
# -----------------------------------------------------------------------------
#
# Internet
#    │
#    ▼
# Proxy inverso central
#    │
#    ├── gestion.midominio.com
#    │        └── gestion-docente
#    │
#    ├── inventario.midominio.com
#    │        └── inventario
#    │
#    └── analitica.midominio.com
#             └── analitica
#
# Cada aplicación contiene:
#
# - Frontend React compilado.
# - Backend FastAPI.
# - PostgreSQL propio o base propia.
# - Red interna.
# - Volúmenes persistentes.
# - Migraciones Alembic.
# - Script de seed idempotente.


# -----------------------------------------------------------------------------
# 4. PREPARAR EL VPS
# -----------------------------------------------------------------------------

ssh wilman@IP_PUBLICA_DEL_VPS

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
# 5. CONFIGURAR FIREWALL
# -----------------------------------------------------------------------------

sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

sudo ufw default deny incoming
sudo ufw default allow outgoing

sudo ufw enable
sudo ufw status verbose

# No publicar:
#
# 5432 PostgreSQL
# 8000 Backend
# 8080 pgAdmin
# 5173 Vite
#
# Solo publicar:
#
# 22 SSH
# 80 HTTP
# 443 HTTPS


# -----------------------------------------------------------------------------
# 6. INSTALAR DOCKER Y DOCKER COMPOSE
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

exit


# -----------------------------------------------------------------------------
# 7. VOLVER A INGRESAR
# -----------------------------------------------------------------------------

ssh wilman@IP_PUBLICA_DEL_VPS

docker version
docker compose version


# -----------------------------------------------------------------------------
# 8. CREAR ESTRUCTURA DE DIRECTORIOS
# -----------------------------------------------------------------------------

sudo mkdir -p /opt/apps/proxy
sudo mkdir -p /opt/apps/gestion-docente
sudo mkdir -p /opt/apps/inventario
sudo mkdir -p /opt/apps/analitica

sudo chown -R "$USER":"$USER" /opt/apps
sudo chmod -R 750 /opt/apps


# -----------------------------------------------------------------------------
# 9. CREAR RED EXTERNA DEL PROXY
# -----------------------------------------------------------------------------

docker network create proxy_public

# Esta red será compartida únicamente entre:
#
# - Proxy inverso.
# - Frontend o gateway de cada aplicación.
#
# Las bases de datos no deben conectarse a proxy_public.


# -----------------------------------------------------------------------------
# 10. DESPLEGAR PROXY INVERSO CENTRAL
# -----------------------------------------------------------------------------
#
# Puede utilizar:
#
# - Nginx Proxy Manager.
# - Traefik.
# - Nginx configurado manualmente.
#
# Recomendación práctica:
# - Traefik o Nginx Proxy Manager para varios proyectos.
# - Nginx manual si se desea control total.


cd /opt/apps/proxy

nano compose.yaml

# Ejemplo conceptual con Nginx Proxy Manager:
#
# services:
#   proxy:
#     image: jc21/nginx-proxy-manager:VERSION_FIJA
#     container_name: proxy_manager
#     restart: unless-stopped
#     ports:
#       - "80:80"
#       - "443:443"
#       - "127.0.0.1:8181:81"
#     volumes:
#       - ./data:/data
#       - ./letsencrypt:/etc/letsencrypt
#     networks:
#       - proxy_public
#
# networks:
#   proxy_public:
#     external: true
#
# Importante:
# - Fijar una versión, no usar latest.
# - El puerto administrativo debe quedar ligado a 127.0.0.1.
# - No publicar el panel directamente a Internet.


docker compose up -d

docker compose ps


# -----------------------------------------------------------------------------
# 11. CLONAR CADA PROYECTO
# -----------------------------------------------------------------------------

cd /opt/apps/gestion-docente
git clone URL_REPOSITORIO_GESTION_DOCENTE .

cd /opt/apps/inventario
git clone URL_REPOSITORIO_INVENTARIO .

cd /opt/apps/analitica
git clone URL_REPOSITORIO_ANALITICA .


# -----------------------------------------------------------------------------
# 12. CREAR VARIABLES DE PRODUCCIÓN POR PROYECTO
# -----------------------------------------------------------------------------

cd /opt/apps/gestion-docente

umask 077
touch .env.production
chmod 600 .env.production

nano .env.production

# Ejemplo:
#
# COMPOSE_PROJECT_NAME=gestion_docente
# APP_ENV=production
# APP_DOMAIN=gestion.midominio.com
#
# POSTGRES_USER=gestion_docente_app
# POSTGRES_PASSWORD=CLAVE_SEGURA_EXCLUSIVA
# POSTGRES_DB=gestion_docente
#
# DATABASE_URL=postgresql+psycopg://gestion_docente_app:CLAVE_SEGURA_EXCLUSIVA@postgres_db:5432/gestion_docente
#
# JWT_SECRET_KEY=CLAVE_JWT_EXCLUSIVA
# JWT_ALGORITHM=HS256
# JWT_EXPIRE_MINUTES=480
#
# FRONTEND_URL=https://gestion.midominio.com
# CORS_ORIGINS=https://gestion.midominio.com
#
# INITIAL_ADMIN_USERNAME=admin
# INITIAL_ADMIN_EMAIL=CORREO_ADMIN
# INITIAL_ADMIN_PASSWORD=CLAVE_TEMPORAL_SEGURA
#
# INITIAL_DIRECTOR_USERNAME=wilman
# INITIAL_DIRECTOR_EMAIL=CORREO_DIRECTOR
# INITIAL_DIRECTOR_PASSWORD=CLAVE_TEMPORAL_SEGURA
#
# SMTP_HOST=
# SMTP_PORT=587
# SMTP_USER=
# SMTP_PASSWORD=
# SMTP_FROM=
# SMTP_USE_TLS=true


# Generar claves:
openssl rand -hex 32
openssl rand -base64 36


# Repetir para cada proyecto:
#
# /opt/apps/inventario/.env.production
# /opt/apps/analitica/.env.production


# -----------------------------------------------------------------------------
# 13. CONFIGURACIÓN COMPOSE POR PROYECTO
# -----------------------------------------------------------------------------
#
# Cada compose.prod.yaml debe incluir:
#
# services:
#
#   postgres_db:
#     image: postgres:16-alpine
#     restart: unless-stopped
#     environment:
#       POSTGRES_USER: ${POSTGRES_USER}
#       POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
#       POSTGRES_DB: ${POSTGRES_DB}
#     volumes:
#       - postgres_data:/var/lib/postgresql/data
#     networks:
#       - internal
#     healthcheck:
#       test:
#         [
#           "CMD-SHELL",
#           "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
#         ]
#       interval: 10s
#       timeout: 5s
#       retries: 5
#
#   backend:
#     build:
#       context: .
#       dockerfile: backend/Dockerfile
#     restart: unless-stopped
#     env_file:
#       - .env.production
#     depends_on:
#       postgres_db:
#         condition: service_healthy
#     networks:
#       - internal
#       - proxy_public
#     expose:
#       - "8000"
#     healthcheck:
#       test:
#         [
#           "CMD",
#           "python",
#           "-c",
#           "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
#         ]
#       interval: 30s
#       timeout: 5s
#       retries: 5
#     mem_limit: 768m
#     cpus: 1.0
#
#   frontend:
#     build:
#       context: ./frontend
#       dockerfile: Dockerfile
#     restart: unless-stopped
#     networks:
#       - proxy_public
#     expose:
#       - "80"
#     mem_limit: 256m
#     cpus: 0.5
#
# volumes:
#   postgres_data:
#
# networks:
#   internal:
#     internal: true
#   proxy_public:
#     external: true
#
# Importante:
#
# - No usar ports en PostgreSQL.
# - No usar ports en backend.
# - No usar ports en frontend.
# - Usar expose solamente para redes internas.
# - No incluir pgAdmin en producción.
# - No usar npm run dev.
# - No usar uvicorn --reload.


# -----------------------------------------------------------------------------
# 14. VALIDAR CADA PROYECTO
# -----------------------------------------------------------------------------

cd /opt/apps/gestion-docente

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  config --quiet

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  config > /tmp/gestion-compose-final.yaml

grep -nE 'ports:|5432|5173|8000|8080' \
  /tmp/gestion-compose-final.yaml

# Solo el proxy central debe publicar 80 y 443.


# -----------------------------------------------------------------------------
# 15. CONSTRUIR EL PROYECTO
# -----------------------------------------------------------------------------

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  build --pull


# -----------------------------------------------------------------------------
# 16. LEVANTAR POSTGRESQL DEL PROYECTO
# -----------------------------------------------------------------------------

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d postgres_db

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps


# -----------------------------------------------------------------------------
# 17. EJECUTAR MIGRACIONES
# -----------------------------------------------------------------------------

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend alembic upgrade head


# -----------------------------------------------------------------------------
# 18. EJECUTAR SEED INICIAL
# -----------------------------------------------------------------------------

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend python scripts/init_db.py

# El script debe:
#
# - Ser idempotente.
# - Crear roles.
# - Crear permisos.
# - Crear usuarios iniciales.
# - No duplicar registros.
# - No imprimir contraseñas.
# - Aplicar hash a las contraseñas.


# -----------------------------------------------------------------------------
# 19. LEVANTAR TODA LA APLICACIÓN
# -----------------------------------------------------------------------------

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d --build --remove-orphans

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps


# -----------------------------------------------------------------------------
# 20. CONFIGURAR DOMINIO EN EL PROXY
# -----------------------------------------------------------------------------
#
# Para gestion.midominio.com:
#
# Destino:
# - frontend del proyecto gestion-docente.
#
# Ruta:
# - /api → backend:8000
# - /    → frontend:80
#
# HTTPS:
# - Solicitar certificado Let's Encrypt.
# - Forzar redirección HTTP → HTTPS.
# - Activar HTTP/2 o HTTP/3 si el proxy lo permite.
#
# Repetir:
#
# inventario.midominio.com
# analitica.midominio.com


# -----------------------------------------------------------------------------
# 21. REPETIR EL DESPLIEGUE PARA CADA PROYECTO
# -----------------------------------------------------------------------------

cd /opt/apps/inventario

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


# -----------------------------------------------------------------------------
# 22. BACKUPS INDEPENDIENTES
# -----------------------------------------------------------------------------

sudo mkdir -p /var/backups/apps/gestion-docente
sudo mkdir -p /var/backups/apps/inventario
sudo mkdir -p /var/backups/apps/analitica

sudo chmod -R 700 /var/backups/apps


# Backup gestión docente:

cd /opt/apps/gestion-docente

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T postgres_db \
  pg_dump \
  -U gestion_docente_app \
  -d gestion_docente \
  -Fc \
  > "/var/backups/apps/gestion-docente/gestion_docente_$(date +%Y%m%d_%H%M%S).dump"


# Backup inventario:

cd /opt/apps/inventario

docker compose \
  -p inventario \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T postgres_db \
  pg_dump \
  -U inventario_app \
  -d inventario \
  -Fc \
  > "/var/backups/apps/inventario/inventario_$(date +%Y%m%d_%H%M%S).dump"


# -----------------------------------------------------------------------------
# 23. PROGRAMAR BACKUPS
# -----------------------------------------------------------------------------

sudo crontab -e

# Ejemplo:
#
# 10 2 * * * cd /opt/apps/gestion-docente && /usr/bin/docker compose -p gestion-docente --env-file .env.production -f compose.yaml -f compose.prod.yaml exec -T postgres_db pg_dump -U gestion_docente_app -d gestion_docente -Fc > /var/backups/apps/gestion-docente/gestion_docente_$(date +\%Y\%m\%d_\%H\%M\%S).dump
#
# 20 2 * * * cd /opt/apps/inventario && /usr/bin/docker compose -p inventario --env-file .env.production -f compose.yaml -f compose.prod.yaml exec -T postgres_db pg_dump -U inventario_app -d inventario -Fc > /var/backups/apps/inventario/inventario_$(date +\%Y\%m\%d_\%H\%M\%S).dump
#
# 30 2 * * * cd /opt/apps/analitica && /usr/bin/docker compose -p analitica --env-file .env.production -f compose.yaml -f compose.prod.yaml exec -T postgres_db pg_dump -U analitica_app -d analitica -Fc > /var/backups/apps/analitica/analitica_$(date +\%Y\%m\%d_\%H\%M\%S).dump
#
# 50 2 * * * find /var/backups/apps -type f -name "*.dump" -mtime +14 -delete


# -----------------------------------------------------------------------------
# 24. ACTUALIZAR UN SOLO PROYECTO
# -----------------------------------------------------------------------------

cd /opt/apps/gestion-docente

# Backup previo:

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T postgres_db \
  pg_dump \
  -U gestion_docente_app \
  -d gestion_docente \
  -Fc \
  > "/var/backups/apps/gestion-docente/predeploy_$(date +%Y%m%d_%H%M%S).dump"

# Descargar actualización:

git fetch --all --tags
git pull --ff-only origin main

# Validar:

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  config --quiet

# Construir:

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  build --pull

# Migrar:

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend alembic upgrade head

# Seed:

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend python scripts/init_db.py

# Actualizar servicios:

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d --build --remove-orphans

# Verificar:

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs --tail=100 backend

curl -fsS https://gestion.midominio.com/api/health


# -----------------------------------------------------------------------------
# 25. MONITOREO
# -----------------------------------------------------------------------------

docker ps

docker stats

df -h

free -h

docker system df

# Logs gestión docente:

cd /opt/apps/gestion-docente

docker compose \
  -p gestion-docente \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs -f

# Logs inventario:

cd /opt/apps/inventario

docker compose \
  -p inventario \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs -f


# -----------------------------------------------------------------------------
# 26. LÍMITES DE RECURSOS
# -----------------------------------------------------------------------------
#
# Cada proyecto debe limitar CPU, memoria y logs.
#
# Ejemplo:
#
# backend:
#   mem_limit: 768m
#   cpus: 1.0
#   logging:
#     driver: json-file
#     options:
#       max-size: "10m"
#       max-file: "3"
#
# frontend:
#   mem_limit: 256m
#   cpus: 0.5
#
# postgres_db:
#   mem_limit: 1g
#   cpus: 1.0
#
# Ajustar después de medir:
#
# docker stats


# -----------------------------------------------------------------------------
# 27. REGLAS OBLIGATORIAS DE PRODUCCIÓN
# -----------------------------------------------------------------------------
#
# 1. Nunca ejecutar:
#
#    docker compose down -v
#
# 2. Nunca publicar:
#
#    5432
#    8000
#    8080
#    5173
#
# 3. Nunca usar:
#
#    npm run dev
#    uvicorn --reload
#
# 4. Nunca versionar:
#
#    .env.production
#    certificados
#    backups
#    claves SSH
#
# 5. Nunca utilizar:
#
#    image: latest
#
#    Usar versiones fijas.
#
# 6. Nunca compartir:
#
#    JWT_SECRET_KEY
#    POSTGRES_PASSWORD
#    volúmenes
#    bases de datos
#    usuarios PostgreSQL
#
# 7. Siempre:
#
#    - Crear backup antes de actualizar.
#    - Ejecutar Alembic.
#    - Ejecutar seed idempotente.
#    - Verificar healthchecks.
#    - Probar login.
#    - Probar roles.
#    - Probar HTTPS.
#    - Mantener copia externa de backups.
#    - Probar restauración.
#    - Documentar versión desplegada.
#
# 8. Cada proyecto debe usar:
#
#    docker compose -p NOMBRE_PROYECTO
#
# 9. pgAdmin:
#
#    - No debe ejecutarse en producción.
#    - Si se necesita temporalmente, usar túnel SSH.
#    - Nunca publicarlo directamente.
#
# 10. El proxy:
#
#    - Es el único que publica 80 y 443.
#    - Debe administrar certificados.
#    - Debe enviar cada dominio al proyecto correcto.
#
# =============================================================================
# DECISIÓN FINAL
# =============================================================================
#
# Para varios proyectos en un mismo VPS:
#
# USAR DOCKER COMPOSE EN PRODUCCIÓN.
#
# Diseño recomendado:
#
# - Un proxy inverso central.
# - Un Compose independiente por proyecto.
# - Un nombre Compose por proyecto.
# - Una red interna por proyecto.
# - Una base de datos por proyecto.
# - Un volumen por proyecto.
# - Un archivo .env.production por proyecto.
# - Backups separados.
# - Límites de recursos.
# - Solo 80 y 443 públicos.
#
# Esta estructura reduce conflictos, facilita migraciones, permite actualizar
# una aplicación sin afectar las demás y mejora la recuperación ante fallos.
# =============================================================================