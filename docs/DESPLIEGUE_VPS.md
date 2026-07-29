# Manual de despliegue en VPS (Hetzner) — Sistema de Gestión y Autoevaluación Docente

Guía paso a paso para publicar este proyecto en tu VPS de Hetzner, bajo un subdominio
de `pisunpa.com`, con SSL, y de forma que **conviva de forma segura y ordenada con
los demás proyectos** que vas a montar en el mismo servidor.

Convenciones usadas en esta guía:
- `<usuario_ssh>`: tu usuario de conexión SSH al VPS (no root).
- `<subdominio>`: el subdominio que le asignes a este proyecto (ver sección 1).
- Todo lo que empieza con `sudo` se ejecuta **en el VPS**, por SSH — nunca en tu PC.
- Reemplaza cualquier contraseña/clave de ejemplo por una generada de verdad.

---

## 0. Antes de empezar: decide dónde vive cada cosa

Como vas a montar **varios proyectos en el mismo VPS**, la decisión más importante
antes de tocar el servidor es adoptar una convención fija y no salirte de ella
proyecto tras proyecto. Con eso resuelves de una vez los tres problemas típicos de
"varios proyectos en un solo servidor": choque de puertos, choque de nombres de
base de datos, y no saber qué servicio pertenece a qué proyecto cuando algo falla.

### 1.1 Subdominios, no rutas

Con un dominio propio (`pisunpa.com`) lo correcto es **un subdominio por proyecto**,
nunca varios proyectos bajo rutas distintas del mismo dominio (`pisunpa.com/app1`,
`pisunpa.com/app2`). Motivo práctico: cada proyecto (React) asume que es dueño de
`/` y de `/api`; meterlo bajo una subruta obliga a reescribir el `base` de Vite,
las cookies, y las rutas del router en cada proyecto. Con subdominios cada Nginx
`server {}` es independiente y cada proyecto no sabe (ni le importa) que existen
los demás.

Ejemplo para este proyecto — recomendado: **`gestion.pisunpa.com`**
(deja `pisunpa.com` / `www.pisunpa.com` libres para tu sistema de egresados u otro
proyecto que ya tengas ahí).

En tu proveedor DNS, crea un registro:
```
Tipo A     gestion.pisunpa.com     ->  <IP pública del VPS>
```
(o `CNAME` a `pisunpa.com` si ya apunta a la misma IP). Espera a que propague
(minutos a un par de horas) antes de pedir el certificado SSL en el paso 8.

### 1.2 Un puerto fijo por proyecto (nunca "el puerto por defecto")

Streamlit usa el puerto `8501` por defecto y FastAPI/uvicorn no tiene "el suyo" —
si dejas que cada proyecto use los valores por defecto, el segundo proyecto que
montes chocará con el primero. Lleva un registro simple, por ejemplo un archivo
`/srv/PUERTOS.md` en el servidor:

| Proyecto                          | Backend (uvicorn) | Streamlit | Base de datos     |
|------------------------------------|:------------------:|:---------:|--------------------|
| gestion-docente (este proyecto)    | 8001                | 8501      | `gestion_docente`  |
| (tu próximo proyecto)              | 8002                | 8502      | `otro_proyecto`     |

Ninguno de estos puertos se expone a Internet directamente — todos quedan atados a
`127.0.0.1` y solo Nginx (que sí escucha en 80/443) los alcanza. Esto es importante
para la seguridad: si el firewall llegara a fallar, el backend y Streamlit igual
serían inalcanzables desde fuera del propio servidor.

### 1.3 Una carpeta por proyecto, mismo patrón siempre

```
/srv/apps/
├── gestion-docente/        <- este proyecto
│   ├── repo/               <- código (git clone aquí)
│   ├── entregas_docentes/  <- archivos subidos (fuera del repo, ver 1.4)
│   └── repositorio_asignaturas/
├── otro-proyecto/
│   └── repo/
└── PUERTOS.md
```

