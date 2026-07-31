# =============================================================================
# DESPLIEGUE PROFESIONAL EN VPS
# React + Vite + FastAPI + PostgreSQL + Docker Compose + Nginx + HTTPS
#
# Supuestos:
# - El proyecto contiene compose.yaml y compose.prod.yaml.
# - El frontend y backend tienen Dockerfile de producción.
# - PostgreSQL no expone el puerto 5432 públicamente.
# - pgAdmin no se ejecuta en producción.
# - Alembic administra las migraciones.
# - scripts/init_db.py crea datos iniciales de forma idempotente.
# - Nginx publica únicamente los puertos 80 y 443.
#
# Sustituir:
#   USUARIO_VPS       -> usuario administrativo del VPS
#   DOMINIO           -> ejemplo: gestion.midominio.com
#   REPOSITORIO_GIT   -> URL SSH o HTTPS del repositorio
#   CORREO_SSL        -> correo para Let's Encrypt
# =============================================================================


# -----------------------------------------------------------------------------
# FASE 1. PREPARAR DNS ANTES DE INGRESAR AL VPS
# -----------------------------------------------------------------------------
# En el proveedor del dominio, crear:
#
# Tipo: A
# Nombre: gestion                 # o @ si se utilizará el dominio principal
# Valor: IP_PUBLICA_DEL_VPS
# TTL: automático
#
# Verificar desde el equipo local:
#
# nslookup DOMINIO
#
# El resultado debe mostrar la IP pública del VPS.


# -----------------------------------------------------------------------------
# FASE 2. CONECTARSE AL VPS
# -----------------------------------------------------------------------------

ssh USUARIO_VPS@IP_PUBLICA_DEL_VPS


# -----------------------------------------------------------------------------
# FASE 3. ACTUALIZAR Y ASEGURAR EL SISTEMA OPERATIVO
# -----------------------------------------------------------------------------

sudo apt update
sudo apt upgrade -y

sudo apt install -y \
  ca-certificates \
  curl \
  git \
  gnupg \
  ufw \
  fail2ban \
  unattended-upgrades

# Configurar zona horaria.
sudo timedatectl set-timezone America/Bogota

# Comprobar fecha y zona horaria.
timedatectl

# Habilitar actualizaciones automáticas de seguridad.
sudo dpkg-reconfigure --priority=low unattended-upgrades


# -----------------------------------------------------------------------------
# FASE 4. CONFIGURAR FIREWALL
# -----------------------------------------------------------------------------
# Abrir SSH antes de habilitar UFW para evitar perder la conexión.

sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable

sudo ufw status verbose

# IMPORTANTE:
# El compose de producción NO debe publicar:
#   5432 PostgreSQL
#   8000 FastAPI
#   8080 pgAdmin
#
# Solo Nginx debe publicar 80 y 443.
#
# Docker puede administrar reglas que no siempre quedan bloqueadas únicamente
# por UFW. La protección principal consiste en no declarar esos puertos en
# compose.prod.yaml.


# -----------------------------------------------------------------------------
# FASE 5. INSTALAR DOCKER DESDE EL REPOSITORIO OFICIAL
# -----------------------------------------------------------------------------

# Eliminar paquetes que puedan entrar en conflicto.
sudo apt remove -y \
  docker.io \
  docker-compose \
  docker-compose-v2 \
  docker-doc \
  podman-docker \
  containerd \
  runc 2>/dev/null || true

# Agregar la clave oficial de Docker.
sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL \
  https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc

# Agregar el repositorio oficial.
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

# Habilitar Docker al iniciar el VPS.
sudo systemctl enable --now docker

# Verificar instalación.
sudo docker run --rm hello-world
sudo docker version
sudo docker compose version


# -----------------------------------------------------------------------------
# FASE 6. CONFIGURAR USUARIO DE DESPLIEGUE
# -----------------------------------------------------------------------------
# Agregar el usuario actual al grupo docker.
# ADVERTENCIA: pertenecer al grupo docker concede privilegios elevados.

sudo usermod -aG docker "$USER"

# Aplicar el grupo sin cerrar completamente la sesión.
newgrp docker

# Comprobar acceso.
docker ps


# -----------------------------------------------------------------------------
# FASE 7. CREAR DIRECTORIO SEGURO PARA LA APLICACIÓN
# -----------------------------------------------------------------------------

sudo mkdir -p /opt/informe-de-gestion
sudo chown -R "$USER":"$USER" /opt/informe-de-gestion
sudo chmod 750 /opt/informe-de-gestion

cd /opt/informe-de-gestion


