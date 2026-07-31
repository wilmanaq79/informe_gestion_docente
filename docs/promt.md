Revisa integralmente este proyecto React + Vite, FastAPI, SQLAlchemy,
PostgreSQL y Docker. La aplicación se desarrolla localmente en Windows,
pero posteriormente se desplegará en un VPS Ubuntu mediante Docker Compose.

No realices solamente la creación manual de dos usuarios. Implementa una
arquitectura reproducible de desarrollo y producción.

Objetivos:

1. Analizar primero la estructura, modelos SQLAlchemy, autenticación,
   roles, permisos, scripts existentes, variables de entorno y pruebas.
   No eliminar ni reemplazar funcionalidades existentes sin justificarlo.

2. Dockerizar completamente:
   - PostgreSQL.
   - Backend FastAPI.
   - Frontend React compilado.
   - Nginx como proxy inverso.
   - pgAdmin únicamente como herramienta opcional de desarrollo.

3. Crear Dockerfile para el backend usando una imagen oficial de Python:
   - Instalar requirements.txt utilizando caché adecuadamente.
   - Ejecutar FastAPI en 0.0.0.0:8000.
   - No utilizar --reload en producción.
   - Ejecutar como usuario no root.
   - Añadir healthcheck.
   - Utilizar --proxy-headers detrás de Nginx.

4. Crear Dockerfile multietapa para el frontend:
   - Construir con Node.
   - Ejecutar npm ci y npm run build.
   - Servir dist/ con Nginx en producción.
   - No utilizar el servidor de desarrollo de Vite en producción.

5. Configurar Alembic:
   - Integrarlo si aún no existe.
   - Detectar todos los modelos SQLAlchemy.
   - Generar una migración inicial válida.
   - Permitir crear todas las tablas sobre una base vacía con
     alembic upgrade head.
   - Documentar el proceso de nuevas migraciones.

6. Crear scripts/init_db.py o scripts/seed_db.py:
   - Crear roles y permisos iniciales.
   - Crear un usuario Administrador.
   - Crear un usuario Director.
   - Obtener credenciales iniciales desde variables de entorno.
   - Hashear las contraseñas con la misma función utilizada por el login.
   - Obligar al cambio de contraseña en el primer acceso, si el modelo lo
     permite; si no, implementar el campo y su migración.
   - Ser idempotente: no duplicar roles, permisos ni usuarios.
   - No guardar contraseñas en texto plano.
   - No imprimir contraseñas en los logs.

7. Separar configuraciones:
   - compose.yaml con servicios comunes.
   - compose.dev.yaml para desarrollo.
   - compose.prod.yaml para producción.
   - .env.example sin secretos reales.
   - Variables distintas para desarrollo y producción.
   - Dentro de Docker, DATABASE_URL debe usar postgres_db como host.
   - Desde el host local, DATABASE_URL puede usar localhost.

8. Configurar dependencias y salud:
   - Healthcheck de PostgreSQL con pg_isready.
   - Healthcheck del backend mediante /api/health.
   - depends_on con condiciones de salud donde sea compatible.
   - Política de reinicio.
   - Rotación o límites de logs.

9. Configurar Nginx:
   - Servir el frontend.
   - Enviar /api al backend.
   - Soportar SPA con fallback a index.html.
   - Incluir encabezados de seguridad.
   - Preparar configuración para HTTPS y Certbot.
   - No exponer directamente PostgreSQL, backend ni pgAdmin en producción.

10. Seguridad:
    - Verificar .gitignore.
    - Eliminar secretos rastreados del código y ejemplos.
    - Restringir CORS en producción.
    - No publicar el puerto 5432 en producción.
    - Deshabilitar pgAdmin en producción.
    - Mantener rate limiting del login.
    - Validar políticas de contraseñas.
    - Utilizar variables o secretos protegidos.

11. Backups:
    - Crear scripts para pg_dump y pg_restore.
    - Preparar una tarea cron documentada para el VPS.
    - Incluir retención de respaldos.
    - Documentar una prueba de restauración.

12. Pruebas:
    - Base vacía + migraciones.
    - Seed idempotente.
    - Login de Administrador y Director.
    - Roles y permisos.
    - Endpoint de salud.
    - Persistencia después de reiniciar contenedores.

13. Documentación:
    - Actualizar README.md.
    - Crear docs/DESARROLLO_DOCKER.md.
    - Crear docs/DESPLIEGUE_VPS.md.
    - Crear docs/BACKUP_RESTORE.md.
    - Incluir comandos exactos para Windows PowerShell y Ubuntu.

Flujo local esperado:

docker compose -f compose.yaml -f compose.dev.yaml up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/init_db.py

Flujo de producción esperado:

docker compose -f compose.yaml -f compose.prod.yaml up -d --build

Antes de modificar, presenta un resumen del diagnóstico y un plan por fases.
Después implementa por fases y ejecuta las pruebas disponibles.
No borres datos ni volúmenes automáticamente.
No uses docker compose down -v en scripts de producción.
No inventes nombres de campos o modelos: inspecciona primero el código existente.
Entrega al final:
- Archivos creados.
- Archivos modificados.
- Comandos de ejecución.
- Variables obligatorias.
- Resultados de pruebas.
- Riesgos o tareas pendientes.
# La prioridad inmediata para recuperar el sistema debe ser:
1. Alembic y migración inicial.
2. Seed de roles y usuarios.
3. Prueba del login.
4. Dockerización del backend.
5. Dockerización del frontend.
6. Configuración de producción para el VPS.