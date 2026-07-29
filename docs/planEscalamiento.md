# Plan: soporte multi-programa académico

## Contexto

El sistema fue construido para UN solo programa académico (Ingeniería de Sistemas). Tras la prueba piloto, la universidad planea registrar ~15 programas académicos con ~250 docentes en total. Una auditoría exhaustiva (dos agentes de exploración + verificación directa) confirmó que **no existe ningún concepto de "programa" en el modelo de datos**: el texto "Ingeniería de Sistemas" está hardcodeado en ~15 lugares (PDF de informes, aviso de privacidad legal, encabezados de React/Streamlit), y ninguna consulta administrativa (`listar_docentes`, `resumen_dashboard_institucional`, `listar_entregas`, `listar_usuarios`, `listar_repositorio_asignaturas`, notificaciones) filtra por programa. Hoy, cualquier Director/Secretario/Secretaria ve y puede aprobar/rechazar/borrar datos de TODO el sistema, y cada evento de entrega notifica a TODO el personal administrativo sin importar programa.

Decisiones ya confirmadas con el usuario:
1. **Cada uno de los 15 programas es administrativamente independiente** — un Director/Secretario/Secretaria de un programa nunca ve datos de otro. No hay rol "super-admin".
2. **El calendario académico es institucional/compartido** — un solo `PeriodoAcademico` activo para todos los programas (no se toca `Corte`, `PeriodoAcademico`, `EventoCalendario`).
3. **El repositorio de sílabos/programas de asignatura también es por programa** (confirmado explícitamente por el usuario) — cada programa tiene sus propias materias, sin colisión de nombres entre programas.
4. El programa se resuelve **siempre desde el usuario autenticado**, nunca desde un parámetro que el cliente pueda manipular — por eso no se agrega ningún selector de programa visible en la UI.

El objetivo de este cambio es agregar una entidad `Programa` real y usarla como filtro obligatorio en cada capa (BD → repositorio → autorización → routers → notificaciones → UI/PDF/aviso legal), sin romper el piloto de Ingeniería de Sistemas mientras se construye.

---

## Fase 1 — Modelo de datos (`db/models.py`)

**Tabla nueva `Programa`** (catálogo, ~15 filas):
```python
class Programa(Base):
    __tablename__ = "programas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)  # "Ingeniería de Sistemas"
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)   # "ing-sistemas"
    logo_ruta_archivo: Mapped[str | None] = mapped_column(String(500))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```
No se agrega texto legal por programa: el aviso de privacidad es un documento institucional (Ley 1581/2012, Universidad del Pacífico) donde solo varía el *nombre del programa*, no el marco legal (ver Fase 9).

**`Usuario`** (línea ~102): agrega `programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"), index=True)`.
- FK directa y simple, **no tabla puente** — la decisión #1 (independencia sin solape) hace innecesaria una relación muchos-a-muchos.
- Nullable a nivel de columna (la cuenta bootstrap `admin` de `db/seed.py` no pertenece a ningún programa real); la regla "todo usuario activo con rol operativo debe tener programa" se aplica en `crear_usuario` y se cubre con una prueba, no con un `NOT NULL` de BD.

**`AsignacionAcademica.programa`** (línea ~135, hoy `String(150)` libre, nunca usado para filtrar): se reemplaza por `programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), nullable=False)` + `programa: Mapped["Programa"] = relationship()`. Se resuelve siempre desde `docente.programa_id`, nunca desde un argumento externo — esto elimina de raíz los dos literales hardcodeados `"Ingeniería de Sistemas"` en `backend/services/informe_service.py:126` y `vistas/docente.py:423`.

**`RepositorioAsignatura`** (línea ~366, confirmado por el usuario que es por programa): hoy `asignatura: Mapped[str] = mapped_column(String(150), unique=True, ...)` — el `unique=True` es GLOBAL (constraint real en Postgres: `repositorio_asignaturas_asignatura_key`). Cambia a:
```python
programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), nullable=False, index=True)
asignatura: Mapped[str] = mapped_column(String(150), nullable=False)
__table_args__ = (UniqueConstraint("programa_id", "asignatura", name="uq_repositorio_programa_asignatura"),)
```
`docente_id` en esta tabla es nullable (una materia puede no tener docente asignado), así que `programa_id` **no se puede derivar del docente** — se fija explícitamente al crear la entrada (Fase 4).

**`Entrega`**: se agrega `programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), nullable=False, index=True)`, desnormalizado desde `docente.programa_id` al crearse (`obtener_o_crear_entrega`). Evita un JOIN a `Usuario` en cada llamada a `listar_entregas`, que ya es la consulta de mayor volumen esperado.