### 1.4 Los archivos que suben los docentes NO van dentro del repo

`agente_notas/almacenamiento.py` guarda los archivos en `entregas_docentes/` y
`repositorio_asignaturas/`, relativos a la raíz del proyecto. Son datos reales de
docentes (documentos firmados, sílabos) — **no se versionan** (ya están en
`.gitignore`) y **no se deben borrar/sobrescribir** en cada actualización de código.
Dos opciones, cualquiera sirve:
- Dejarlos tal cual dentro de `repo/` (el `git pull` de una actualización no los
  toca porque están ignorados) — más simple, suficiente para el piloto.
- O moverlos fuera del repo con un symlink, si más adelante quieres poder borrar y
  reclonar `repo/` sin miedo:
  `ln -s /srv/apps/gestion-docente/entregas_docentes /srv/apps/gestion-docente/repo/entregas_docentes`

De cualquier forma, esta carpeta es la que debes incluir en tus backups (sección 12).

----------

## 1. Preparación inicial del servidor (una sola vez para todo el VPS)

Si el VPS ya tiene otros proyectos corriendo, probablemente ya hiciste esto —
revísalo como checklist en vez de repetirlo a ciegas.

```bash
# Conéctate por SSH y actualiza el sistema
sudo apt update && sudo apt upgrade -y

# Usuario sin privilegios para desplegar (si no existe ya uno)
sudo adduser deploy
sudo usermod -aG sudo deploy
# A partir de aqui, conectate como "deploy", no como root.

# Firewall: solo SSH, HTTP y HTTPS abiertos al mundo
sudo apt install -y ufw
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status

# Fail2ban: bloquea IPs que fuerzan el SSH
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban

# Actualizaciones de seguridad automáticas del sistema operativo
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

**Rotación de logs**: los servicios de systemd (backend y Streamlit, sección 7) no
definen su propio archivo de log — van al `journal` de systemd, compartido por
todo el VPS entre todos los proyectos. Confirma (o fija explícitamente) un límite
de tamaño para que no crezca sin control a medida que aumenta el tráfico:
```bash
sudo nano /etc/systemd/journald.conf
# Descomenta y ajusta:
#   SystemMaxUse=500M
sudo systemctl restart systemd-journald
```

**SSH endurecido** (si aún no lo hiciste): en `/etc/ssh/sshd_config`, confirma:
```
PermitRootLogin no
PasswordAuthentication no
```
(esto exige que ya tengas tu clave pública en `~/.ssh/authorized_keys` del usuario
`deploy` — sin eso te quedas afuera). Luego `sudo systemctl restart sshd`.

---

## 2. Dependencias del sistema para este proyecto

```bash
# Python 3.12 (si el repo ya trae otra version del sistema, usa deadsnakes)
sudo apt install -y python3.12 python3.12-venv python3-pip

# Node.js 20 LTS (para compilar el frontend React) — via NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# PostgreSQL (si no lo tienes ya de otro proyecto, se puede compartir la
# misma instancia entre proyectos -- solo aislas por base de datos, ver 3)
sudo apt install -y postgresql postgresql-contrib

# Nginx + Certbot (SSL)
sudo apt install -y nginx certbot python3-certbot-nginx