# -----------------------------------------------------------------------------
# FASE 8. DESCARGAR EL PROYECTO
# -----------------------------------------------------------------------------
# Recomendado: repositorio privado y autenticación mediante clave SSH de
# despliegue. No almacenar tokens dentro del proyecto.

git clone REPOSITORIO_GIT .

# Cambiar a una rama o etiqueta estable.
git fetch --all --tags
git checkout main

# Verificar estado.
git status
git log -1 --oneline


# -----------------------------------------------------------------------------
# FASE 9. CREAR EL ARCHIVO DE VARIABLES DE PRODUCCIÓN
# -----------------------------------------------------------------------------
# Nunca copiar contraseñas de desarrollo.
# Nunca versionar este archivo.
# No utilizar contraseñas como secret123 o admin123.

umask 077
touch .env.production
chmod 600 .env.production

# Generar secretos.
openssl rand -hex 32
openssl rand -base64 36
openssl rand -base64 36

# Editar el archivo.
nano .env.production

# Contenido de referencia:
#
# APP_ENV=production
# APP_DOMAIN=DOMINIO
#
# POSTGRES_USER=gestion_docente_app
# POSTGRES_PASSWORD=CONTRASENA_POSTGRES_MUY_SEGURA
# POSTGRES_DB=gestion_docente
#
# Dentro de Docker el host debe ser postgres_db, no localhost:
# DATABASE_URL=postgresql+psycopg://gestion_docente_app:CONTRASENA_URL_ENCODED@postgres_db:5432/gestion_docente
#
# JWT_SECRET_KEY=CLAVE_ALEATORIA_DE_AL_MENOS_64_CARACTERES
# JWT_ALGORITHM=HS256
# JWT_EXPIRE_MINUTES=480
#
# FRONTEND_URL=https://DOMINIO
# CORS_ORIGINS=https://DOMINIO
#
# INITIAL_ADMIN_USERNAME=admin
# INITIAL_ADMIN_EMAIL=CORREO_ADMINISTRADOR
# INITIAL_ADMIN_PASSWORD=CONTRASENA_TEMPORAL_SEGURA
#
# INITIAL_DIRECTOR_USERNAME=wilman
# INITIAL_DIRECTOR_EMAIL=CORREO_DIRECTOR
# INITIAL_DIRECTOR_PASSWORD=CONTRASENA_TEMPORAL_SEGURA
#
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=CORREO_SMTP
# SMTP_PASSWORD=CONTRASENA_DE_APLICACION
# SMTP_FROM=CORREO_REMITENTE
# SMTP_USE_TLS=true
#
# LETSENCRYPT_EMAIL=CORREO_SSL
#
# Las cuentas iniciales deben requerir cambio de contraseña en el primer acceso.

# Verificar permisos sin mostrar el contenido.
ls -l .env.production


# -----------------------------------------------------------------------------
# FASE 10. VALIDAR LA CONFIGURACIÓN DE DOCKER COMPOSE
# -----------------------------------------------------------------------------
# La configuración resultante debe cumplir:
#
# - postgres_db sin "ports" en producción.
# - backend sin "ports" públicos.
# - pgAdmin ausente o deshabilitado.
# - nginx publica solamente 80 y 443.
# - DATABASE_URL usa postgres_db.
# - No existen montajes del código fuente.
# - No se utiliza --reload.
# - Existen healthchecks.
# - Existen políticas de reinicio.
# - Los contenedores no ejecutan como root cuando sea posible.
# - Los logs tienen límites de tamaño.

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  config > /tmp/compose-final.yaml

# Revisar cuidadosamente antes de desplegar.
less /tmp/compose-final.yaml

# Comprobar los puertos publicados.
grep -nE "ports:|5432|8000|8080|80:|443:" /tmp/compose-final.yaml


# -----------------------------------------------------------------------------
# FASE 11. CONSTRUIR LAS IMÁGENES
# -----------------------------------------------------------------------------

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  build --pull

# Ver imágenes.
docker images


# -----------------------------------------------------------------------------
# FASE 12. LEVANTAR PRIMERO POSTGRESQL
# -----------------------------------------------------------------------------

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d postgres_db

# Verificar estado.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps

# Revisar logs sin mostrar secretos.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs --tail=100 postgres_db

# Esperar hasta que PostgreSQL esté saludable.
until docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T postgres_db pg_isready \
    -U gestion_docente_app \
    -d gestion_docente
do
  echo "Esperando PostgreSQL..."
  sleep 3
done


