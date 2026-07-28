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


def eliminar_archivo(ruta_relativa: str) -> None:
    ruta = ruta_absoluta_segura(ruta_relativa)
    if ruta is not None:
        ruta.unlink(missing_ok=True)
