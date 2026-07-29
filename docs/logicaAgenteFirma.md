# Lógica del Agente de Verificación de Firmas

Este documento explica en detalle el **Agente de Verificación de Firmas**: qué
problema resuelve, cómo razona internamente, y cómo queda conectado con la
base de datos, el backend (FastAPI) y los dos frontends (React y Streamlit).
Complementa a `docs/entendiendoLogica.md` (que explica la arquitectura
general del proyecto) enfocándose solo en esta funcionalidad.

---

## 1. El problema que resuelve

Los docentes suben, en la sesión **"Entrega de documentos"**, los soportes de
cada corte (listas de asistencia, notas firmadas, informe de gestión
docente, etc.). Antes de este agente, el Director, el Secretario Académico y
la Secretaria del Programa tenían que **abrir cada archivo uno por uno** para
confirmar si de verdad estaba firmado antes de aprobar o rechazar la entrega.

El agente automatiza esa primera revisión: analiza cada archivo **apenas se
sube**, da un veredicto, lo muestra en pantalla, y si algo no parece estar
firmado, **notifica de inmediato** a los tres roles revisores — para que
puedan enviarle la observación al docente (usando el botón "❌ Rechazar" que
ya existía) y este vuelva a firmar y cargar.

## 2. Una limitación honesta, explicada primero

**Detectar una firma manuscrita dentro de una imagen escaneada no se puede
hacer de forma confiable con reglas de programación simples** — eso
requeriría un modelo de visión por computador entrenado específicamente para
reconocer trazos de firma, algo que este proyecto no incluye. Por eso el
agente **nunca dice "sí" o "no" a ciegas** cuando no tiene evidencia sólida:
cuando no puede confirmar nada con certeza razonable, dice explícitamente
*"revisar manualmente"* en vez de arriesgar un falso positivo o negativo.
Esto es una decisión de diseño deliberada, no una limitación oculta.

## 3. Los 4 veredictos posibles

El agente clasifica cada documento en uno de estos 4 casos, de mayor a menor
certeza:

| Veredicto | `firma_detectada` | Confianza | Cuándo se da |
|---|:---:|:---:|---|
| ✅ Firma digital | `True` | alta | El PDF trae una **firma digital real** (certificado electrónico embebido en el archivo) |
| ✅ Mención textual | `True` | media | El **texto** del PDF contiene una palabra de firma ("firma", "firmado"...) **junto al nombre** del docente |
| ⚠️ Revisar manualmente | `None` | baja | Es una imagen (jpg/png), un Excel, o un PDF con imágenes incrustadas (posible firma/sello escaneado) sin ninguna de las señales anteriores |
| ❌ Sin firma | `False` | media | El PDF no tiene firma digital, no menciona firma en el texto, y no trae ninguna imagen |

`firma_detectada` se guarda como un booleano de **tres estados** (no dos):
`True`, `False`, o `None` (indeterminado) — justamente para poder distinguir
"confirmado que no está firmado" de "no se pudo determinar, hay que mirarlo".

## 4. Dónde vive el código: `agente_notas/agente_firmas.py`

Este archivo tiene dos funciones públicas:

### `analizar_documento(nombre_archivo, contenido, nombre_docente)`

Recibe el nombre del archivo, sus bytes crudos, y el nombre completo del
docente que lo subió. Por dentro, decide qué análisis aplicar según la
extensión:

```
                    ┌─ ¿Es .pdf? ──┐
                    │              │
                   Sí              No
                    │              │
      ┌─────────────┴───────┐      └─ .jpg/.jpeg/.png → indeterminado
      │ ¿Tiene firma        │         .xlsx/.xls      → indeterminado
      │ digital (campo      │         otro            → indeterminado
      │ /Sig en el PDF)?    │
      └─────────┬───────────┘
             Sí  │  No
   True,alta ◄───┘  │
                    ▼
      ¿El texto menciona "firma"
      Y aparece el nombre del docente?
             Sí │ No
  True,media◄───┘  │
                   ▼
        ¿El PDF tiene imágenes incrustadas?
             Sí │ No
  None,baja ◄────┘  │
                     ▼
              False, media
```