**Sin cambios** (heredan el alcance transitivamente, o quedan institucionales por la decisión #2): `Corte`, `PeriodoAcademico` (incluido el índice `uq_un_solo_periodo_activo` agregado en la auditoría anterior), `EventoCalendario`, `InformeCorte`, `NotaEstudiante`, `DocumentoEntrega`, `Notificacion`, `AceptacionPoliticaTratamiento`, `IntentoLoginFallido`, `Rol` (catálogo global de 4 roles, correcto tal cual).

---

## Fase 2 — Migración de datos (`scripts/migrar_multi_programa.py`)

Sigue el patrón idempotente ya usado en `scripts/migrar_consentimiento_datos.py` / `scripts/migrar_periodo_activo_y_calendario.py` (ALTER TABLE con `IF NOT EXISTS`, sin Alembic):

1. `CREATE TABLE IF NOT EXISTS programas (...)`.
2. Insertar (si no existe) `Programa(nombre="Ingeniería de Sistemas", codigo="ing-sistemas")` — el programa piloto actual.
3. `ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS programa_id ...`; backfill: todo usuario real (`username <> 'admin'`) → `programa_id` del programa piloto.
4. `ALTER TABLE asignaciones_academicas ADD COLUMN IF NOT EXISTS programa_id ...`; backfill desde `usuarios.programa_id` vía `docente_id`; `SET NOT NULL`; **recién entonces** `DROP COLUMN programa` (la vieja columna de texto libre).
5. `ALTER TABLE repositorio_asignaturas ADD COLUMN IF NOT EXISTS programa_id ...`; backfill al programa piloto (todas las filas existentes son de ese programa); `SET NOT NULL`; `DROP CONSTRAINT IF EXISTS repositorio_asignaturas_asignatura_key` (nombre real confirmado); `CREATE UNIQUE INDEX IF NOT EXISTS uq_repositorio_programa_asignatura ON repositorio_asignaturas (programa_id, asignatura)`.
6. `ALTER TABLE entregas ADD COLUMN IF NOT EXISTS programa_id ...`; backfill desde `usuarios.programa_id` vía `docente_id`; `SET NOT NULL`.
7. Imprimir resumen de conteos migrados (mismo estilo `print()` de los scripts existentes).

El alta de los 14 programas nuevos (nombre, código, Director inicial por programa) es una extensión posterior de este mismo script o uno hermano, siguiendo el patrón de `USUARIO_BOOTSTRAP` en `db/seed.py` — **no antes** de verificar que los pasos 1-6 no rompieron el piloto (con solo 1 programa en la tabla, todo filtro por `programa_id` es un no-op equivalente al comportamiento actual).

---

## Fase 3 — Autorización (`backend/api/deps.py`)

Se agrega una función reutilizable, generalizando el patrón que YA existe en `_verificar_acceso_entrega` (`backend/api/routers/entregas.py`) y `_verificar_permiso_programa` (`backend/api/routers/repositorio_asignaturas.py`) — ambas hoy comparan `docente_id`, se les añade el mismo tipo de chequeo para `programa_id`:

```python
def verificar_pertenece_a_programa(programa_id_entidad: int | None, usuario: Usuario) -> None:
    if usuario.programa_id is None or programa_id_entidad != usuario.programa_id:
        raise HTTPException(status_code=403, detail="No puedes acceder a datos de otro programa académico.")
```

`requiere_roles()` no cambia (sigue siendo solo control por nombre de rol). El JWT tampoco cambia — `get_current_user` ya carga el `Usuario` completo desde la BD en cada request, así que `usuario.programa_id` está disponible sin codificarlo en el token.

---

## Fase 4 — Repositorio (`db/repository.py`)

Agregan `programa_id: int` como parámetro **obligatorio** (nunca opcional, para que sea imposible olvidarlo):

| Función | Cambio |
|---|---|
| `listar_docentes` | `+ programa_id`, filtra `Usuario.programa_id == programa_id` |
| `listar_usuarios` | `+ programa_id`, mismo filtro |
| `resumen_dashboard_institucional` | `+ programa_id`, extiende el `where` existente con `AsignacionAcademica.programa_id == programa_id` |
| `listar_entregas` | `+ programa_id`, usa la columna desnormalizada `Entrega.programa_id` (sin JOIN extra) |
| `listar_repositorio_asignaturas` | `+ programa_id` |
| `emails_personal_revisor` / `ids_personal_revisor` | `+ programa_id` — corrige el bug más urgente: hoy notifican a TODO el personal administrativo del sistema en cada evento de entrega |

Además:
- `obtener_o_crear_asignacion(...)`: se elimina el parámetro `programa: str | None`; resuelve `programa_id` internamente desde `session.get(Usuario, docente_id).programa_id`. Los dos call-sites (`backend/services/informe_service.py:126`, `vistas/docente.py:423`) dejan de pasar el literal hardcodeado.
- `crear_repositorio_asignatura(...)`: agrega `programa_id` (el del usuario administrativo que crea la entrada).
- `obtener_o_crear_entrega(...)`: fija `Entrega.programa_id` desde `docente.programa_id` al crear.

---

## Fase 5 — Notificaciones

Los 4 puntos de llamada en `backend/api/routers/entregas.py` (subir documento, aprobar, rechazar, confirmar revisión) pasan `usuario.programa_id` (o `entrega.programa_id`, ya en memoria) a `emails_personal_revisor`/`ids_personal_revisor`. Con esto, un evento en el Programa X deja de notificar a los 44 administrativos de los otros 14 programas.

---

## Fase 6 — Routers (`backend/api/routers/*.py`)

Patrón repetido: pasar `usuario.programa_id` a la función de repositorio; para endpoints que reciben un id de entidad ajena, llamar `verificar_pertenece_a_programa` tras el fetch.

- **`docentes.py`**: `listar()`/`detalle()` — si un `docente_id` no pertenece al programa del usuario, ya no aparece en la lista filtrada → 404 natural, sin necesitar un 403 aparte.
- **`dashboard.py`**: pasa `usuario.programa_id` a `resumen_dashboard_institucional`.
- **`entregas.py`**: `listar()`, `subir_documento()`, `aprobar()`, `rechazar()`; en `_verificar_acceso_entrega` agrega `verificar_pertenece_a_programa(entrega.programa_id, usuario)`.
- **`usuarios.py`**: `listar()` filtra por programa; `crear()` fija `programa_id = usuario.programa_id` en el nuevo usuario (nunca elegible desde el formulario — un Director no puede dar de alta a nadie en otro programa).
- **`repositorio_asignaturas.py`**: `listar()`/`crear()` (fija `programa_id=usuario.programa_id`) y en `detalle`/`actualizar`/`eliminar`/subir/descargar agrega `verificar_pertenece_a_programa` tras cada fetch por id.
- **`reportes.py`**: `reporte_docente()`/`reporte_consolidado()` pasan `usuario.programa_id`.
- **`informes.py`**: `borrar_informe()` — agrega verificación de que la asignación del informe pertenece al programa del director antes de borrar (hoy no verifica ni siquiera propiedad de docente).
- **`consentimiento.py`**: `politica()` (hoy sin ninguna dependencia de autenticación) agrega `usuario: Usuario = Depends(get_current_user)` para poder resolver el nombre del programa (ver Fase 9) — cambio necesario detectado al revisar el código real, no estaba en la exploración inicial.

Sin cambios: `periodos.py`, `calendario.py`, `notificaciones.py` (ya filtra por `usuario_id`), `auth.py`.

---

## Fase 7 — Frontend React

- `backend/schemas/auth.py` (`UsuarioOut`, hoy sin ningún campo de programa): agrega `programa_id: int | None` y `programa_nombre: str | None`. `backend/api/routers/auth.py` (`_usuario_out`) los llena desde `usuario.programa_id`/`usuario.programa.nombre`.
- `frontend/src/types/index.ts` (`interface Usuario`): agrega los mismos dos campos.
- `frontend/src/components/Header.tsx`: reemplaza el texto fijo "Programa de Ingeniería de Sistemas" por `{usuario?.programa_nombre ?? "Programa"}`.
- `frontend/src/pages/DireccionPage.tsx` y `frontend/src/components/DashboardInstitucional.tsx`: mismo reemplazo en sus textos descriptivos.
- **Sin selector de programa en la UI** — cada usuario pertenece a un único programa; el `programa_id` nunca viaja como parámetro elegible desde el cliente, siempre se deriva del JWT en el backend. Esto también cierra la puerta a manipular un `?programa_id=` en la URL.

---

## Fase 8 — Streamlit

- `app.py` (encabezado fijo) y `vistas/direccion.py` (texto descriptivo): reemplazan el nombre fijo por el del usuario en sesión.
- `vistas/docente.py:423`: se elimina el literal (ya resuelto en Fase 4).
- Cada vista que llama directo a `db.repository.*` (bypasa la API REST) — `vistas/direccion.py`, `vistas/entregas.py`, `vistas/repositorio_asignaturas.py` — se actualiza para pasar `programa_id` desde `st.session_state`.

---

## Fase 9 — PDF y aviso de privacidad

- `agente_notas/reporte_pdf.py`: `_encabezado(...)` recibe `programa_nombre` y `logo_ruta` como parámetros en vez de la constante de módulo `LOGO_PROGRAMA`. `ESCUDO_UNPA` no cambia (escudo institucional, igual para los 15 programas). Se propaga a través de `generar_reporte_docente`/`generar_reporte_consolidado`.
- `agente_notas/aviso_privacidad.py`: **corrección de detalle real** — `TEXTO_POLITICA` hoy es una constante de módulo (string plano), no una función. Se convierte en `texto_politica(programa_nombre: str) -> str` que interpola el nombre en los ~10 lugares donde hoy dice "Programa de Ingeniería de Sistemas"; `TITULO_POLITICA` y `VERSION_POLITICA` no cambian (no mencionan el programa). Se mantiene **una sola versión legal global** — el cambio es cosmético (nombre), no afecta el marco legal.
- `backend/api/routers/consentimiento.py`: `politica()` pasa a depender de `get_current_user` (ver Fase 6) para resolver `usuario.programa.nombre` y llamar `texto_politica(...)`.
- `vistas/consentimiento.py`: usa `texto_politica(programa_nombre)` en vez de importar `TEXTO_POLITICA` directo.

---

## Fase 10 — Pruebas (pytest + vitest, siguiendo los patrones ya existentes)

- **`tests/test_deps_rbac.py`**: agrega `TestVerificarPertenceAPrograma` (mismo patrón `_UsuarioFalso`, ahora con `.programa_id`).
- **Nuevo `tests/test_multi_programa.py`** (patrón de `tests/test_entregas_gate.py`, con la fixture `db_session` de rollback): crea 2 `Programa` + 1 docente por programa, y verifica que `listar_docentes`, `listar_entregas`, `emails_personal_revisor`, `ids_personal_revisor`, `listar_repositorio_asignaturas` con `programa_id=A` **nunca** devuelven filas del programa B — la prueba más importante de todo el plan, es la garantía de aislamiento que motivó el pedido.
- **`tests/test_acid.py`**: agrega una prueba de la constraint compuesta `uq_repositorio_programa_asignatura` — dos `RepositorioAsignatura` con el mismo nombre de materia en programas distintos deben coexistir; en el mismo programa, debe fallar (`IntegrityError`).
- Prueba de regresión: `obtener_o_crear_asignacion` siempre asigna el `programa_id` del docente, sin importar qué se le pase.
- **Frontend (vitest)**: `Header.test.tsx` verifica que renderiza `usuario.programa_nombre` en vez de texto fijo.

---

## Orden de ejecución recomendado

1. Fases 1-2 (modelo + migración) en desarrollo/staging — columnas nuevas, sin romper el piloto.
2. Fase 4 (repositorio) — se puede desplegar con `programa_id` obligatorio porque en este punto solo existe 1 programa en la BD.
3. Fases 3 y 6 (autorización + routers), uno por uno, cada uno con su prueba antes de pasar al siguiente.
4. Fase 5 (notificaciones), junto con `entregas.py`.
5. Fases 7-9 (React, Streamlit, PDF, aviso legal) — cosméticas una vez el backend devuelve `programa_nombre`.
6. Alta de los 14 programas nuevos — **solo después** de verificar que Ingeniería de Sistemas sigue funcionando exactamente igual (regresión cero).
7. Fase 10 en paralelo a cada fase anterior, no al final.

## Explícitamente fuera de alcance

`Corte`, `PeriodoAcademico` (incluido `uq_un_solo_periodo_activo`), `EventoCalendario` — calendario institucional compartido, confirmado por el usuario. Ningún rol "super-admin". JWT sin cambios. `InformeCorte`, `NotaEstudiante`, `DocumentoEntrega`, `Notificacion`, `AceptacionPoliticaTratamiento`, `IntentoLoginFallido` — heredan el alcance por FK transitiva, sin columna propia.

## Verificación end-to-end

- `python -m pytest` (68 pruebas existentes deben seguir en verde + las nuevas de la Fase 10).
- `cd frontend && npm test`.
- Prueba manual con datos reales: crear un 2.º programa de prueba + 1 docente + 1 director de ese programa; confirmar en el navegador (React) que el Director del programa piloto NO ve al docente nuevo, y viceversa; confirmar que aprobar una entrega en un programa no genera notificación al personal del otro.
- Confirmar que el piloto de Ingeniería de Sistemas (datos ya existentes) sigue funcionando idéntico tras la migración (mismos docentes, mismas entregas, mismo dashboard).
