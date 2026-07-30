"""
Modelo de datos normalizado (marco de referencia) para el sistema de
Gestion y Autoevaluacion Docente -- Programa de Ingenieria de Sistemas,
Universidad del Pacifico.

Tablas de referencia/catalogo (no cambian con el uso diario):
    roles, cortes, periodos_academicos, eventos_calendario,
    repositorio_asignaturas (silabos y programas de asignatura)

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
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
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
        # Indice unico parcial: la BD (no solo db.repository.activar_periodo)
        # garantiza que nunca haya dos periodos activos a la vez, incluso
        # si dos requests concurrentes intentan activar periodos distintos
        # al mismo tiempo (columna con un solo valor posible -- True -- en
        # la condicion, asi que un segundo INSERT/UPDATE con activo=True
        # choca con esta constraint en vez de dejar dos filas activas).
        Index("uq_un_solo_periodo_activo", "activo", unique=True, postgresql_where=text("activo")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # '2026-1'
    anio: Mapped[int] = mapped_column(nullable=False)
    semestre: Mapped[int] = mapped_column(nullable=False)  # 1 o 2
    activo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """Periodo 'actual': donde el Director/Secretario activa la carga de
    notas de los docentes. Solo uno puede estar activo a la vez (lo
    garantiza db.repository.activar_periodo, no una constraint de BD).
    Es institucional/compartido entre todos los Programa -- el calendario
    academico NO se aisla por programa (decision de negocio)."""


# --- Programas academicos -----------------------------------------------------

class Programa(Base):
    """Un programa academico (Ingenieria de Sistemas, Ingenieria Civil,
    etc.). Cada uno es administrativamente independiente: su propio
    Director, Secretario Academico, Secretaria del Programa, docentes,
    entregas y repositorio de silabos -- ninguno ve datos de otro. El
    calendario academico (PeriodoAcademico/Corte/EventoCalendario) es la
    unica excepcion: sigue siendo institucional/compartido.

    Tambien guarda los 4 formatos institucionales (gestion y
    autoevaluacion docente, acuerdo pedagogico, plan de actividades,
    lista de asistencia): a diferencia del silabo/programa de
    asignatura de RepositorioAsignatura (uno por MATERIA), estos son un
    unico juego de archivos por PROGRAMA ACADEMICO completo --
    Director/Secretario/Secretaria los suben, cualquier rol del
    programa los consulta y descarga (ver
    db.repository.TIPOS_FORMATO_INSTITUCIONAL,
    backend/api/routers/formatos_institucionales.py)."""

    __tablename__ = "programas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)  # "Ingeniería de Sistemas"
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # "ing-sistemas"
    logo_ruta_archivo: Mapped[str | None] = mapped_column(String(500))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    gestion_docente_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    gestion_docente_ruta_archivo: Mapped[str | None] = mapped_column(String(500))
    gestion_docente_tamano_bytes: Mapped[int | None]

    acuerdo_pedagogico_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    acuerdo_pedagogico_ruta_archivo: Mapped[str | None] = mapped_column(String(500))
    acuerdo_pedagogico_tamano_bytes: Mapped[int | None]

    plan_actividades_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    plan_actividades_ruta_archivo: Mapped[str | None] = mapped_column(String(500))
    plan_actividades_tamano_bytes: Mapped[int | None]

    lista_asistencia_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    lista_asistencia_ruta_archivo: Mapped[str | None] = mapped_column(String(500))
    lista_asistencia_tamano_bytes: Mapped[int | None]


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
    # Nullable: la cuenta bootstrap (db/seed.py) no pertenece a ningun
    # programa real. Todo usuario operativo (docente/director/secretario/
    # secretaria_programa) activo SI debe tener uno -- se exige en
    # db.repository.crear_usuario, no con NOT NULL de BD.
    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"), index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acepto_tratamiento_datos: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fecha_aceptacion_tratamiento: Mapped[datetime | None] = mapped_column(DateTime)
    version_politica_aceptada: Mapped[str | None] = mapped_column(String(20))
    # True para toda cuenta creada con una contrasena temporal (ver
    # db.repository.crear_usuario) -- se apaga cuando el usuario la
    # cambia (ya sea por backend.api.routers.auth.cambiar_password o
    # por restablecer_password). Las cuentas que ya existian antes de
    # este campo (admin, wilman) quedan en False: no se fuerza el
    # cambio retroactivamente.
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    rol: Mapped["Rol"] = relationship(back_populates="usuarios")
    programa: Mapped["Programa | None"] = relationship()
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
    # Siempre resuelto desde docente.programa_id (db.repository.
    # obtener_o_crear_asignacion) -- nunca un valor de texto libre pasado
    # por el caller, que es como funcionaba antes (columna 'programa' str).
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), nullable=False, index=True)
    grupo: Mapped[str | None] = mapped_column(String(30))

    docente: Mapped["Usuario"] = relationship(back_populates="asignaciones")
    periodo: Mapped["PeriodoAcademico"] = relationship()
    programa: Mapped["Programa"] = relationship()
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
    asignacion_id: Mapped[int] = mapped_column(
        ForeignKey("asignaciones_academicas.id", ondelete="CASCADE"), nullable=False
    )
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
        ForeignKey("informes_corte.id", ondelete="CASCADE"), nullable=False, index=True
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
    # Desnormalizado desde docente.programa_id al crear (db.repository.
    # obtener_o_crear_entrega) -- evita un JOIN a usuarios en cada
    # listar_entregas, la consulta de mayor volumen del sistema.
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), nullable=False, index=True)

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
    entrega_id: Mapped[int] = mapped_column(
        ForeignKey("entregas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo_documento: Mapped[str] = mapped_column(String(50), nullable=False)  # ver TIPOS_DOCUMENTO_ENTREGA
    descripcion_otro: Mapped[str | None] = mapped_column(String(150))  # solo si tipo_documento == 'otro'
    materia: Mapped[str | None] = mapped_column(String(150))

    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    ruta_archivo: Mapped[str] = mapped_column(String(500), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(nullable=False)
    subido_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Veredicto del agente de verificacion de firmas (agente_notas.agente_firmas),
    # calculado automaticamente al subir el archivo. None = indeterminado
    # (requiere revision humana, p.ej. firma manuscrita escaneada).
    firma_detectada: Mapped[bool | None] = mapped_column(Boolean)
    firma_confianza: Mapped[str | None] = mapped_column(String(10))
    firma_detalle: Mapped[str | None] = mapped_column(String(300))

    # Cuando firma_detectada no es True (Revision manual o No firmado), un
    # revisor (Director/Secretario/Secretaria del Programa) debe abrir o
    # descargar el archivo (visto_en) antes de poder confirmar la revision
    # manual (revisado_manualmente); aprobar_entrega() en el repository
    # bloquea la aprobacion de la entrega mientras falte esta confirmacion.
    visto_en: Mapped[datetime | None] = mapped_column(DateTime)
    revisado_manualmente: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revisado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime)

    revisado_por: Mapped["Usuario | None"] = relationship(foreign_keys=[revisado_por_id])

    entrega: Mapped["Entrega"] = relationship(back_populates="documentos")


# --- Notificaciones dentro de la aplicacion ----------------------------------

class Notificacion(Base):
    """Aviso dentro de la app (independiente del correo) para que un
    usuario se entere de un evento que le corresponde -- p.ej. que su
    entrega fue aprobada/rechazada, o que hay una entrega para revisar.
    Se muestra en la campanita de notificaciones de los 4 roles."""

    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mensaje: Mapped[str] = mapped_column(String(500), nullable=False)
    entrega_id: Mapped[int | None] = mapped_column(ForeignKey("entregas.id", ondelete="SET NULL"))
    leida: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario: Mapped["Usuario"] = relationship()


class AceptacionPoliticaTratamiento(Base):
    """Bitacora inmutable de cada aceptacion del Aviso de Privacidad y
    Autorizacion para el Tratamiento de Datos Personales (Ley 1581 de
    2012). A diferencia de los campos en Usuario (que solo reflejan el
    estado MAS RECIENTE), aqui queda un registro por cada aceptacion --
    incluidas las de versiones anteriores de la politica -- como prueba
    de la autorizacion otorgada."""

    __tablename__ = "aceptaciones_politica_tratamiento"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    version_politica: Mapped[str] = mapped_column(String(20), nullable=False)
    aceptado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    direccion_ip: Mapped[str | None] = mapped_column(String(45))


class TokenRecuperacionPassword(Base):
    """Token de un solo uso para el flujo de 'olvide mi contrasena'. Solo
    se persiste el hash (sha256) del token -- el token en texto plano
    solo existe en el correo enviado y en el POST de canje, nunca en la
    base de datos (ver db.repository.crear_token_recuperacion)."""

    __tablename__ = "tokens_recuperacion_password"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    usado_en: Mapped[datetime | None] = mapped_column(DateTime)

    usuario: Mapped["Usuario"] = relationship()


# --- Repositorio de silabos y programas de asignatura ------------------------

class RepositorioAsignatura(Base):
    """Repositorio de consulta del sílabo y el programa de asignatura de
    cada materia. Director, Secretario Académico y Secretaria del
    Programa cargan/actualizan/eliminan el sílabo; cada docente puede
    actualizar el programa de asignatura de SU propia materia (ver
    backend/api/routers/repositorio_asignaturas.py,
    _verificar_permiso_programa). Los formatos institucionales
    (gestión y autoevaluación docente, acuerdo pedagógico, plan de
    actividades) NO viven aquí -- son un archivo único por programa
    académico completo, ver la clase Programa."""

    __tablename__ = "repositorio_asignaturas"
    __table_args__ = (
        UniqueConstraint("programa_id", "asignatura", name="uq_repositorio_programa_asignatura"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # OJO con la terminología: este 'programa_id' es el PROGRAMA ACADÉMICO
    # (Ingeniería de Sistemas, etc. -- FK a la tabla `programas`), NO tiene
    # relación con las columnas programa_nombre_archivo/programa_ruta_archivo/
    # programa_tamano_bytes de más abajo, que son el archivo "programa de
    # asignatura" (el sílabo/programa de UNA materia) -- dos sentidos
    # distintos de la palabra "programa" que coexisten en esta misma tabla.
    # Cada programa académico tiene sus propias materias: el nombre de
    # asignatura ya NO es único globalmente (antes sí lo era), solo dentro
    # de su programa (ver UniqueConstraint arriba).
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"), nullable=False, index=True)
    asignatura: Mapped[str] = mapped_column(String(150), nullable=False)
    docente_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))  # quien la dicta actualmente

    silabo_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    silabo_ruta_archivo: Mapped[str | None] = mapped_column(String(500))
    silabo_tamano_bytes: Mapped[int | None]

    programa_nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    programa_ruta_archivo: Mapped[str | None] = mapped_column(String(500))
    programa_tamano_bytes: Mapped[int | None]

    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    creado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    actualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    docente: Mapped["Usuario | None"] = relationship(foreign_keys=[docente_id])
    creado_por: Mapped["Usuario | None"] = relationship(foreign_keys=[creado_por_id])
    actualizado_por: Mapped["Usuario | None"] = relationship(foreign_keys=[actualizado_por_id])


# --- Limitador de intentos de login -------------------------------------------

class IntentoLoginFallido(Base):
    """Contador de intentos fallidos de login por usuario, respaldado en
    Postgres (no en memoria del proceso) para que el limite sea correcto
    sin importar cuantos workers de uvicorn esten corriendo -- un
    diccionario en memoria por proceso (la version anterior) da un
    limite efectivo de N_workers x MAX_INTENTOS en vez de MAX_INTENTOS,
    porque cada worker es un proceso de SO independiente con su propia
    memoria. Ver backend/core/rate_limit.py."""

    __tablename__ = "intentos_login_fallidos"

    clave: Mapped[str] = mapped_column(String(50), primary_key=True)  # username normalizado
    intentos: Mapped[int] = mapped_column(nullable=False, default=0)
    primer_intento_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
