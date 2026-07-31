# ESPECIFICACIÓN FUNCIONAL Y TÉCNICA
## Módulo de Gestión de Tareas Académicas y Administrativas

**Adaptada al stack ya en producción de este proyecto** (FastAPI + SQLAlchemy + PostgreSQL +
React/Streamlit, todo en el mismo VPS) — a partir de la especificación funcional original
entregada por el usuario (`ESPECIFICACION_MODULO_TAREAS.md`), removiendo el stack alternativo que
proponía (Next.js/NestJS/Prisma/Redis/MinIO, monorepo aparte) y sustituyéndolo por la
arquitectura real de este repositorio.

Este módulo **no es una aplicación nueva**: es una extensión del sistema de Gestión y
Autoevaluación Docente ya existente. Reutiliza usuarios, roles, programas académicos, JWT,
RBAC, almacenamiento de archivos, notificaciones y el patrón de paridad React/Streamlit ya
establecidos — no se crea una base de datos, un login ni un backend aparte.

---

## 1. Propósito

Construir un módulo web para producción que permita crear, asignar, programar, ejecutar,
supervisar, evaluar y cerrar tareas académicas y administrativas del Programa de Ingeniería de
Sistemas (y de cualquier otro programa académico que use este mismo sistema, dado que ya es
multi-programa — ver `db.models.Programa`).

El sistema debe centralizar tareas, subtareas, responsables, fechas, prioridades, evidencias,
comentarios, seguimiento, solicitudes de ampliación, indicadores, reportes, notificaciones y
auditoría.

## 2. Objetivo general

Extender la plataforma ya existente para administrar integralmente las tareas del programa, con
control de acceso por roles, trazabilidad completa, indicadores automáticos, seguridad,
accesibilidad y despliegue en el mismo VPS donde ya corre el sistema.

## 3. Objetivos específicos

1. Crear, programar y asignar tareas a los integrantes del programa.
2. Controlar estados, avances, fechas y vencimientos.
3. Centralizar evidencias, observaciones y documentos.
4. Generar indicadores para apoyar la toma de decisiones.
5. Garantizar seguridad, auditoría y conservación del historial.

---

# 4. Jerarquía de roles

```text
Director / Administrador del Sistema
                ↓
            Secretario
                ↓
             Docente
                ↓
    Secretaria del Programa
```

Estos son **los mismos 4 roles que ya existen** en `db.models.Rol` / tabla `roles`
(`director`, `secretario`, `docente`, `secretaria_programa`) y en el mismo alcance por
programa académico (`Usuario.programa_id`) ya implementado. No se crean roles nuevos ni una
segunda tabla de usuarios — el módulo de tareas usa `usuarios.id` como responsable, asignador,
autorizador, etc.

La jerarquía expresa nivel de autoridad. Cada permiso debe validarse de forma explícita en
backend (dependencias de FastAPI, igual que hoy `requiere_roles(...)` en
`backend/api/deps.py`) y en frontend (ocultar acciones no permitidas, aunque el backend sigue
siendo la única barrera real).

---

# 5. Roles

*(Capacidades y restricciones — sin cambios respecto a la especificación funcional original;
se listan aquí para que este documento quede autocontenido. La sección 6 tiene la matriz
consolidada.)*

## 5.1. Director — Administrador del Sistema

Es el único administrador general.

### Puede

- Crear, editar, activar, desactivar y bloquear usuarios *(ya existe: `backend/api/routers/usuarios.py`)*.
- Restablecer contraseñas *(ya existe: flujo de recuperación en `backend/api/routers/auth.py`)*.
- Asignar roles y permisos.
- Administrar categorías, prioridades, estados, periodos, programas, indicadores y parámetros
  del módulo de tareas.
- Crear, editar, asignar, reasignar, suspender, cancelar, reabrir, aprobar y cerrar tareas.
- Asignar tareas al Secretario, Docentes y Secretaria del Programa.
- Definir responsables principales y secundarios.
- Modificar fechas, prioridades, categorías y evidencias requeridas.
- Aprobar o rechazar solicitudes de ampliación.
- Revisar evidencias.
- Evaluar definitivamente el cumplimiento.
- Consultar todos los indicadores, reportes y auditorías.
- Consultar carga laboral, productividad y riesgos de incumplimiento.
- Administrar plantillas, notificaciones y niveles de confidencialidad.

### Restricciones

- No puede eliminar físicamente tareas, evidencias, observaciones, evaluaciones ni auditorías
  (mismo principio que ya se sigue en todo el sistema: nunca se hace `DELETE` físico de datos
  con valor histórico/legal — ver `aceptaciones_politica_tratamiento`, `notas_estudiantes`).
- Todas sus acciones deben quedar auditadas (tabla `auditoria`, nueva — ver sección 29).

## 5.2. Secretario

Está debajo del Director y coordina, supervisa y realiza seguimiento.

### Puede

- Crear tareas institucionales.
- Programar tareas.
- Asignar tareas a Docentes y a la Secretaria del Programa.
- Reasignar con autorización del Director.
- Definir título, descripción, objetivo, resultado esperado, fechas, prioridad y categoría.
- Crear subtareas y dependencias.
- Definir evidencias requeridas.
- Registrar seguimientos, comentarios, compromisos y recordatorios.
- Revisar avances y evidencias.
- Solicitar correcciones.
- Realizar evaluación preliminar.
- Recomendar aprobación o devolución.
- Consultar indicadores operativos.
- Generar reportes operativos.
- Consultar calendario y carga de trabajo *(reutiliza `vistas/calendario.py` /
  `CalendarioAcademico.tsx` ya existentes)*.
- Enviar tareas al Director para decisión final.

### No puede

- Crear o eliminar usuarios.
- Modificar roles o permisos.
- Cambiar configuración crítica.
- Aprobar, cerrar o reabrir definitivamente una tarea.
- Modificar evaluaciones definitivas.
- Eliminar evidencias, observaciones o auditorías.
- Acceder a información fuera de su alcance (fuera de su `programa_id`, igual que hoy con
  `verificar_pertenece_a_programa`).