# Git
sudo apt install -y git
```

---

## 3. Base de datos: aislada por proyecto, aunque el servidor Postgres sea compartido

Aunque reutilices el mismo Postgres para varios proyectos, **cada proyecto tiene su
propia base de datos y su propio usuario**, con permisos solo sobre su propia base
— nunca un usuario "admin" compartido entre proyectos. Así un problema en un
proyecto no puede tocar los datos del otro.

```bash
sudo -u postgres psql
```
```sql
CREATE USER gestion_docente_app WITH PASSWORD 'una-contrasena-larga-y-unica-para-este-proyecto';
CREATE DATABASE gestion_docente OWNER gestion_docente_app;
\q
```

Confirma que Postgres solo escucha en localhost (no debe ser alcanzable desde
Internet): en `/etc/postgresql/*/main/postgresql.conf`, `listen_addresses =
'localhost'`; y en `pg_hba.conf`, las líneas de `host` deben decir `127.0.0.1/32`
o `md5`/`scram-sha-256`, nunca `trust` para conexiones remotas.

---

## 4. Subir el código al servidor

```bash
sudo mkdir -p /srv/apps/gestion-docente
sudo chown deploy:deploy /srv/apps/gestion-docente
cd /srv/apps/gestion-docente

# Si el repo esta en GitHub/GitLab (privado, recomendado):
git clone git@github.com:<tu-usuario>/<tu-repo>.git repo
cd repo

# Si aun no tienes un remoto, la alternativa mas simple es empaquetar el
# proyecto en tu PC (excluyendo .venv, node_modules, __pycache__, y las
# carpetas con datos reales) y subirlo por scp/rsync una vez, y desde ahi
# ya trabajas con git normal en el servidor.
```

> Recomendación: usa un repositorio **privado**. Este proyecto maneja datos
> académicos reales y credenciales de la Universidad — nunca lo publiques en un
> repo público.

---

## 5. Backend: entorno Python + variables de entorno de producción

```bash
cd /srv/apps/gestion-docente/repo
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

`pywin32` en `requirements.txt` ya está condicionado a Windows
(`pywin32; sys_platform == "win32"`), así que en Linux `pip` simplemente lo omite
— no hay que tocar el archivo.

Crea el `.env` de producción (nunca copies el `.env` de tu PC de desarrollo, genera
uno nuevo con secretos propios del servidor):

```bash
cp .env.example .env
nano .env
```

Complétalo así:
```dotenv
DATABASE_URL=postgresql+psycopg://gestion_docente_app:<la-contrasena-del-paso-3>@localhost:5432/gestion_docente

JWT_SECRET_KEY=<genera-una-nueva-con-el-comando-de-abajo>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# SMTP: lo dejas vacío hasta que tengas el correo institucional configurado
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=notificaciones@pisunpa.com
SMTP_USE_TLS=true
```

Genera una `JWT_SECRET_KEY` **nueva y exclusiva de este servidor** (nunca la misma
que usaste en tu PC, y nunca la reutilices entre proyectos):
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Protege el archivo — solo el dueño puede leerlo:
```bash
chmod 600 .env
```

`backend/core/config.py` también trae `CORS_ORIGINS` — en producción no hace
falta tocarlo porque el frontend llama a `/api` con ruta relativa (mismo origen,
ver sección 8), pero si en el futuro otro dominio necesita llamar a esta API,
agrégalo ahí explícitamente en vez de dejarlo abierto a cualquier origen.

### 5.1 Migraciones y datos base

Este proyecto no usa Alembic — las migraciones son scripts puntuales e
idempotentes en `scripts/`. Ejecútalos **en este orden** la primera vez
(y solo los que aún no hayas corrido, si el servidor ya tenía una base parcial):

```bash
python -m db.seed                                     # roles, cortes, catálogo base
python -m scripts.migrar_periodo_anio_semestre
python -m scripts.migrar_periodo_activo_y_calendario
python -m scripts.migrar_entregas_documentos
python -m scripts.migrar_notificaciones
python -m scripts.migrar_repositorio_asignaturas
python -m scripts.migrar_consentimiento_datos
python -m scripts.migrar_auditoria_consentimiento
```

Luego crea las cuentas reales (Director, Docentes, etc.) — **no reutilices** las
del entorno de desarrollo. Puedes usar un script puntual con
`db.repository.crear_usuario` o crearlas desde la propia app una vez esté arriba
(Dirección → Administración de usuarios), usando la cuenta del Director como
primera cuenta.

---

## 6. Frontend: build de producción (nunca `npm run dev` en el servidor)

```bash
cd /srv/apps/gestion-docente/repo/frontend
npm install
npm run build
```

Esto genera `frontend/dist/` — un conjunto de archivos estáticos (HTML/JS/CSS) que
Nginx sirve directamente, sin Node corriendo en producción. Cada vez que
actualices el frontend, repites `npm run build` y Nginx sirve el resultado nuevo
sin reiniciar nada.

---

## 7. systemd: mantener el backend y Streamlit siempre corriendo

Usa `systemd` (no `nohup`, no `screen`/`tmux`) para que ambos procesos arranquen
solos al reiniciar el servidor y se reinicien solos si fallan.

### 7.1 Backend (FastAPI)

`/etc/systemd/system/gestion-docente-backend.service`:
```ini
[Unit]
Description=Gestion Docente - Backend FastAPI
After=network.target postgresql.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/srv/apps/gestion-docente/repo
Environment="PATH=/srv/apps/gestion-docente/repo/.venv/bin"
ExecStart=/srv/apps/gestion-docente/repo/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8001 --workers 4
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Notas importantes:
- **Sin `--reload`**: esa opción es solo para desarrollo (recarga en caliente, más
  lenta y menos estable). En producción, cada cambio de código se despliega
  reiniciando el servicio (sección 13).
- `--host 127.0.0.1`: el backend NO se expone directamente a Internet, solo Nginx
  lo alcanza.
- `--workers 4`: para un piloto de un solo programa con pocos docentes, 2 workers
  alcanza; pero si el plan es crecer a varios cientos de docentes usando la app a
  la vez (picos reales: fecha límite de entrega de notas), 4 workers es el mínimo
  recomendado (ver la sección "Escalamiento" del `README.md`, dimensionada para
  ~100 docentes concurrentes). Ajusta según CPUs reales del VPS (regla general:
  2×núcleos+1). Cada worker abre su propio pool de conexiones a Postgres
  (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW` en `.env`, por defecto 10+10) — con varios
  proyectos en el mismo Postgres, vigila que la suma de todos los
  `workers × (pool_size + max_overflow)` no supere el `max_connections` de
  Postgres (200 en el `docker-compose.yml` de referencia de este proyecto). Con
  4 workers de este proyecto: `4 × 20 = 80` conexiones máx. — deja margen de 120
  para los demás proyectos del mismo Postgres.
- **El limitador de intentos de login (`backend/core/rate_limit.py`) está
  respaldado en Postgres**, no en memoria del proceso — por eso es seguro subir
  `--workers` sin que el límite de intentos fallidos se vuelva más permisivo (con
  un límite en memoria, cada worker llevaría su propio contador independiente).

### 7.2 Streamlit

`/etc/systemd/system/gestion-docente-streamlit.service`:
```ini
[Unit]
Description=Gestion Docente - Streamlit
After=network.target postgresql.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/srv/apps/gestion-docente/repo
Environment="PATH=/srv/apps/gestion-docente/repo/.venv/bin"
ExecStart=/srv/apps/gestion-docente/repo/.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --server.enableCORS false --server.enableXsrfProtection true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Actívalos:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gestion-docente-backend
sudo systemctl enable --now gestion-docente-streamlit

# Verificar que arrancaron bien:
sudo systemctl status gestion-docente-backend
sudo systemctl status gestion-docente-streamlit
journalctl -u gestion-docente-backend -f     # logs en vivo (Ctrl+C para salir)
```

---

## 8. Nginx: dominio, SSL y proxy hacia backend/Streamlit/React

### 8.1 Server block (HTTP, antes de pedir el certificado)

`/etc/nginx/sites-available/gestion.pisunpa.com`:
```nginx
server {
    listen 80;
    server_name gestion.pisunpa.com;

    root /srv/apps/gestion-docente/repo/frontend/dist;
    index index.html;

    # Sin esto, Nginx rechaza CUALQUIER subida mayor a 1 MB (su límite por
    # defecto) antes de que llegue al backend -- rompería la subida de
    # documentos firmados/sílabos normales, que el backend sí permite hasta
    # 20 MB (backend/core/limite_tamano.py). Debe ser >= ese límite.
    client_max_body_size 20m;

    # API del backend (FastAPI)
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Streamlit (interfaz alternativa), bajo /streamlit/ -- necesita
    # soporte de WebSocket para funcionar (Streamlit lo usa para todo).
    location /streamlit/ {
        proxy_pass http://127.0.0.1:8501/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # React (SPA): cualquier ruta que no exista como archivo, cae a index.html
    # para que el enrutador de React (react-router-dom) la resuelva del lado
    # del cliente.
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Los archivos que Vite genera en /assets/ ya llevan un hash en el
    # nombre (p.ej. index-DlNSKjNr.css) -- si el contenido cambia, el
    # nombre cambia, así que es seguro cachearlos "para siempre" en el
    # navegador. index.html NUNCA se cachea (siempre debe revalidarse,
    # es el único archivo con nombre fijo que referencia los assets).
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    location = /index.html {
        add_header Cache-Control "no-cache";
    }

    # Cabeceras de seguridad basicas
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/gestion.pisunpa.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

> Si usas Streamlit solo internamente (no lo vas a exponer a los docentes), puedes
> omitir el bloque `location /streamlit/` por completo y dejar esa interfaz
> accesible únicamente por SSH-tunnel cuando la necesites — reduce superficie de
> ataque. Decide según cuál de las dos interfaces (React o Streamlit) es la que
> realmente van a usar los docentes en el piloto.

### 8.2 Certificado SSL (Let's Encrypt, gratis, autorrenovable)

Con el DNS ya propagado (sección 1.1) y Nginx sirviendo por HTTP:
```bash
sudo certbot --nginx -d gestion.pisunpa.com
```
Certbot reescribe el `server {}` para servir HTTPS y agrega la redirección
automática de HTTP → HTTPS. La renovación automática queda instalada como timer
de systemd — confírmalo:
```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

---

## 9. Primera verificación en el servidor real

Antes de avisarle a nadie que ya está publicado:

1. `https://gestion.pisunpa.com` carga el login de React (candado verde, sin
   advertencias de certificado).
2. Login con la cuenta real del Director → aparece el Aviso de Privacidad
   (todavía sin aceptar, es la primera vez en este servidor) → acéptalo → carga el
   dashboard.
3. Prueba subir un archivo pequeño (Entrega de documentos o Repositorio) y
   confirma que aparece en `entregas_docentes/` o `repositorio_asignaturas/` en el
   servidor (`ls -la` dentro de esas carpetas).
4. `sudo journalctl -u gestion-docente-backend -n 50` y
   `sudo journalctl -u gestion-docente-streamlit -n 50` sin errores.
5. Repite el login con una cuenta de Docente para confirmar el otro rol.

---

## 10. Backups

Lo mínimo indispensable — un cron diario que respalda la base de datos y los
archivos subidos, con unos días de retención:

`/srv/apps/gestion-docente/backup.sh`:
```bash
#!/bin/bash
set -e
FECHA=$(date +%Y-%m-%d)
DESTINO=/srv/backups/gestion-docente
mkdir -p "$DESTINO"

pg_dump -U gestion_docente_app -h localhost gestion_docente | gzip > "$DESTINO/db_$FECHA.sql.gz"

tar -czf "$DESTINO/archivos_$FECHA.tar.gz" \
  -C /srv/apps/gestion-docente/repo entregas_docentes repositorio_asignaturas

# Retener solo los ultimos 14 dias
find "$DESTINO" -type f -mtime +14 -delete
```
```bash
chmod +x /srv/apps/gestion-docente/backup.sh
crontab -e
# Agrega: 0 3 * * * /srv/apps/gestion-docente/backup.sh
```

Idealmente copia además `/srv/backups/` fuera del propio VPS de vez en cuando
(snapshot de Hetzner, o `rsync` a otra máquina) — un backup que vive solo en el
mismo disco que puede fallar no es un backup completo.

---

## 11. Actualizar el proyecto tras un cambio de código

```bash
cd /srv/apps/gestion-docente/repo
git pull

# Si cambiaron dependencias de Python:
source .venv/bin/activate && pip install -r requirements.txt

# Si hay una migracion nueva en scripts/, correla (son idempotentes)
python -m scripts.migrar_xxx

# Si cambio el frontend:
cd frontend && npm install && npm run build && cd ..

# Reiniciar los servicios que cambiaron
sudo systemctl restart gestion-docente-backend
sudo systemctl restart gestion-docente-streamlit
```

Streamlit y el build de React no necesitan "restart" per se (el build estático lo
sirve Nginx directo, y Streamlit sí necesita restart si cambió `vistas/*.py`).

---

## 12. Checklist de seguridad — resumen

- [ ] SSH: solo con clave, `root` deshabilitado, `fail2ban` activo.
- [ ] `ufw`: solo 22/80/443 abiertos; Postgres, backend y Streamlit **no**
      expuestos (`127.0.0.1` / puerto de Postgres no escuchando en `0.0.0.0`).
- [ ] Cada proyecto con su propia base de datos y su propio usuario de Postgres,
      contraseñas distintas y únicas.
- [ ] `.env` con `chmod 600`, `JWT_SECRET_KEY` generada de nuevo para este
      servidor (no reutilizada de tu PC ni de otro proyecto).
- [ ] HTTPS obligatorio (certbot redirige HTTP→HTTPS), renovación automática
      verificada.
- [ ] `uvicorn` sin `--reload`, ambos servicios como `systemd` con
      `Restart=on-failure`.
- [ ] Repositorio de código **privado**, `entregas_docentes/` y
      `repositorio_asignaturas/` nunca versionados (ya en `.gitignore`).
- [ ] Backup diario de base de datos + archivos, con copia fuera del propio VPS.
- [ ] `unattended-upgrades` activo para parches de seguridad del sistema
      operativo.
- [ ] Prueba de los 4 roles (Docente, Director, Secretario Académico, Secretaria
      del Programa) contra el dominio real, con el Aviso de Privacidad
      aceptándose correctamente y quedando registrado en
      `aceptaciones_politica_tratamiento`.
- [ ] `client_max_body_size 20m;` en el bloque Nginx (sin esto, Nginx rechaza
      subidas >1 MB por defecto, antes de que lleguen al backend).
- [ ] `--workers 4` (no 2) si se espera más de un puñado de docentes usando la
      app a la vez — probado con una subida real de documento firmado bajo carga.
- [ ] `SystemMaxUse` de `journald` fijado explícitamente (no depender del valor
      por defecto del sistema, compartido con otros proyectos del VPS).
- [ ] Decisión explícita tomada sobre si Streamlit se expone a todos los
      docentes como interfaz de producción, o si queda solo para uso interno
      (React como interfaz oficial) — un solo proceso Streamlit sin réplicas
      no está pensado para cientos de sesiones concurrentes.

---

## 13. Cuando montes el siguiente proyecto en el mismo VPS

Repite exactamente este mismo manual, cambiando solo:
- El subdominio (paso 1.1) y el `server_name` / certificado de Nginx.
- Los puertos (siguiente fila libre en tu `PUERTOS.md`).
- El nombre de la base de datos y su usuario propio (nunca reutilices el de este
  proyecto).
- Los nombres de los archivos `.service` de systemd (con un prefijo distinto,
  p. ej. `otro-proyecto-backend.service`).

Todo lo demás (firewall, fail2ban, certbot, Postgres compartido, convención de
carpetas en `/srv/apps/`) ya queda resuelto para todos los proyectos que montes
después.
