"""Repositorio de consulta de sílabos y programas de asignatura por
materia. Cualquier rol autenticado puede consultar, buscar por materia
y descargar. Director, Secretario Académico y Secretaria del Programa
cargan/actualizan el sílabo, crean/renombran asignaturas, reasignan el
docente y eliminan. Cada docente actualiza (sube o quita) el programa de
asignatura únicamente de la materia que él mismo dicta."""
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agente_notas.almacenamiento import (
    ArchivoInvalido,
    guardar_archivo_repositorio,
    nombre_seguro_para_header,
    ruta_absoluta_segura,
    tipo_y_disposicion,
)
from backend.api.deps import get_db, requiere_roles
from backend.schemas.repositorio_asignatura import (
    RepositorioAsignaturaCreate,
    RepositorioAsignaturaOut,
    RepositorioAsignaturaUpdate,
)
from db.models import RepositorioAsignatura, Usuario
from db.repository import (
    actualizar_repositorio_asignatura,
    adjuntar_programa,
    adjuntar_silabo,
    crear_repositorio_asignatura,
    eliminar_repositorio_asignatura,
    listar_repositorio_asignaturas,
    quitar_programa,
    quitar_silabo,
    repositorio_asignatura_por_id,
)

router = APIRouter(prefix="/api/repositorio-asignaturas", tags=["repositorio-asignaturas"])

ROLES_EDITORES = ("director", "secretario", "secretaria_programa")
ROLES_TODOS = ("docente", *ROLES_EDITORES)


def _verificar_permiso_programa(entrada: RepositorioAsignatura, usuario: Usuario) -> None:
    """Los docentes solo pueden subir/quitar el programa de SU PROPIA
    asignatura (donde figuran como el docente que la dicta); los roles
    administrativos pueden hacerlo para cualquiera."""
    if usuario.rol.nombre == "docente" and entrada.docente_id != usuario.id:
        raise HTTPException(
            status_code=403, detail="Solo puedes actualizar el programa de la asignatura que tú dictas."
        )


def _out(e: RepositorioAsignatura) -> RepositorioAsignaturaOut:
    return RepositorioAsignaturaOut(
        id=e.id,
        asignatura=e.asignatura,
        docente_id=e.docente_id,
        docente_nombre=e.docente.nombre_completo if e.docente else None,
        silabo_nombre_archivo=e.silabo_nombre_archivo,
        silabo_tamano_bytes=e.silabo_tamano_bytes,
        programa_nombre_archivo=e.programa_nombre_archivo,
        programa_tamano_bytes=e.programa_tamano_bytes,
        creado_en=e.creado_en,
        actualizado_en=e.actualizado_en,
        creado_por_nombre=e.creado_por.nombre_completo if e.creado_por else None,
        actualizado_por_nombre=e.actualizado_por.nombre_completo if e.actualizado_por else None,
    )


@router.get("", response_model=list[RepositorioAsignaturaOut])
def listar(
    busqueda: str | None = None,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    return [_out(e) for e in listar_repositorio_asignaturas(db, busqueda=busqueda)]


@router.get("/{id_}", response_model=RepositorioAsignaturaOut)
def detalle(id_: int, db: Session = Depends(get_db), _usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))):
    entrada = repositorio_asignatura_por_id(db, id_)
    if entrada is None:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada en el repositorio")
    return _out(entrada)


@router.post("", response_model=RepositorioAsignaturaOut, status_code=201)
def crear(
    datos: RepositorioAsignaturaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_EDITORES)),
):
    if not datos.asignatura.strip():
        raise HTTPException(status_code=400, detail="El nombre de la asignatura es obligatorio.")
    try:
        entrada = crear_repositorio_asignatura(db, datos.asignatura, datos.docente_id, usuario.id)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"No se pudo crear (¿ya existe esa asignatura?): {exc}")
    return _out(entrada)


