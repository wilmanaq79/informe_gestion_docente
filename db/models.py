"""
Modelo de datos normalizado (marco de referencia) para el sistema de
Gestion y Autoevaluacion Docente -- Programa de Ingenieria de Sistemas,
Universidad del Pacifico.

Tablas de referencia/catalogo (no cambian con el uso diario):
    roles, cortes, periodos_academicos, eventos_calendario

Tablas operativas:
    usuarios              -- los 27 docentes + director + secretario
    asignaciones_academicas -- que materia/grupo dicta cada docente en que periodo
    informes_corte        -- Matriculados/Asistencia/Evaluados/Aprobados por
                              asignacion y corte (lo que hoy se escribe en Excel)
    notas_estudiantes     -- detalle por estudiante (Corte1/2/3, Def. Pond,
                              nota necesaria, estado) que respalda cada informe

Diagrama entidad-relacion:

    roles 1───* usuarios 1───* asignaciones_academicas *───1 periodos_academicos
                                        │
                                        1
                                        │
                                        *
                              informes_corte *───1 cortes
                                        │
                                        1
                                        │
                                        *
                              notas_estudiantes
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --- Catalogos / marco de referencia ----------------------------------------

class Rol(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="rol")


class Corte(Base):
    __tablename__ = "cortes"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(unique=True, nullable=False)  # 1, 2, 3
    nombre: Mapped[str] = mapped_column(String(30), nullable=False)
    peso_porcentual: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)


class PeriodoAcademico(Base):
    """Un semestre academico concreto ('2026-1'). anio/semestre quedan
    como columnas propias (no solo derivadas de 'nombre') para poder
    filtrar y agrupar informes por Año, por Semestre y por Corte en los
    reportes consolidados del Director y el Secretario Academico."""

    __tablename__ = "periodos_academicos"
    __table_args__ = (
        UniqueConstraint("anio", "semestre", name="uq_periodo_anio_semestre"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # '2026-1'
    anio: Mapped[int] = mapped_column(nullable=False)
    semestre: Mapped[int] = mapped_column(nullable=False)  # 1 o 2
    activo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """Periodo 'actual': donde el Director/Secretario activa la carga de
    notas de los docentes. Solo uno puede estar activo a la vez (lo
    garantiza db.repository.activar_periodo, no una constraint de BD)."""


# --- Usuarios y asignaciones -------------------------------------------------

class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    cedula: Mapped[str | None] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(120))
    telefono: Mapped[str | None] = mapped_column(String(30))
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rol: Mapped["Rol"] = relationship(back_populates="usuarios")
    asignaciones: Mapped[list["AsignacionAcademica"]] = relationship(back_populates="docente")


class AsignacionAcademica(Base):
    """Una materia/grupo que un docente dicta en un periodo academico."""

    __tablename__ = "asignaciones_academicas"
    __table_args__ = (
        UniqueConstraint("docente_id", "periodo_id", "asignatura", "grupo", name="uq_asignacion"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    docente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos_academicos.id"), nullable=False)
    asignatura: Mapped[str] = mapped_column(String(150), nullable=False)
    programa: Mapped[str | None] = mapped_column(String(150))
    grupo: Mapped[str | None] = mapped_column(String(30))

    docente: Mapped["Usuario"] = relationship(back_populates="asignaciones")
    periodo: Mapped["PeriodoAcademico"] = relationship()
    informes: Mapped[list["InformeCorte"]] = relationship(
        back_populates="asignacion", cascade="all, delete-orphan"
    )


# --- Informes por corte -------------------------------------------------------

class InformeCorte(Base):
    """Matriculados / Asistencia regular / Evaluados / Aprobados de una
    asignacion en un corte especifico -- lo que el agente escribe en el
    Excel de gestion docente, guardado tambien aqui para consulta del
    director y del secretario academico."""

    __tablename__ = "informes_corte"
    __table_args__ = (
        UniqueConstraint("asignacion_id", "corte_id", name="uq_informe_por_corte"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asignacion_id: Mapped[int] = mapped_column(ForeignKey("asignaciones_academicas.id"), nullable=False)
    corte_id: Mapped[int] = mapped_column(ForeignKey("cortes.id"), nullable=False)

    matriculados: Mapped[int] = mapped_column(nullable=False)
    asistencia_regular: Mapped[int | None]
    evaluados: Mapped[int] = mapped_column(nullable=False)
    aprobaron: Mapped[int] = mapped_column(nullable=False)
    es_estimado: Mapped[bool] = mapped_column(Boolean, default=True)

    promedio: Mapped[float | None] = mapped_column(Numeric(5, 2))
    mediana: Mapped[float | None] = mapped_column(Numeric(5, 2))
    desviacion: Mapped[float | None] = mapped_column(Numeric(5, 2))

    generado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asignacion: Mapped["AsignacionAcademica"] = relationship(back_populates="informes")
    corte: Mapped["Corte"] = relationship()
    notas: Mapped[list["NotaEstudiante"]] = relationship(
        back_populates="informe", cascade="all, delete-orphan"
    )


class NotaEstudiante(Base):
    """Detalle por estudiante que respalda un InformeCorte: notas por
    corte, acumulado ponderado (Def. Pond) y estado de aprobacion."""

    __tablename__ = "notas_estudiantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    informe_corte_id: Mapped[int] = mapped_column(
        ForeignKey("informes_corte.id", ondelete="CASCADE"), nullable=False
    )
    documento: Mapped[str | None] = mapped_column(String(30))
    nombre_estudiante: Mapped[str] = mapped_column(String(150), nullable=False)

    corte1: Mapped[float | None] = mapped_column(Numeric(5, 2))
    corte2: Mapped[float | None] = mapped_column(Numeric(5, 2))
    corte3: Mapped[float | None] = mapped_column(Numeric(5, 2))
    def_pond: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    nota_necesaria: Mapped[float | None] = mapped_column(Numeric(5, 2))
    estado: Mapped[str] = mapped_column(String(30), nullable=False)

    informe: Mapped["InformeCorte"] = relationship(back_populates="notas")


# --- Calendario academico ----------------------------------------------------

class EventoCalendario(Base):
    """Una fila del calendario academico oficial de un periodo (Inicio de
    clases, parciales, limites de reporte de notas por corte, etc.). Solo
    el Director y el Secretario Academico pueden crear/editar/borrar estos
    eventos; los docentes solo los consultan."""

    __tablename__ = "eventos_calendario"

    id: Mapped[int] = mapped_column(primary_key=True)
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos_academicos.id"), nullable=False)
    actividad: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date | None] = mapped_column(Date)  # None si es una fecha unica (no un rango)
    orden: Mapped[int] = mapped_column(default=0)  # para respetar el orden del calendario oficial

    periodo: Mapped["PeriodoAcademico"] = relationship()


# --- Entrega de documentos del docente (listas de asistencia, notas --------
# firmadas, informe de gestion docente, etc.), revisada y aprobada por la
# Secretaria del Programa. --------------------------------------------------

TIPOS_DOCUMENTO_ENTREGA = {
    "lista_asistencia": "Lista de asistencia (firmada por el docente)",
    "notas_firmadas": "Notas (firmadas por el docente)",
    "informe_gestion_docente": "Informe de gestión docente (firmado por el docente)",
    "otro": "Otro (firmado por el docente)",
}

ESTADOS_ENTREGA = ("pendiente", "aprobado", "rechazado")


class Entrega(Base):
    """La entrega documental de UN docente para UN periodo+corte: agrupa
    todos los archivos que sube (listas de asistencia, notas firmadas,
    informe de gestion docente, etc.) bajo un solo estado de revision.
    Solo la Secretaria del Programa aprueba o rechaza; al aprobar se
    notifica por correo al Director, al Secretario Academico y al
    docente."""

    __tablename__ = "entregas"
    __table_args__ = (
        UniqueConstraint("docente_id", "periodo_id", "corte_id", name="uq_entrega_docente_periodo_corte"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    docente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos_academicos.id"), nullable=False)
    corte_id: Mapped[int] = mapped_column(ForeignKey("cortes.id"), nullable=False)

    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    documentos_firmados_confirmado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    comentario_revision: Mapped[str | None] = mapped_column(String(500))
    revisado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime)

    notificacion_enviada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notificacion_error: Mapped[str | None] = mapped_column(String(300))

    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    docente: Mapped["Usuario"] = relationship(foreign_keys=[docente_id])
    revisado_por: Mapped["Usuario | None"] = relationship(foreign_keys=[revisado_por_id])
    periodo: Mapped["PeriodoAcademico"] = relationship()
    corte: Mapped["Corte"] = relationship()
    documentos: Mapped[list["DocumentoEntrega"]] = relationship(
        back_populates="entrega", cascade="all, delete-orphan", order_by="DocumentoEntrega.subido_en"
    )


class DocumentoEntrega(Base):
    """Un archivo especifico dentro de una Entrega (p.ej. la lista de
    asistencia de una materia, o el Excel de informe de gestion
    docente). El archivo en si se guarda en disco (ver
    agente_notas.almacenamiento); aqui solo se guarda la ruta y los
    metadatos."""

    __tablename__ = "documentos_entrega"

    id: Mapped[int] = mapped_column(primary_key=True)
    entrega_id: Mapped[int] = mapped_column(ForeignKey("entregas.id", ondelete="CASCADE"), nullable=False)
    tipo_documento: Mapped[str] = mapped_column(String(50), nullable=False)  # ver TIPOS_DOCUMENTO_ENTREGA
    descripcion_otro: Mapped[str | None] = mapped_column(String(150))  # solo si tipo_documento == 'otro'
    materia: Mapped[str | None] = mapped_column(String(150))

    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    ruta_archivo: Mapped[str] = mapped_column(String(500), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(nullable=False)
    subido_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    entrega: Mapped["Entrega"] = relationship(back_populates="documentos")


# --- Notificaciones dentro de la aplicacion ----------------------------------

class Notificacion(Base):
    """Aviso dentro de la app (independiente del correo) para que un
    usuario se entere de un evento que le corresponde -- p.ej. que su
    entrega fue aprobada/rechazada, o que hay una entrega para revisar.
    Se muestra en la campanita de notificaciones de los 4 roles."""

    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(500), nullable=False)
    entrega_id: Mapped[int | None] = mapped_column(ForeignKey("entregas.id", ondelete="SET NULL"))
    leida: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario: Mapped["Usuario"] = relationship()