## 5.3. Docente

Ejecuta tareas asignadas por el Director o el Secretario.

### Puede

- Consultar tareas asignadas.
- Confirmar recepción.
- Iniciar tareas.
- Registrar porcentaje y descripción del avance.
- Crear subtareas de ejecución.
- Adjuntar evidencias.
- Registrar comentarios y dificultades.
- Solicitar ampliación de plazo.
- Enviar tareas a revisión.
- Corregir tareas devueltas.
- Consultar observaciones, historial e indicadores personales.
- Crear tareas personales.
- Consultar calendario y recordatorios.
- Registrar tiempo invertido.

### Transiciones permitidas

```text
Sin comenzar → En proceso
En proceso → Pendiente de revisión
Devuelta con observaciones → En proceso
```

### No puede

- Administrar usuarios, roles o permisos.
- Asignar tareas institucionales a otros usuarios.
- Aprobar sus propias tareas.
- Cambiar fechas autorizadas sin solicitud.
- Modificar tareas pendientes de revisión.
- Consultar tareas privadas de otros usuarios.
- Reabrir o cerrar definitivamente tareas.
- Modificar evaluaciones.

## 5.4. Secretaria del Programa

Es el rol operativo y documental que trabaja bajo orientación del Director y del Secretario.
Debe diferenciarse del Secretario (son roles distintos ya en el sistema:
`secretaria_programa` vs `secretario`).

### Puede

- Crear borradores de tareas.
- Registrar tareas administrativas.
- Registrar fechas institucionales *(reutiliza `eventos_calendario` ya existente si aplica)*.
- Programar recordatorios.
- Adjuntar documentos.
- Registrar llamadas, contactos y seguimientos.
- Organizar soportes, actas y comunicaciones.
- Consultar tareas dentro de su alcance.
- Consultar calendario administrativo.
- Notificar vencimientos.
- Elaborar reportes operativos.
- Registrar avance en sus tareas.
- Enviar sus tareas a revisión.
- Registrar compromisos y próxima fecha de seguimiento.

### Creación de tareas

Solo podrá crear tareas en estado:

```text
Borrador
```

El borrador deberá ser publicado por el Director o el Secretario.

La asignación directa solo será posible con un permiso delegado, explícito, temporal y
auditable (tabla nueva `permisos_delegados`, ver sección 29).

### No puede

- Administrar usuarios, roles o permisos.
- Aprobar tareas.
- Evaluar Docentes.
- Publicar sus propios borradores.
- Asignar tareas sin autorización.
- Modificar indicadores o configuración.
- Reasignar responsables.
- Reabrir o cerrar tareas.
- Consultar información confidencial no autorizada.
- Modificar evaluaciones.
- Eliminar registros, observaciones o evidencias aprobadas.

---

# 6. Matriz de permisos

| Funcionalidad | Director | Secretario | Docente | Secretaria del Programa |
|---|---:|---:|---:|---:|
| Administrar usuarios | Sí | No | No | No |
| Administrar roles y permisos | Sí | No | No | No |
| Configurar el módulo (categorías, prioridades, plantillas) | Sí | No | No | No |
| Crear tareas institucionales | Sí | Sí | No | Solo borradores |
| Crear tareas personales | Sí | Sí | Sí | Sí |
| Asignar a Docentes | Sí | Sí | No | Solo delegado |
| Asignar a Secretaria del Programa | Sí | Sí | No | No |
| Reasignar tareas | Sí | Autorizado | No | No |
| Cambiar fechas | Sí | Limitado | Solicita | No |
| Registrar avances | Sí | Sí | Sí | Sí |
| Registrar seguimiento | Sí | Sí | En sus tareas | Operativo |
| Adjuntar evidencias | Sí | Sí | Sí | Sí |
| Revisar evidencias | Sí | Sí | Propias | Autorizadas |
| Evaluación preliminar | Sí | Sí | No | No |
| Evaluación definitiva | Sí | No | No | No |
| Aprobar y cerrar | Sí | No | No | No |
| Reabrir | Sí | No | No | No |
| Indicadores generales | Sí | Sí | No | Parcial |
| Indicadores personales | Sí | Sí | Sí | Sí |
| Reportes generales | Sí | Sí | No | No |
| Reportes operativos | Sí | Sí | Personales | Sí |
| Auditoría | Completa | Limitada | No | No |
| Eliminar físicamente | No | No | No | No |

Esta matriz se implementa igual que la matriz de permisos ya documentada del sistema actual
(ver referencia histórica de auditoría de roles): un `requiere_roles(*roles_permitidos)` por
endpoint en FastAPI, más el filtro por `programa_id` vía `verificar_pertenece_a_programa`, y
chequeos adicionales de "dueño del recurso" (p. ej. un Docente solo ve/edita SUS tareas)
resueltos en la capa de repositorio (`db/repository.py`), no solo en el router.

---

# 7. Estados y flujo

Estados (10, con icono — implementados en `estados_tarea`):

- 📝 Borrador
- 🗓️ Programada
- 🟢 Sin comenzar
- 🟡 En proceso
- 🔵 Pendiente de revisión (equivalente a "En revisión")
- 🟠 Devuelta con observaciones
- ✅ Terminada
- ⏸️ Suspendida
- 🔴 Cancelada
- ⏰ **Vencida**

> **Decisión revisada (corrige una decisión anterior de este documento):** Vencida **es un
> estado real** de la tarea, no una condición calculada aparte del estado operativo. El sistema
> lo asigna **automáticamente** cuando se supera `fecha_limite` y la tarea no ha sido finalizada
> ni cancelada — sin depender de un job periódico: la actualización ocurre mediante un `UPDATE`
> en bloque ejecutado al inicio de `listar_tareas`/`tarea_por_id` (ver
> `db.repository._marcar_tareas_vencidas`), así que el estado siempre queda correcto en cuanto
> alguien vuelve a consultar las tareas. Quedan exentas de pasar a Vencida: **Borrador** (todavía
> no se publica, no tiene una fecha límite "activa" en la práctica), **Terminada**, **Cancelada**
> y la propia **Vencida**. Esto reemplaza la versión original de esta sección y la regla 28 (ver
> sección 25), que trataban "vencida" como una condición temporal separada del estado.