Las herramientas que usa para cada paso:
- **`pypdf.PdfReader`**: para leer los **campos de formulario** del PDF
  (`reader.get_fields()`) y revisar si alguno tiene tipo `/Sig` (firma
  digital), y para inspeccionar los recursos de cada página (`/Resources` →
  `/XObject`) en busca de imágenes incrustadas.
- **`pdfplumber`**: para extraer el **texto** del PDF (la misma librería que
  ya usa el "agente de notas" de `agente_notas/core.py` para leer los PDF de
  Academusoft — reutilizar la misma herramienta ya probada en el proyecto).
- **`_normalizar(texto)`**: quita tildes y pasa a minúsculas (usa
  `unicodedata`), para que "Wilman Andrés Quiñonez" y una mención en el texto
  como "WILMAN QUIÑONEZ" se puedan comparar sin que un acento arruine la
  coincidencia. Solo se comparan palabras de más de 3 letras del nombre (para
  no hacer falsos positivos con conectores como "de", "la").

Devuelve siempre un diccionario con 3 llaves:
```python
{
    "firma_detectada": True | False | None,
    "confianza": "alta" | "media" | "baja",
    "detalle": "texto explicando por qué se llegó a ese veredicto",
}
```
El campo `detalle` es importante: es lo que ve el revisor al pasar el mouse
sobre el ícono en React, o en la columna de la tabla en Streamlit — nunca se
espera que un usuario confíe en el ícono solo, sin poder ver el porqué.

### `resumen_entrega(documentos)`

Recibe la lista de documentos de una Entrega completa y calcula un resumen:
```python
{
    "todos_firmados": bool,          # True solo si TODOS tienen firma_detectada == True
    "documentos_pendientes": [...],   # los que no (False o None), para listarlos
}
```
Esta función es la que le permite a la pantalla de revisión mostrar, de un
vistazo, si una entrega completa "cumple con todas las firmas" o no — y si
no cumple, cuáles específicamente faltan. La usan **tanto el backend
(`backend/api/routers/entregas.py`) como Streamlit (`vistas/entregas.py`)**,
para no repetir la lógica dos veces.

## 5. La base de datos: 3 columnas nuevas

El agente guarda su veredicto directamente en la tabla `documentos_entrega`
(modelo `DocumentoEntrega` en `db/models.py`), agregando 3 columnas:

| Columna | Tipo | Significado |
|---|---|---|
| `firma_detectada` | `BOOLEAN` (nullable) | `True`/`False`/`NULL` (indeterminado) |
| `firma_confianza` | `VARCHAR(10)` (nullable) | `"alta"`, `"media"` o `"baja"` |
| `firma_detalle` | `VARCHAR(300)` (nullable) | La explicación legible del veredicto |

La migración que las creó es `scripts/migrar_agente_firmas.py` (usa `ALTER
TABLE ... ADD COLUMN IF NOT EXISTS`, así que es segura de correr más de una
vez). Estas columnas quedan **nulas para cualquier documento subido antes**
de que existiera el agente — eso es intencional: el agente solo evalúa
documentos nuevos, no reinterpreta archivos históricos.

## 6. El backend: cuándo se ejecuta el agente

El agente se invoca en **un solo punto** del backend:
`backend/api/routers/entregas.py`, función `subir_documento()` — el endpoint
`POST /api/entregas/documentos`.

Orden exacto de lo que pasa cuando un docente sube un archivo:

```
1. El docente envía el archivo (formulario con periodo, corte, tipo, archivo)
2. subir_documento() lee los bytes: contenido = archivo.file.read()
3. veredicto = analizar_documento(nombre_archivo, contenido, usuario.nombre_completo)
   ── AQUÍ corre el agente, ANTES de guardar nada ──
4. guardar_archivo_entrega(...)          -> guarda el archivo en disco
5. agregar_documento_entrega(...)        -> guarda la fila en la BD,
                                             incluyendo firma_detectada/
                                             firma_confianza/firma_detalle
6. Si veredicto["firma_detectada"] is not True:
       notificar_usuarios(ids_personal_revisor(db), mensaje, entrega_id=...)
   ── se avisa a Director + Secretario + Secretaria del Programa ──
7. Se devuelve la Entrega completa (con el resumen de firmas incluido)
```