@router.put("/{id_}", response_model=RepositorioAsignaturaOut)
def actualizar(
    id_: int,
    datos: RepositorioAsignaturaUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_EDITORES)),
):
    campos_provistos = datos.model_fields_set
    asignatura = datos.asignatura if "asignatura" in campos_provistos else None
    docente_id = datos.docente_id if "docente_id" in campos_provistos else -1
    entrada = actualizar_repositorio_asignatura(
        db, id_, usuario.id, asignatura=asignatura, docente_id=docente_id
    )
    if entrada is None:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada en el repositorio")
    return _out(entrada)


@router.delete("/{id_}")
def eliminar(
    id_: int, db: Session = Depends(get_db), _usuario: Usuario = Depends(requiere_roles(*ROLES_EDITORES))
):
    if not eliminar_repositorio_asignatura(db, id_):
        raise HTTPException(status_code=404, detail="Asignatura no encontrada en el repositorio")
    return {"ok": True}


def _subir(db: Session, id_: int, archivo: UploadFile, usuario: Usuario, tipo: str):
    contenido = archivo.file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    try:
        ruta_relativa, tamano = guardar_archivo_repositorio(id_, tipo, archivo.filename or "archivo", contenido)
    except ArchivoInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    fn = adjuntar_silabo if tipo == "silabo" else adjuntar_programa
    entrada = fn(db, id_, archivo.filename or "archivo", ruta_relativa, tamano, usuario.id)
    if entrada is None:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada en el repositorio")
    return entrada


@router.post("/{id_}/silabo", response_model=RepositorioAsignaturaOut)
def subir_silabo(
    id_: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_EDITORES)),
):
    return _out(_subir(db, id_, archivo, usuario, "silabo"))


@router.post("/{id_}/programa", response_model=RepositorioAsignaturaOut)
def subir_programa(
    id_: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS)),
):
    entrada = repositorio_asignatura_por_id(db, id_)
    if entrada is None:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada en el repositorio")
    _verificar_permiso_programa(entrada, usuario)
    return _out(_subir(db, id_, archivo, usuario, "programa"))


@router.delete("/{id_}/silabo")
def borrar_silabo(
    id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_EDITORES))
):
    if not quitar_silabo(db, id_, usuario.id):
        raise HTTPException(status_code=404, detail="No hay sílabo cargado para esta asignatura.")
    return {"ok": True}


@router.delete("/{id_}/programa")
def borrar_programa(
    id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))
):
    entrada = repositorio_asignatura_por_id(db, id_)
    if entrada is None:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada en el repositorio")
    _verificar_permiso_programa(entrada, usuario)
    if not quitar_programa(db, id_, usuario.id):
        raise HTTPException(status_code=404, detail="No hay programa de asignatura cargado para esta materia.")
    return {"ok": True}


def _descargar(ruta_archivo: str | None, nombre_archivo: str | None):
    if not ruta_archivo:
        raise HTTPException(status_code=404, detail="No hay archivo cargado.")
    ruta = ruta_absoluta_segura(ruta_archivo)
    if ruta is None:
        raise HTTPException(status_code=404, detail="El archivo ya no existe en el servidor.")
    media_type, disposicion = tipo_y_disposicion(nombre_archivo or ruta.name)
    nombre_header = nombre_seguro_para_header(nombre_archivo or ruta.name)
    buffer = io.BytesIO(ruta.read_bytes())
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'{disposicion}; filename="{nombre_header}"'},
    )


@router.get("/{id_}/silabo/descargar")
def descargar_silabo(id_: int, db: Session = Depends(get_db), _usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))):
    entrada = repositorio_asignatura_por_id(db, id_)
    if entrada is None:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada en el repositorio")
    return _descargar(entrada.silabo_ruta_archivo, entrada.silabo_nombre_archivo)


@router.get("/{id_}/programa/descargar")
def descargar_programa(id_: int, db: Session = Depends(get_db), _usuario: Usuario = Depends(requiere_roles(*ROLES_TODOS))):
    entrada = repositorio_asignatura_por_id(db, id_)
    if entrada is None:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada en el repositorio")
    return _descargar(entrada.programa_ruta_archivo, entrada.programa_nombre_archivo)