```text
Borrador
   ↓
Programada
   ↓
Sin comenzar
   ↓
En proceso
   ↓
Pendiente de revisión
   ├───────────────→ Terminada
   └→ Devuelta con observaciones
                 ↓
             En proceso

(Cualquier estado no exento) → Vencida, automático, si se supera fecha_limite
```

Los estados se modelan como una tabla de catálogo pequeña (`estados_tarea`), siguiendo el
mismo patrón ya usado para `roles` y `cortes` (tabla de referencia, no un `Enum` de Python
embebido en la columna) — así se pueden reordenar/renombrar sin migración de esquema.

---

# 8. Campos de una tarea

- ID único.
- Código visible.
- Título.
- Descripción.
- Objetivo.
- Resultado esperado.
- Tipo.
- Categoría.
- Prioridad.
- Responsable principal.
- Responsables secundarios.
- Creador.
- Asignador.
- Autorizador.
- Fecha de creación.
- Fecha de inicio.
- Fecha límite.
- Hora límite.
- Fecha real de finalización.
- Estado.
- Condición temporal (vencida/no vencida, calculada).
- Porcentaje de avance.
- Programa (`programa_id`, reutiliza `programas`).
- Periodo académico (`periodo_id`, reutiliza `periodos_academicos`, opcional).
- Indicador asociado.
- Evidencias requeridas.
- Subtareas.
- Dependencias.
- Etiquetas.
- Nivel de confidencialidad.
- Frecuencia de repetición.
- Tiempo estimado.
- Tiempo invertido.
- Motivo de cancelación.
- Justificación de retraso.
- Requiere aprobación.
- Requiere evidencia.
- Permite ampliación.
- Historial.

---

# 9. Categorías iniciales

- Docencia
- Investigación
- Proyección Social
- Dirección de Programa
- Secretaría
- Consejo Académico
- Autoevaluación
- Acreditación
- Gestión de Calidad
- Bienestar
- Eventos
- Reuniones
- Capacitación
- Tutorías
- Gestión Administrativa
- Internacionalización
- Egresados
- Prácticas profesionales
- Comunicaciones
- Planeación
- Personal
- Otras

Configurables por el Director vía CRUD simple (tabla `categorias_tarea`, mismo patrón que
`RepositorioAsignatura`/`Programa`: alta desde la UI, sin tocar código).

---

# 10. Prioridades

- Baja
- Media
- Alta
- Crítica

Cada prioridad tiene nombre, icono (emoji, igual convención que el resto de la UI: 🗓️ 📎 📚),
color, orden y nivel numérico. La interfaz no depende exclusivamente del color (icono + texto
siempre visibles, mismo criterio ya aplicado en `docs/testQA.md`/accesibilidad del resto del
sistema).

---

# 11. Recurrencia

Permitir tareas:

- Únicas
- Diarias
- Semanales
- Quincenales
- Mensuales
- Bimestrales
- Trimestrales
- Semestrales
- Anuales
- Personalizadas

Configurar inicio, fin, intervalo, días de repetición, número de ocurrencias, exclusión de
días no laborables (reutiliza `eventos_calendario` para saber qué días son no hábiles) y
recordatorios.

Las tareas recurrentes generan instancias independientes (filas propias en `tareas`, no una
sola fila con lógica de repetición en el cliente) — se generan con un job periódico simple
(ver sección 27, "sin cola de mensajería").

---

# 12. Subtareas y dependencias

## Subtareas

Campos: título, descripción, responsable, estado, fecha límite, porcentaje, orden, evidencia
opcional.

## Dependencias

Tipos:

- Finaliza para iniciar
- Inicia para iniciar
- Finaliza para finalizar
- Inicia para finalizar

Una tarea bloqueada no puede iniciarse hasta cumplir su dependencia — validado en
`db/repository.py` antes de permitir la transición de estado (regla de negocio, no solo UI).

---

# 13. Seguimiento

Cada registro guarda: usuario y rol, fecha y hora, porcentaje, descripción, dificultades,
compromisos, próxima revisión, archivos, estado anterior y nuevo, responsable de próxima
acción, visibilidad.

No se elimina físicamente (mismo principio que el historial de notas/informes ya existente).

---

# 14. Evidencias

Tipos permitidos: PDF, Word, Excel, PowerPoint, Imagen, Video, ZIP, Enlace.

Metadatos: nombre original, nombre interno, MIME, extensión, tamaño, usuario, fecha y hora,
versión, descripción, estado de revisión, hash, ruta, confidencialidad, comentario de
revisión.

**Almacenamiento: disco local del VPS, no S3/MinIO** — se extiende
`agente_notas/almacenamiento.py` (mismo módulo que ya guarda sílabos, entregas y formatos
institucionales) con una nueva carpeta `evidencias_tareas/` y una whitelist de extensiones
propia (mismo patrón que `EXTENSIONES_POR_TIPO_REPOSITORIO`/`EXTENSIONES_POR_TIPO_INSTITUCIONAL`),
más un campo `hash` (sha256, calculado al guardar) para poder verificar integridad. Si el
volumen de archivos del módulo de tareas crece mucho más que el resto del sistema, migrar a un
bucket S3-compatible queda como mejora futura documentada, no como requisito de esta fase.

---

# 15. Comentarios y observaciones

Tipos: Informativa, Recordatorio, Corrección, Recomendación, Aprobación, Incumplimiento,
Justificación, Seguimiento administrativo, Seguimiento académico, Solicitud de información,
Respuesta, Alerta.

Guardar autor, rol, fecha, hora, contenido, adjuntos, destinatarios, visibilidad y estado de
lectura.

---

# 16. Solicitudes de ampliación