# -----------------------------------------------------------------------------
# FASE 13. EJECUTAR MIGRACIONES
# -----------------------------------------------------------------------------
# No usar Base.metadata.create_all() como sustituto de Alembic en producción.

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend alembic upgrade head

# Confirmar versión aplicada.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend alembic current


# -----------------------------------------------------------------------------
# FASE 14. EJECUTAR SEED INICIAL
# -----------------------------------------------------------------------------
# El script debe ser idempotente:
# - No duplica roles.
# - No duplica permisos.
# - No duplica usuarios.
# - No imprime contraseñas.
# - Utiliza el mismo hash del sistema de autenticación.

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend python scripts/init_db.py


# -----------------------------------------------------------------------------
# FASE 15. LEVANTAR EL BACKEND Y VERIFICAR SALUD
# -----------------------------------------------------------------------------

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d backend

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs --tail=100 backend

# Probar el endpoint desde la red interna de Docker.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T backend \
  python -c "
import urllib.request
response = urllib.request.urlopen('http://127.0.0.1:8000/api/health')
print(response.status, response.read().decode())
"


# -----------------------------------------------------------------------------
# FASE 16. LEVANTAR FRONTEND Y NGINX
# -----------------------------------------------------------------------------

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d frontend nginx

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs --tail=100 frontend nginx


# -----------------------------------------------------------------------------
# FASE 17. OBTENER CERTIFICADO HTTPS
# -----------------------------------------------------------------------------
# Esta sección presupone que Claude configuró:
#
# - nginx escuchando inicialmente en el puerto 80.
# - ubicación /.well-known/acme-challenge/.
# - volumen compartido entre Nginx y Certbot.
# - servicio certbot en compose.prod.yaml.
#
# Confirmar primero que el dominio responde por HTTP:
curl -I "http://DOMINIO"

# Solicitar certificado por primera vez.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email CORREO_SSL \
  --agree-tos \
  --no-eff-email \
  -d DOMINIO

# Validar configuración de Nginx.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T nginx nginx -t

# Recargar Nginx.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T nginx nginx -s reload

# Verificar redirección y HTTPS.
curl -I "http://DOMINIO"
curl -I "https://DOMINIO"
curl -fsS "https://DOMINIO/api/health"


# -----------------------------------------------------------------------------
# FASE 18. RENOVACIÓN AUTOMÁTICA DEL CERTIFICADO
# -----------------------------------------------------------------------------
# Si compose.prod.yaml ya tiene un servicio Certbot con ciclo de renovación,
# verificar sus logs. En caso contrario, crear una tarea cron.

sudo crontab -e

# Agregar, ajustando la ruta:
#
# 17 3 * * * cd /opt/informe-de-gestion && /usr/bin/docker compose --env-file .env.production -f compose.yaml -f compose.prod.yaml run --rm certbot renew --quiet && /usr/bin/docker compose --env-file .env.production -f compose.yaml -f compose.prod.yaml exec -T nginx nginx -s reload
#
# Probar renovación sin modificar certificados:
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm certbot renew --dry-run


# -----------------------------------------------------------------------------
# FASE 19. REALIZAR PRUEBAS FUNCIONALES
# -----------------------------------------------------------------------------

# Salud pública.
curl -fsS "https://DOMINIO/api/health"

# Encabezados HTTP.
curl -I "https://DOMINIO"

# Verificar contenedores.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps

# Verificar que no haya servicios internos publicados.
sudo ss -lntp

# Externamente solo deberían estar disponibles:
# - 22/tcp SSH
# - 80/tcp HTTP
# - 443/tcp HTTPS

# Probar manualmente:
# 1. Abrir https://DOMINIO.
# 2. Iniciar sesión con el usuario administrador.
# 3. Cambiar inmediatamente la contraseña temporal.
# 4. Iniciar sesión con el usuario director.
# 5. Cambiar inmediatamente la contraseña temporal.
# 6. Verificar roles y permisos.
# 7. Crear un registro de prueba.
# 8. Cerrar sesión.
# 9. Verificar recuperación de contraseña.
# 10. Confirmar que /docs no esté expuesto públicamente si se deshabilitó.


# -----------------------------------------------------------------------------
# FASE 20. CONFIGURAR BACKUPS DE POSTGRESQL
# -----------------------------------------------------------------------------

sudo mkdir -p /var/backups/informe-de-gestion
sudo chmod 700 /var/backups/informe-de-gestion

# Ejecutar el script creado por Claude.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T postgres_db \
  pg_dump \
    -U gestion_docente_app \
    -d gestion_docente \
    -Fc \
  > "/var/backups/informe-de-gestion/gestion_docente_$(date +%Y%m%d_%H%M%S).dump"

