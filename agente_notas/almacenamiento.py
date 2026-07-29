"""Almacenamiento en disco de archivos que la app guarda fuera de la base
de datos: los documentos que los docentes entregan (listas de
asistencia, notas firmadas, informe de gestión docente, etc.) y los
sílabos/programas de asignatura del repositorio de consulta. Los
archivos NUNCA se versionan (ver .gitignore) -- solo su ruta y metadatos
quedan en la base de datos (db.models.DocumentoEntrega /
db.models.RepositorioAsignatura)."""
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIO_ENTREGAS = RAIZ / "entregas_docentes"
DIRECTORIO_REPOSITORIO = RAIZ / "repositorio_asignaturas"
DIRECTORIOS_PERMITIDOS = (DIRECTORIO_ENTREGAS, DIRECTORIO_REPOSITORIO)

# Whitelist real de extensiones aceptadas para CUALQUIER archivo que un
# usuario suba (entregas y repositorio): el <input accept="..."> del
# frontend es solo una sugerencia de UI, no una validacion -- sin este
# chequeo en el servidor, alguien podia subir un .html/.svg con
# JavaScript embebido y, al descargarse con Content-Disposition
# "inline" (ver descargar_documento/_descargar en los routers), el
# navegador de un revisor (Director/Secretario/Secretaria) lo ejecutaria
# en el origen de la API (XSS almacenado).
EXTENSIONES_PERMITIDAS = {"pdf", "xlsx", "jpg", "jpeg", "png"}
TAMANO_MAXIMO_BYTES = 15 * 1024 * 1024  # 15 MB: de sobra para estos documentos


class ArchivoInvalido(ValueError):
    """Extension no permitida o archivo demasiado grande."""


def validar_archivo_subido(nombre_original: str, contenido: bytes) -> None:
    extension = nombre_original.lower().rsplit(".", 1)[-1] if "." in nombre_original else ""
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ArchivoInvalido(
            f"Tipo de archivo '.{extension}' no permitido. Solo se aceptan: "
            f"{', '.join(sorted(EXTENSIONES_PERMITIDAS))}."
        )
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise ArchivoInvalido(
            f"El archivo pesa {len(contenido) / (1024 * 1024):.1f} MB; el máximo permitido es "
            f"{TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB."
        )


def _sanitizar(nombre: str) -> str:
    """Nombre de archivo seguro para el sistema de archivos: sin acentos,
    sin espacios ni caracteres especiales, y con un largo razonable."""
    sin_acentos = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r"[^A-Za-z0-9._-]+", "_", sin_acentos).strip("_")
    return limpio[:120] or "archivo"


def _nombre_archivo_unico(prefijo: str, nombre_original: str) -> str:
    marca_tiempo = datetime.now().strftime("%Y%m%d%H%M%S")
    sufijo = uuid.uuid4().hex[:8]
    return f"{prefijo}_{marca_tiempo}_{sufijo}_{_sanitizar(nombre_original)}"


def guardar_archivo_entrega(
    periodo_nombre: str, docente_id: int, corte_numero: int, tipo_documento: str, nombre_original: str, contenido: bytes
) -> tuple[str, int]:
    """Guarda 'contenido' en disco bajo una ruta organizada por
    periodo/docente/corte y devuelve (ruta_relativa_al_proyecto,
    tamaño_en_bytes). La ruta relativa es lo que se guarda en
    DocumentoEntrega.ruta_archivo."""
    validar_archivo_subido(nombre_original, contenido)
    carpeta = DIRECTORIO_ENTREGAS / periodo_nombre / f"docente_{docente_id}" / f"corte_{corte_numero}"
    carpeta.mkdir(parents=True, exist_ok=True)

    ruta_absoluta = carpeta / _nombre_archivo_unico(tipo_documento, nombre_original)
    ruta_absoluta.write_bytes(contenido)

    ruta_relativa = ruta_absoluta.relative_to(RAIZ).as_posix()
    return ruta_relativa, len(contenido)


def guardar_archivo_repositorio(asignatura_id: int, tipo: str, nombre_original: str, contenido: bytes) -> tuple[str, int]:
    """Guarda el sílabo o el programa de asignatura de una materia del
    repositorio de consulta. 'tipo' es 'silabo' o 'programa'. Devuelve
    (ruta_relativa_al_proyecto, tamaño_en_bytes)."""
    validar_archivo_subido(nombre_original, contenido)
    carpeta = DIRECTORIO_REPOSITORIO / f"asignatura_{asignatura_id}"
    carpeta.mkdir(parents=True, exist_ok=True)

    ruta_absoluta = carpeta / _nombre_archivo_unico(tipo, nombre_original)
    ruta_absoluta.write_bytes(contenido)

    ruta_relativa = ruta_absoluta.relative_to(RAIZ).as_posix()
    return ruta_relativa, len(contenido)


def ruta_absoluta_segura(ruta_relativa: str) -> Path | None:
    """Resuelve una ruta guardada en BD a una ruta absoluta, verificando
    que quede dentro de uno de los DIRECTORIOS_PERMITIDOS (nunca confiar
    en una ruta a ciegas, aunque venga de nuestra propia BD). Devuelve
    None si el archivo no existe o la ruta intenta salir de esos
    directorios."""
    candidato = (RAIZ / ruta_relativa).resolve()
    for base in DIRECTORIOS_PERMITIDOS:
        try:
            candidato.relative_to(base.resolve())
        except ValueError:
            continue
        return candidato if candidato.is_file() else None
    return None


# Solo estas extensiones se sirven "inline" (mostradas en el navegador,
# como hacen los botones "Ver"). Se resuelve por whitelist explicita en
# vez de mimetypes.guess_type(nombre_archivo) sobre el nombre tal como lo
# escribio el usuario: adivinar el tipo por extension y mostrarlo inline
# es exactamente el vector de XSS que valida_archivo_subido ya bloquea en
# la subida, pero esta segunda barrera protege incluso archivos
# guardados antes de que existiera esa validacion.
_TIPOS_INLINE = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}


def tipo_y_disposicion(nombre_archivo: str) -> tuple[str, str]:
    """Devuelve (media_type, disposicion) para servir un archivo
    descargado: solo pdf/jpg/jpeg/png se muestran 'inline' en el
    navegador; cualquier otra extension (p.ej. xlsx, o cualquier cosa
    que no pase por la whitelist de subida) se fuerza a descarga binaria
    ('attachment' + application/octet-stream), que el navegador nunca
    ejecuta como HTML/script."""
    extension = nombre_archivo.lower().rsplit(".", 1)[-1] if "." in nombre_archivo else ""
    if extension in _TIPOS_INLINE:
        return _TIPOS_INLINE[extension], "inline"
    return "application/octet-stream", "attachment"


def nombre_seguro_para_header(nombre_archivo: str) -> str:
    """Elimina comillas dobles del nombre antes de interpolarlo en la
    cabecera Content-Disposition -- nombre_archivo es el nombre ORIGINAL
    tal como lo escribio quien subio el archivo, nunca el sanitizado."""
    return nombre_archivo.replace('"', "")


def eliminar_archivo(ruta_relativa: str) -> None:
    ruta = ruta_absoluta_segura(ruta_relativa)
    if ruta is not None:
        ruta.unlink(missing_ok=True)