Campos: tarea, solicitante, motivo, fecha actual, nueva fecha propuesta, evidencia, fecha de
solicitud, estado, recomendación del Secretario, decisión del Director, fecha de decisión.

Estados: Pendiente, Recomendada, Aprobada, Rechazada, Cancelada.

Solo el Director decide definitivamente.

---

# 17. Evaluación

Criterios: cumplimiento del objetivo, calidad del resultado, puntualidad, calidad de
evidencias, cumplimiento de instrucciones, claridad documental, autonomía, impacto.

Escala cualitativa: Excelente, Satisfactorio, Aceptable, Requiere mejora, Incumplido. También
podrá usarse escala de 0 a 100.

El Secretario registra evaluación preliminar. El Director registra evaluación definitiva.

---

# 18. Indicadores

## Individuales

Tareas asignadas, terminadas, vencidas, en proceso, cumplimiento dentro del plazo, puntualidad,
promedio de retraso, tareas devueltas, tareas con evidencia, promedio de evaluación,
cumplimiento mensual y semestral, tiempo promedio de ejecución, carga activa, solicitudes de
ampliación.

## Generales

Cumplimiento del programa, cumplimiento por usuario/rol/categoría/periodo, tareas por estado y
prioridad, tareas críticas, tendencia mensual, carga laboral, tiempo promedio de finalización,
tareas devueltas, tareas sin evidencia, tareas pendientes de revisión, productividad.

```text
Cumplimiento =
(Tareas terminadas dentro del plazo / Tareas asignadas válidas) × 100
```

Las tareas canceladas justificadamente no se incluyen.

**Cálculo:** igual que `DashboardInstitucional` ya existente (backend/api/routers/dashboard.py)
— se calculan **al vuelo** con consultas agregadas (SQLAlchemy `func.count`/`func.avg`, etc.)
sobre las tablas de tareas, no se persisten en una tabla `indicadores`/`valores_indicador`
aparte. Si el volumen de tareas crece lo suficiente para que el cálculo en vivo sea lento,
cachear resultados (ver sección 27) es una mejora futura, no un requisito inicial — evita
mantener una tabla derivada que puede desincronizarse de los datos reales.

---

# 19. Dashboards

## Director

Total y distribución de tareas, cumplimiento general, cumplimiento por usuario/rol/categoría,
vencidas y críticas, pendientes de revisión, solicitudes de ampliación, comparativos, carga
laboral, alertas, auditoría reciente, productividad, riesgos.

## Secretario

Tareas asignadas, seguimientos, revisión preliminar, próximas a vencer, vencidas, sin
evidencia, cumplimiento por Docente, cumplimiento de Secretaria del Programa, calendario,
reportes operativos, solicitudes de ampliación.

## Docente

Tareas de hoy/semana/mes, próximas a vencer, vencidas, devueltas, pendientes de revisión,
terminadas, calendario, cumplimiento, observaciones, evidencias pendientes, carga actual.

## Secretaria del Programa

Tareas propias, borradores, recordatorios, seguimientos, documentos pendientes, calendario
administrativo, actividades del día, comunicaciones pendientes, evidencias administrativas.

Cada dashboard se implementa como una página propia dentro del layout de cada rol ya existente
(`frontend/src/layouts/{Docente,Direccion,Secretaria}Layout.tsx`), reutilizando los componentes
de gráficas ya construidos en `frontend/src/components/charts/` donde aplique (mismo estilo
visual que `DashboardInstitucional`).

---

# 20. Vistas

Lista, Tabla, Kanban, Calendario, Línea de tiempo, Por responsable, Por categoría, Por
prioridad, Por periodo, Vencidas, Pendientes de revisión.

El drag and drop del Kanban debe validar permisos y transiciones **en backend** (el endpoint de
cambio de estado rechaza la transición aunque el frontend ya haya movido la tarjeta
visualmente) — mismo principio que ya se sigue en el resto del sistema (nunca confiar en
validación solo de cliente).

---

# 21. Búsqueda y filtros

Buscar por código, título, descripción, responsable, creador, categoría, estado, prioridad,
etiquetas, periodo y programa.

Filtros: estado, vencimiento, prioridad, categoría, responsable, programa, fecha, periodo,
tipo, confidencialidad, con/sin evidencia, con ampliación, pendiente de revisión.

---

# 22. Notificaciones

Generar cuando: se crea/asigna/reasigna una tarea, cambia estado/prioridad/fecha, se agrega
comentario, se carga evidencia, se envía a revisión, se devuelve, se aprueba, se
solicita/aprueba/rechaza ampliación, está próxima a vencer, vence, se menciona a un usuario, se
publica un borrador, se suspende/cancela/reabre.

**Reutiliza el sistema de notificaciones ya existente** (`db.models.Notificacion`,
`agente_notas/notificaciones.py`, `NotificacionesBell.tsx`) en vez de crear uno nuevo:

- Canal interno (in-app): agregar un `tarea_id` nullable a `notificaciones` (o una tabla
  `notificaciones_tarea` espejo si se prefiere no tocar la tabla existente — a decidir en la
  Fase correspondiente), reutilizando la campanita del Header ya construida.
- Canal correo: reutiliza `agente_notas/notificaciones.py` (mismo patrón `notificar_*` que
  `notificar_entrega_aprobada`), enviado en segundo plano con `BackgroundTasks` de FastAPI
  (mismo patrón ya usado en `entregas.py`) — no se introduce una cola de mensajería (Redis/
  BullMQ) para esto.
- Push, Google Calendar y Outlook quedan como "futuro" (igual que en la especificación
  original) — no forman parte de esta fase.
- "Próxima a vencer" / "vence": se resuelve con un job programado simple (cron del sistema
  operativo o `APScheduler` en el propio proceso de `uvicorn`) que recorre tareas con fecha
  límite próxima y encola las notificaciones correspondientes — sin BullMQ ni Redis.

---

# 23. Reportes

Cumplimiento, productividad, por usuario, por rol, por categoría, por periodo, vencidas,
próximas a vencer, evaluaciones, evidencias, ampliaciones, carga laboral, seguimientos,
auditoría.