El mensaje de la notificación se arma así (ejemplo real):
> ⚠️ Wilman Andrés Quiñonez subió 'lista_asistencia_corte1.pdf' (Lista de
> asistencia) para el Corte 1 — el agente no detectó firma (No se detectó
> firma digital, texto de firma, ni imágenes en el documento). Revísalo antes
> de aprobar la entrega.

Esta notificación usa el **mismo sistema de notificaciones in-app** que ya
existía para avisos de aprobación/rechazo (`db.repository.notificar_usuarios`
+ `ids_personal_revisor`) — no se creó un canal nuevo, se reutilizó el que
ya funcionaba.

### Cómo se expone en la API (`backend/schemas/entrega.py`)

- `DocumentoEntregaOut` ahora incluye `firma_detectada`, `firma_confianza`,
  `firma_detalle` — así viaja en cada documento dentro de la respuesta JSON.
- `EntregaOut` incluye `todos_firmados_agente: bool` — el resumen calculado
  con `resumen_entrega()` justo antes de armar la respuesta
  (`_out()` en `entregas.py`), para que el frontend no tenga que recalcularlo
  él mismo a partir de la lista de documentos.

## 7. El frontend React: cómo se ve

Archivo: `frontend/src/components/EntregasDocumentos.tsx`.

- **`badgeFirma(documento)`**: función que decide qué ícono y color mostrar
  por documento — ✅ verde (`firma_detectada === true`), ❌ rojo
  (`firma_detectada === false`), o ⚠️ naranja (`null`, indeterminado). El
  atributo `title` del `<span>` muestra el `firma_detalle` como *tooltip* al
  pasar el mouse.
- **`bannerFirmas(entrega)`**: si `entrega.todos_firmados_agente` es `false`
  y hay documentos, muestra un mensaje de advertencia (`mensaje
  mensaje--warning`) listando los nombres de archivo que el agente marcó
  para revisar.
- La tabla de documentos (`tablaDocumentos()`) ahora tiene una columna
  **"Firma (agente)"** entre "Archivo" y "Tamaño".
- El banner se muestra tanto en la vista del **docente** (para que sepa de
  una vez si algo quedó marcado, sin esperar a que lo rechacen) como en la
  vista de los **revisores** (Director/Secretario/Secretaria del Programa),
  justo antes de la tabla de cada entrega.

Los tipos de TypeScript (`frontend/src/types/index.ts`) se actualizaron para
que `DocumentoEntrega` tenga `firma_detectada: boolean | null`,
`firma_confianza: string | null`, `firma_detalle: string | null`, y `Entrega`
tenga `todos_firmados_agente: boolean` — reflejando exactamente lo que manda
el backend.

## 8. Streamlit: la misma lógica, sin pasar por la API

Archivo: `vistas/entregas.py`. Como Streamlit no tiene una capa de API en el
medio (ver `docs/entendiendoLogica.md`, sección 8), el flujo es más directo:

- Dentro del formulario de subida (`_render_docente`), justo después de leer
  `contenido = archivo.getvalue()`, se llama a
  `analizar_documento(archivo.name, contenido, nombre_docente)` directamente
  — **la misma función** que usa el backend, importada desde
  `agente_notas.agente_firmas` (no hay dos implementaciones distintas).
- El veredicto se pasa a `agregar_documento_entrega(...)` igual que en el
  backend, y si `firma_detectada is not True`, se llama a
  `notificar_usuarios(...)` con el mismo formato de mensaje.
- **`_etiqueta_firma(documento)`**: la versión Streamlit de `badgeFirma()`
  — devuelve el texto del ícono para la columna "Firma (agente)" del
  `st.dataframe(...)`.
- **`_banner_firmas(entrega)`**: la versión Streamlit de `bannerFirmas()`
  — usa `resumen_entrega()` (la misma función que el backend) y muestra
  `st.warning(...)` si hace falta.

