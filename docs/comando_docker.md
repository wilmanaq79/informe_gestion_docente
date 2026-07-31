
# Detén y elimina contenedores y volumen
- docker compose down -v --remove-orphans
# Confirma que el volumen desapareció
- docker volume ls | findstr gestion_docente
- No, debería mostrar es: gestion_docente_postgres_data
- Si todavía aparece, elimínalo manualmente:
- docker volume rm informe_de_gestion_gestion_docente_postgres_data
# configuracion de archivo docker_compose
- docker compose config
# Comprueba la creación de PostgreSQ
- docker logs [ name contenedor - gestion_docente_postgres]
# Este comando obliga a validar la contraseña:
- docker exec -it gestion_docente_postgres psql -h localhost -U gestion_docente_app -d gestion_docente -W
# Levanta nuevamente los servicios
- docker compose up -d
# Listar contenedoras
- docker compose ps