Exportar a PDF (reutiliza `reportlab`, ya usado en `agente_notas/reporte_pdf.py`), Excel
(reutiliza `openpyxl`, ya usado en `agente_notas/core.py`) y CSV (nativo de `pandas`, ya
dependencia del proyecto).

---

# 24. Auditoría

Registrar: inicios y cierres de sesión, intentos fallidos (reutiliza el mecanismo ya existente
de `intentos_login_fallidos`/`backend/core/rate_limit.py`), cambios de usuarios/roles/permisos,
creación y edición de tareas, asignaciones y reasignaciones, cambios de
estado/prioridad/fecha, comentarios, evidencias, descargas, evaluaciones, ampliaciones,
reportes, cambios de configuración.

Campos: usuario, rol, acción, recurso, ID del recurso, fecha y hora, IP, agente de usuario,
valor anterior, valor nuevo, resultado, motivo.

Nueva tabla `auditoria` (no existe hoy una tabla de auditoría genérica — lo más parecido es
`aceptaciones_politica_tratamiento`, que es específica de esa funcionalidad). Los registros son
inmutables: solo `INSERT`, nunca `UPDATE`/`DELETE` (aplicado a nivel de código en
`db/repository.py`, ya que este proyecto no usa permisos de base de datos por rol de Postgres
para reforzarlo).

---

# 25. Reglas de negocio

1. El Director es el único administrador.
2. El Secretario está debajo del Director.
3. El Secretario asigna tareas a Docentes y Secretaria del Programa.
4. El Docente ejecuta tareas.
5. La Secretaria del Programa realiza apoyo operativo y documental.
6. Solo el Director aprueba, evalúa definitivamente y cierra.
7. El Secretario realiza seguimiento y evaluación preliminar.
8. La Secretaria del Programa crea borradores, pero no los publica.
9. El Docente no aprueba sus tareas.
10. Toda tarea institucional tiene responsable y fecha.
11. Las tareas personales no afectan indicadores institucionales.
12. Todo cambio queda en historial.
13. No hay eliminación física.
14. Solo el Director reabre tareas terminadas.
15. Los cambios de fecha conservan valor anterior.
16. Una tarea en revisión no puede ser modificada por el responsable.
17. Toda devolución requiere observación.
18. Toda cancelación requiere justificación.
19. Una tarea con evidencia obligatoria no puede aprobarse sin evidencia.
20. El acceso debe respetar alcance (`programa_id`) y confidencialidad.
21. Las acciones del Director también se auditan.
22. Las ampliaciones requieren motivo y fecha propuesta.
23. Los indicadores se recalculan al vuelo, no se desactualizan.
24. Los archivos deben validarse (extensión + tamaño, igual que `almacenamiento.py`).
25. Las transiciones se validan en backend.
26. Kanban no puede omitir reglas.
27. Recurrencias generan instancias independientes.
28. Vencida **es** un estado real, asignado automáticamente por el sistema cuando se supera
    `fecha_limite` y la tarea no está Terminada/Cancelada/Borrador (ver sección 7 — corrige la
    redacción original de esta regla).
29. Permisos delegados son temporales y auditables.
30. La Secretaria del Programa no publica sus borradores.
31. El Secretario no puede otorgarse permisos.
32. Evidencias enviadas a revisión no se eliminan.
33. Versiones anteriores deben conservarse.
34. Tareas bloqueadas por dependencia no pueden iniciar.
35. Reportes respetan permisos y confidencialidad.

---

# 26. UX/UI

Responsive, mobile first, WCAG 2.2 AA, menú según rol (reutiliza el `Sidebar.tsx` /
`st.navigation` recién construidos — ver `docs/planRediseñoNavegacion.md`), formularios por
pasos, validación en tiempo real, mensajes claros, confirmación de acciones críticas, skeleton
loading, toasts, tablas con paginación, Kanban, calendario, timeline, barras de progreso, modo
claro y oscuro (reutiliza las variables CSS `--surface`/`--texto`/etc. ya definidas en
`index.css`), navegación por teclado, no depender solo del color, autoguardado de borradores,
advertencia por cambios sin guardar, estados vacíos explicativos (reutiliza el componente
`EstadoVacio` ya existente), tooltips, breadcrumbs, componentes reutilizables.

Colores sugeridos (usar los tokens ya definidos, no hex nuevos):

- Verde (`--verde`/`--marca-verde`): terminada.
- Dorado/amarillo (`--dorado`): en proceso.
- Azul (`--azul`): revisión.
- Rojo (`--rojo`): vencida.
- Gris (`--muted`): suspendida.
- Un color adicional (a definir, p. ej. un morado nuevo agregado a `:root`) para devuelta.

---

# 27. Stack (el que ya está en producción — sin cambios)

## Frontend

```text
React 18 + TypeScript (Vite)
React Router DOM (rutas anidadas por rol, ver docs/planRediseñoNavegacion.md)
CSS plano con variables (index.css) -- sin Tailwind ni shadcn/ui
Axios (frontend/src/api/client.ts)
Recharts (frontend/src/components/charts/) para gráficas
Vitest + Testing Library para pruebas
```

Paralelo en Streamlit (paridad ya establecida, ver [[react_frontend_produccion]] — React es el
que se publica en el VPS, Streamlit se mantiene equivalente):

```text
Streamlit 1.60 (st.navigation / st.Page para las páginas del módulo)
pandas / openpyxl para tablas y export
```

## Backend

```text
FastAPI + Uvicorn
SQLAlchemy 2.x (ORM, sin Prisma)
PostgreSQL (psycopg)
python-jose (JWT) + bcrypt (hash de contraseña) -- ya implementados en
    backend/core/security.py y db/auth.py, se reutilizan tal cual
pydantic-settings (backend/core/config.py)
reportlab (PDF), openpyxl (Excel) -- ya dependencias del proyecto
Sin Redis ni BullMQ: tareas en segundo plano con BackgroundTasks de FastAPI
    (ya usado en entregas.py) + un scheduler simple en proceso (APScheduler)
    si se necesita algo periódico (vencimientos, recurrencias)
Almacenamiento de archivos en disco local del VPS (agente_notas/almacenamiento.py),
    no S3/MinIO
```