## 9. Un recorrido completo, de punta a punta

```
1. El docente sube "notas_corte1.pdf" (tipo: Notas firmadas) desde React
   o Streamlit.

2. agente_notas.agente_firmas.analizar_documento() se ejecuta:
   - ¿Firma digital?          No
   - ¿Menciona "firma" +
     nombre del docente?      No
   - ¿Tiene imágenes?         Sí (es un PDF escaneado)
   → veredicto = {"firma_detectada": None, "confianza": "baja",
                   "detalle": "El PDF contiene imágenes... requiere
                   revisión manual."}

3. Se guarda en documentos_entrega: firma_detectada = NULL,
   firma_confianza = 'baja', firma_detalle = '...'

4. Como firma_detectada no es True, se notifica a Director, Secretario
   Académico y Secretaria del Programa:
   "⚠️ ... subió 'notas_corte1.pdf' ... el agente no pudo confirmar la
   firma (...). Revísalo antes de aprobar la entrega."

5. El Director abre "Entrega de documentos": ve el banner de advertencia,
   la columna "Firma (agente)" con ⚠️ Revisar manualmente, y — como
   corresponde a algo indeterminado, no confirmado como ausente — abre el
   PDF con el botón "👁️ Ver" para revisarlo él mismo.

6. Si al verlo confirma que SÍ está firmado a mano: aprueba la entrega
   normalmente (el veredicto del agente no bloquea nada, es solo una
   ayuda visual). Si NO está firmada: la rechaza con un comentario
   ("Falta tu firma en las notas del Corte 1, vuelve a cargar el
   documento firmado"), y el docente lo ve en su propia pantalla para
   corregirlo.
```

## 10. Verificación y pruebas

El agente se probó de punta a punta (usuarios y archivos sintéticos, todos
eliminados después de la prueba):
- Un PDF con el texto "Firmado por: [nombre del docente]" → veredicto
  `True`, confianza `media`.
- Un PDF de solo texto sin ninguna mención de firma → veredicto `False`,
  confianza `media`.
- Se confirmó que `todos_firmados_agente` cambia correctamente de `True` a
  `False` al agregar el segundo documento.
- Se confirmó que la notificación llega al rol Director cuando corresponde.

## 11. Qué NO hace el agente (para que quede claro)

- **No abre ni bloquea la aprobación de una entrega.** El Director/
  Secretario/Secretaria del Programa siempre tienen la última palabra —
  el agente solo les ahorra tener que adivinar por dónde empezar a mirar.
- **No verifica la autenticidad de una firma digital** más allá de
  confirmar que el campo de firma existe en el PDF (no valida el
  certificado ni si fue alterado después de firmarse).
- **No usa inteligencia artificial ni visión por computador** — es lógica
  de reglas simple (leer campos del PDF, buscar palabras clave, contar
  imágenes). Es deliberadamente conservador: prefiere decir "no estoy
  seguro" antes que inventar una certeza falsa.

---

## 12. Archivos relevantes (referencia rápida)

| Archivo | Qué contiene |
|---|---|
| `agente_notas/agente_firmas.py` | El agente en sí: `analizar_documento()` y `resumen_entrega()` |
| `scripts/migrar_agente_firmas.py` | Migración de las 3 columnas nuevas |
| `db/models.py` | Columnas `firma_detectada`/`firma_confianza`/`firma_detalle` en `DocumentoEntrega` |
| `db/repository.py` | `agregar_documento_entrega()` extendida para guardar el veredicto |
| `backend/api/routers/entregas.py` | Llama al agente al subir, dispara la notificación, arma el resumen |
| `backend/schemas/entrega.py` | Expone los campos nuevos en la API |
| `frontend/src/types/index.ts` | Tipos TypeScript actualizados |
| `frontend/src/components/EntregasDocumentos.tsx` | `badgeFirma()`, `bannerFirmas()`, columna nueva en la tabla |
| `vistas/entregas.py` | Misma lógica para Streamlit: `_etiqueta_firma()`, `_banner_firmas()` |