# Verificar que el archivo no esté vacío.
ls -lh /var/backups/informe-de-gestion

# Automatizar respaldo diario.
sudo crontab -e

# Ejemplo de tarea diaria a las 2:15 a. m.:
#
# 15 2 * * * cd /opt/informe-de-gestion && /usr/bin/docker compose --env-file .env.production -f compose.yaml -f compose.prod.yaml exec -T postgres_db pg_dump -U gestion_docente_app -d gestion_docente -Fc > /var/backups/informe-de-gestion/gestion_docente_$(date +\%Y\%m\%d_\%H\%M\%S).dump
#
# Eliminar respaldos locales de más de 14 días:
#
# 45 2 * * * find /var/backups/informe-de-gestion -type f -name "*.dump" -mtime +14 -delete
#
# BUENA PRÁCTICA:
# Mantener otra copia cifrada fuera del VPS. Un respaldo alojado únicamente
# en el mismo servidor no protege frente a pérdida total del VPS.


# -----------------------------------------------------------------------------
# FASE 21. VERIFICAR REINICIO AUTOMÁTICO
# -----------------------------------------------------------------------------

sudo reboot

# Volver a ingresar después del reinicio.
ssh USUARIO_VPS@IP_PUBLICA_DEL_VPS

cd /opt/informe-de-gestion

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps

curl -fsS "https://DOMINIO/api/health"


# -----------------------------------------------------------------------------
# FASE 22. PROCEDIMIENTO PROFESIONAL PARA ACTUALIZACIONES
# -----------------------------------------------------------------------------

cd /opt/informe-de-gestion

# 1. Crear respaldo antes de actualizar.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  exec -T postgres_db \
  pg_dump \
    -U gestion_docente_app \
    -d gestion_docente \
    -Fc \
  > "/var/backups/informe-de-gestion/predeploy_$(date +%Y%m%d_%H%M%S).dump"

# 2. Descargar cambios.
git fetch --all --tags
git pull --ff-only origin main

# Preferiblemente desplegar una etiqueta concreta:
# git checkout v1.0.1

# 3. Validar Compose.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  config --quiet

# 4. Construir imágenes nuevas.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  build --pull

# 5. Ejecutar migraciones antes de recrear toda la aplicación.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend alembic upgrade head

# 6. Ejecutar seed idempotente.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  run --rm backend python scripts/init_db.py

# 7. Recrear servicios sin borrar volúmenes.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  up -d --build --remove-orphans

# 8. Verificar estado y logs.
docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  ps

docker compose \
  --env-file .env.production \
  -f compose.yaml \
  -f compose.prod.yaml \
  logs --tail=100 backend nginx

curl -fsS "https://DOMINIO/api/health"

# 9. Eliminar imágenes no utilizadas únicamente después de comprobar el sistema.
docker image prune -f


# -----------------------------------------------------------------------------
# FASE 23. REGLAS DE PRODUCCIÓN QUE NUNCA SE DEBEN INCUMPLIR
# -----------------------------------------------------------------------------
#
# 1. Nunca ejecutar:
#       docker compose down -v
#    en producción. El parámetro -v elimina los volúmenes y puede borrar la BD.
#
# 2. Nunca versionar:
#       .env
#       .env.production
#       certificados
#       respaldos
#       claves SSH
#
# 3. Nunca publicar PostgreSQL en:
#       0.0.0.0:5432
#
# 4. Nunca exponer pgAdmin públicamente.
#
# 5. Nunca utilizar:
#       uvicorn --reload
#       npm run dev
#    en producción.
#
# 6. Nunca insertar contraseñas directamente mediante SQL sin hash.
#
# 7. Nunca desplegar sin:
#       backup
#       migraciones
#       healthcheck
#       prueba funcional
#
# 8. Nunca usar la rama de trabajo sin identificar la versión desplegada.
#    Usar etiquetas:
#       git tag v1.0.0
#       git push origin v1.0.0
#
# 9. Rotar inmediatamente cualquier clave que haya sido compartida,
#    publicada o incluida accidentalmente en Git.
#
# 10. Probar periódicamente la restauración de los respaldos.
#
# 11. Supervisar:
#       docker compose ps
#       docker stats
#       espacio disponible con df -h
#       logs
#       fecha de vencimiento del certificado
#       respaldos
#
# 12. Mantener documentado:
#       versión desplegada
#       fecha del despliegue
#       migraciones ejecutadas
#       responsable
#       resultado de las pruebas
#       procedimiento de reversión
#
# =============================================================================
# FIN DEL PROCEDIMIENTO
# =============================================================================