## Migraciones

**Sin Alembic.** Este proyecto usa scripts idempotentes en `scripts/migrar_*.py`
(`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` vía
`sqlalchemy.text()`, ejecutados a mano con `python -m scripts.migrar_x`) — el módulo de tareas
sigue el mismo patrón (`scripts/migrar_modulo_tareas.py`), no se introduce una herramienta de
migraciones nueva.

## Pruebas

```text
pytest (backend) -- fixture db_session de tests/conftest.py, pruebas a nivel de
    db/repository.py, sin TestClient salvo para lo ya existente en tests/test_api_smoke.py
Vitest + Testing Library (frontend React)
```

Sin pruebas E2E automatizadas (Playwright/Cypress) por ahora — la verificación end-to-end se
hace manualmente en el Browser pane, igual que en todas las fases anteriores de este proyecto.

---

# 28. Arquitectura

```text
React (Vite, build estático)          Streamlit (paridad)
        │                                     │
        └───────────────┬─────────────────────┘
                         ▼
                FastAPI (uvicorn, systemd)
                         │
                         ▼
                   PostgreSQL
                         │
              ┌──────────┼──────────┐
       Disco local   Correo (SMTP)   Notificaciones in-app
   (evidencias_tareas/)  (agente_notas/notificaciones.py)   (tabla notificaciones)
```

Nginx (ya configurado, ver `docs/DESPLIEGUE_VPS.md`) hace de proxy inverso hacia el backend
(puerto interno fijo, p. ej. `8001`) y sirve el build estático de React; Streamlit corre en su
propio puerto interno (p. ej. `8501`) detrás del mismo Nginx si se decide exponerlo. No hay
Docker en producción — el despliegue es `git pull` + `systemd` (`gestion-docente-api.service`,
`gestion-docente-streamlit.service`) reiniciado, tal como ya está documentado. `docker-compose.yml`
en la raíz del repo sigue siendo **solo para levantar Postgres en desarrollo local**, no para
producción.

Se sigue la misma arquitectura modular ya usada: routers FastAPI delgados
(`backend/api/routers/tareas.py`, etc.) que llaman a funciones de `db/repository.py` (la capa
que concentra las reglas de negocio y las consultas), esquemas Pydantic en
`backend/schemas/`, y RBAC vía dependencias (`requiere_roles`, `verificar_pertenece_a_programa`)
— ningún patrón nuevo de arquitectura, solo más módulos siguiendo el que ya existe.

---

# 29. Modelo de datos

## Tablas que se reutilizan tal cual (ya existen, no se tocan)

```text
usuarios                 -- responsable, asignador, autorizador, etc.
roles                     -- director / secretario / docente / secretaria_programa
programas                 -- alcance multi-programa
periodos_academicos        -- periodo académico opcional de la tarea
eventos_calendario         -- días no hábiles / fechas institucionales
notificaciones             -- canal in-app (se le agrega tarea_id nullable)
```

## Tablas nuevas del módulo (nomenclatura en español, snake_case — igual convención que el
resto de `db/models.py`)

```text
tareas
subtareas
dependencias_tarea
categorias_tarea
prioridades_tarea
estados_tarea
tipos_tarea
etiquetas_tarea
tarea_etiquetas              -- tabla puente tarea <-> etiqueta (muchos a muchos)
tarea_responsables           -- responsable principal + secundarios (tabla puente)
comentarios_tarea
evidencias_tarea
evidencias_tarea_versiones
seguimiento_tarea
historial_tarea
evaluaciones_tarea
criterios_evaluacion
puntajes_evaluacion
solicitudes_ampliacion
permisos_delegados
plantillas_tarea
auditoria
```

Campos comunes en las tablas nuevas (igual convención que ya usa `db/models.py`:
`creado_en`/`actualizado_en` con `datetime.utcnow`, FKs a `usuarios.id` para
`creado_por_id`/`actualizado_por_id` donde aplique):

```text
id                (PK, serial)
creado_en         (DateTime, default=utcnow)
actualizado_en    (DateTime, default=utcnow, onupdate=utcnow)
creado_por_id     (FK usuarios.id, nullable)
actualizado_por_id (FK usuarios.id, nullable)
```

No se agregan columnas `deleted_at` / soft-delete genérico: el principio "no hay eliminación
física" ya se resuelve en este proyecto marcando estado (`estado = 'cancelada'`) en vez de un
flag de borrado transversal — se mantiene esa misma convención en vez de introducir un patrón
nuevo.

`indicators` / `indicator_values` **no se crean** (ver sección 18: los indicadores se calculan
al vuelo, como ya hace `DashboardInstitucional`). `refresh_tokens` **no se crea** por ahora: el
sistema ya usa un único JWT de vida corta/media (`JWT_EXPIRE_MINUTES`) sin rotación — añadir
refresh tokens sería un cambio transversal de autenticación ajeno al alcance de este módulo;
queda como decisión aparte si se necesita en el futuro.

---

# 30. Endpoints principales

Sin prefijo de versión (`/api/v1/...`): este proyecto no versiona la API hoy
(`backend/main.py` registra los routers directamente bajo `/api/...`) — se mantiene esa
convención por consistencia con el resto del sistema.

## Tareas

```text
GET    /api/tareas
POST   /api/tareas
GET    /api/tareas/{id}
PATCH  /api/tareas/{id}
POST   /api/tareas/{id}/asignar
POST   /api/tareas/{id}/reasignar
POST   /api/tareas/{id}/iniciar
POST   /api/tareas/{id}/enviar-revision
POST   /api/tareas/{id}/devolver
POST   /api/tareas/{id}/aprobar
POST   /api/tareas/{id}/cerrar
POST   /api/tareas/{id}/reabrir
POST   /api/tareas/{id}/suspender
POST   /api/tareas/{id}/cancelar
GET    /api/tareas/{id}/historial
```

## Subtareas y dependencias

```text
GET  /api/tareas/{id}/subtareas
POST /api/tareas/{id}/subtareas
PATCH /api/subtareas/{id}
GET  /api/tareas/{id}/dependencias
POST /api/tareas/{id}/dependencias
```

## Seguimiento, comentarios y evidencia

```text
GET  /api/tareas/{id}/seguimiento
POST /api/tareas/{id}/seguimiento
GET  /api/tareas/{id}/comentarios
POST /api/tareas/{id}/comentarios
GET  /api/tareas/{id}/evidencias
POST /api/tareas/{id}/evidencias
POST /api/evidencias/{id}/version
GET  /api/evidencias/{id}/descargar
```

## Ampliaciones y evaluaciones

```text
POST /api/tareas/{id}/solicitudes-ampliacion
POST /api/solicitudes-ampliacion/{id}/recomendar
POST /api/solicitudes-ampliacion/{id}/aprobar
POST /api/solicitudes-ampliacion/{id}/rechazar
POST /api/tareas/{id}/evaluaciones/preliminar
POST /api/tareas/{id}/evaluaciones/definitiva
```

## Categorías, prioridades, estados y plantillas (administración, solo Director)

```text
GET/POST/PATCH  /api/tareas-categorias
GET/POST/PATCH  /api/tareas-prioridades
GET/POST/PATCH  /api/tareas-plantillas
```

## Indicadores, reportes y auditoría

```text
GET /api/tareas/indicadores/dashboard
GET /api/tareas/indicadores/usuarios/{id}
GET /api/tareas/reportes/cumplimiento
GET /api/tareas/reportes/productividad
GET /api/tareas/reportes/vencidas
GET /api/auditoria                     -- solo Director
```

Las notificaciones **no** necesitan endpoints nuevos: se reutilizan
`GET /api/notificaciones` y `PATCH /api/notificaciones/{id}/leida` ya existentes
(`backend/api/routers/notificaciones.py`), solo agregando el nuevo evento como origen.

---

# 31. Seguridad

Se reutiliza tal cual lo ya implementado, sin introducir mecanismos nuevos:

- JWT (`python-jose`) con expiración — ya implementado, sin refresh tokens rotativos por ahora
  (ver sección 29).
- Hash de contraseña con `bcrypt` — ya implementado (`db/auth.py`).
- RBAC por rol vía `requiere_roles(...)` — ya implementado, se agregan los roles/combinaciones
  que necesite cada endpoint nuevo.
- Aislamiento multi-programa vía `verificar_pertenece_a_programa` — ya implementado.
- HTTPS vía Nginx + Let's Encrypt — ya documentado en `docs/DESPLIEGUE_VPS.md`.
- CORS restringido (`backend/core/config.py::CORS_ORIGINS`) — ya implementado.
- Rate limiting y bloqueo por intentos fallidos — ya implementado
  (`backend/core/rate_limit.py`, tabla `intentos_login_fallidos`); se reutiliza la misma
  función genérica para limitar acciones sensibles del módulo de tareas si hiciera falta
  (p. ej. exportar reportes masivamente).
- Validación de extensión/MIME y tamaño de archivo — ya implementado
  (`agente_notas/almacenamiento.py`), se extiende con la whitelist propia de evidencias.
- Sanitización de nombre de archivo para `Content-Disposition` — ya implementado
  (`nombre_seguro_para_header`).
- Protección contra path traversal al servir descargas — ya implementado
  (`ruta_absoluta_segura`).
- Auditoría de acciones sensibles — nueva tabla `auditoria` (sección 29), poblada desde
  `db/repository.py` en cada acción listada en la sección 24.
- Principio de mínimo privilegio y "sin eliminación física" — ya son principios seguidos en
  todo el proyecto, se mantienen igual aquí.

No se agrega HttpOnly/SameSite cookies (el frontend ya usa `localStorage` + header
`Authorization: Bearer`, patrón ya establecido) ni un WAF/Cloudflare nuevo — fuera del alcance
de este módulo.

---

# 32. Producción

Se despliega igual que el resto del sistema (ver `docs/DESPLIEGUE_VPS.md`), sin Docker ni
CI/CD nuevos:

- Mismo VPS, mismo Nginx, mismos servicios `systemd` (`gestion-docente-api`,
  `gestion-docente-streamlit`) — el módulo de tareas no necesita un proceso ni un puerto nuevo,
  solo más routers dentro del mismo `backend/main.py`.
- Migraciones: script idempotente nuevo en `scripts/`, ejecutado a mano tras el `git pull` en
  el servidor (igual que todas las migraciones anteriores de este proyecto).
- Backups: la misma estrategia de backup de PostgreSQL ya definida para el resto de las tablas
  cubre las tablas nuevas automáticamente (es la misma base de datos).
- Carpeta de evidencias (`evidencias_tareas/`) sigue la misma convención de
  `entregas_docentes/`/`repositorio_asignaturas/`: fuera del repo git, con su propia rutina de
  backup (ver sección 1.4 de `docs/DESPLIEGUE_VPS.md`).
- Pruebas: `pytest` + `vitest` ya integrados al flujo de trabajo del proyecto (se ejecutan a
  mano antes de cada entrega, no hay pipeline de CI/CD automático todavía — introducir uno
  queda como mejora futura opcional, no requisito de esta fase).
- Documentación: este archivo (`docs/especificacionModuloTareas.md`) + Swagger/OpenAPI que
  FastAPI ya expone automáticamente en `/docs` (nada que configurar aparte).

---

# 33. Datos iniciales

## Roles

Ya existen — no se crean de nuevo (`director`, `secretario`, `docente`, `secretaria_programa`).

## Estados de tarea (tabla `estados_tarea`, con `icono`/`color` por estado)

```text
BORRADOR
PROGRAMADA
SIN_COMENZAR
EN_PROCESO
PENDIENTE_REVISION
DEVUELTA_OBSERVACIONES
TERMINADA
SUSPENDIDA
CANCELADA
VENCIDA   -- asignado automáticamente por el sistema, ver sección 7
```

## Prioridades (tabla `prioridades_tarea`)

```text
BAJA
MEDIA
ALTA
CRITICA
```

## Categorías (tabla `categorias_tarea`)

Las 22 listadas en la sección 9, sembradas por el script de migración/seed del módulo (mismo
patrón que `scripts/` ya usa para sembrar catálogos, p. ej. cortes/roles iniciales).

No se crea un usuario Director "inicial" nuevo: el sistema ya tiene sus cuentas de Director
por programa (creadas vía el flujo de administración de usuarios existente).

---

# 34. Fases de implementación

```text
Fase 1: modelo de datos del módulo (tareas, categorías, prioridades, estados) +
        migración + repository + RBAC + endpoints CRUD básicos de tarea
Fase 2: subtareas, dependencias y transiciones de estado (con sus reglas de negocio)
Fase 3: comentarios/observaciones y evidencias (con almacenamiento en disco)
Fase 4: seguimiento e historial (auditoría de cambios de la propia tarea)
Fase 5: solicitudes de ampliación y evaluación (preliminar/definitiva)
Fase 6: indicadores (cálculo al vuelo) y reportes (PDF/Excel/CSV)
Fase 7: notificaciones (reutilizando el sistema in-app + correo ya existente) y recurrencia
Fase 8: dashboards y vistas (Lista/Tabla/Kanban/Calendario/Timeline) por rol, en React
        y su paralelo en Streamlit
Fase 9: auditoría transversal (tabla auditoria) + pruebas (pytest/vitest) + revisión de
        seguridad
Fase 10: migración final en el VPS de producción + verificación end-to-end con los 4 roles
```

Cada fase se presenta y se aprueba antes de implementarse (igual que todas las fases
anteriores de este proyecto) — no se construye todo en una sola tanda.

---

# 35. Instrucciones para Claude Code

Antes de escribir código de cada fase:

1. Presentar el plan de esa fase (qué tablas, qué endpoints, qué páginas).
2. Mostrar los archivos que se van a crear/tocar.
3. Describir las entidades nuevas y cómo se relacionan con las ya existentes.
4. Definir los endpoints exactos.
5. Definir qué roles pueden hacer qué (reutilizando `requiere_roles`).
6. Escribir el script de migración (idempotente, siguiendo `scripts/migrar_*.py`).
7. Sembrar catálogos si aplica.
8. Implementar las reglas de negocio de esa fase en `db/repository.py`.
9. Escribir pruebas (`pytest` para backend, `vitest` para los componentes React nuevos).
10. Verificar en el Browser pane con los roles relevantes antes de dar la fase por cerrada.
11. Esperar aprobación antes de continuar con la siguiente fase.

---

# 36. Criterios de aceptación

- Los cuatro roles funcionan correctamente dentro del módulo de tareas.
- El Director es el único que aprueba, evalúa definitivamente, cierra y reabre.
- El Secretario coordina, asigna y hace seguimiento/evaluación preliminar.
- El Docente ejecuta, reporta avance y solicita ampliaciones.
- La Secretaria del Programa gestiona borradores y apoyo operativo/documental.
- Los permisos se validan en frontend y, sobre todo, en backend.
- Las acciones críticas quedan auditadas en la tabla `auditoria`.
- No existe eliminación física de tareas/evidencias/evaluaciones/auditoría.
- El flujo de estados se respeta y las transiciones inválidas se rechazan en backend.
- Las evidencias conservan versiones.
- Los indicadores reflejan los datos reales en todo momento (cálculo al vuelo).
- Los reportes respetan permisos y confidencialidad.
- La interfaz es responsive y accesible (WCAG 2.2 AA razonable) en React, con paridad en
  Streamlit.
- La API queda documentada automáticamente vía Swagger/OpenAPI de FastAPI.
- Existen pruebas automatizadas (`pytest` + `vitest`) para la lógica de negocio nueva.
- El módulo se despliega en el mismo VPS, con los mismos mecanismos ya usados (systemd + Nginx,
  sin Docker en producción).

---

# 37. Estructura de archivos (extiende el repositorio actual, sin monorepo nuevo)

```text
informe_de_gestion/
├── db/
│   ├── models.py                  <- se agregan las clases nuevas (Tarea, Subtarea, ...)
│   └── repository.py              <- se agregan las funciones del módulo de tareas
├── backend/
│   ├── schemas/
│   │   └── tarea.py                <- Pydantic schemas nuevos
│   └── api/routers/
│       ├── tareas.py
│       ├── tareas_categorias.py
│       └── auditoria.py
├── agente_notas/
│   └── almacenamiento.py           <- se extiende con evidencias_tareas/
├── scripts/
│   └── migrar_modulo_tareas.py     <- nuevo, mismo patrón idempotente de siempre
├── frontend/src/
│   ├── layouts/                    <- ya existen (Docente/Direccion/Secretaria), se les
│   │                                  agrega el ítem "📋 Tareas" al sidebar de cada uno
│   ├── pages/tareas/                <- páginas nuevas del módulo (una por vista/rol)
│   └── components/tareas/           <- componentes reutilizables (tarjeta de tarea,
│                                        Kanban, formulario, etc.)
├── vistas/
│   └── tareas.py                    <- vista Streamlit del módulo (funciones
│                                        render_* registradas como st.Page, mismo
│                                        patrón que vistas/direccion.py y vistas/docente.py)
├── tests/
│   ├── test_tareas.py
│   └── test_tareas_permisos.py
└── docs/
    └── especificacionModuloTareas.md   <- este documento
```

No se crea un monorepo (`apps/`, `packages/`), ni una carpeta `infrastructure/docker/` nueva:
el módulo vive dentro del mismo repositorio, con la misma estructura ya usada por el resto del
sistema.

---

**Fin del documento**
