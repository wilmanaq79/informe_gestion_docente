# -*- coding: utf-8 -*-
"""Pruebas de las reglas de permiso propias del router de tareas
(backend/api/routers/tareas.py) -- lo que NO cubre ya
tests/test_deps_rbac.py (que prueba requiere_roles de forma generica):
visibilidad (_puede_ver), edicion segun rol/estado (_verificar_permiso_
editar), y la barrera de 'solo tareas personales' para quien no puede
asignar tareas institucionales."""
import io
import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from agente_notas.almacenamiento import eliminar_archivo
from backend.api.routers import tareas as tareas_router
from backend.schemas.tarea import CancelarTareaIn, DevolverTareaIn, ReactivarTareaIn, TareaCreate
from db.models import Programa
from db.repository import crear_tarea, crear_usuario, listar_notificaciones, listar_prioridades_tarea, listar_roles


class _ArchivoFalso:
    """Doble minimo de fastapi.UploadFile: el router solo usa
    .filename y .file.read()."""

    def __init__(self, filename: str, contenido: bytes):
        self.filename = filename
        self.file = io.BytesIO(contenido)


def _rol_id(session, nombre: str) -> int:
    return next(r.id for r in listar_roles(session) if r.nombre == nombre)


def _crear_programa(session) -> Programa:
    programa = Programa(nombre=f"PYTEST Programa {uuid.uuid4().hex[:6]}", codigo=f"pytest-{uuid.uuid4().hex[:8]}")
    session.add(programa)
    session.flush()
    return programa


def _crear_usuario(session, rol_nombre: str, programa_id: int):
    return crear_usuario(
        session, f"PYTEST {rol_nombre}", None, None, f"__pytest_tareas_perm_{uuid.uuid4().hex[:10]}__",
        "hash", _rol_id(session, rol_nombre), programa_id=programa_id,
    )


class _RolFalso:
    def __init__(self, nombre):
        self.nombre = nombre


class _UsuarioFalso:
    def __init__(self, id_, rol_nombre):
        self.id = id_
        self.rol = _RolFalso(rol_nombre)


class _EstadoFalso:
    def __init__(self, nombre):
        self.nombre = nombre


class _ResponsableSecundarioFalso:
    def __init__(self, usuario_id):
        self.usuario_id = usuario_id


class _TareaFalsa:
    def __init__(
        self, tipo, estado_nombre, creado_por_id=None, responsable_principal_id=None, secundarios=None,
        asignado_por_id=None, fecha_limite=None,
    ):
        self.tipo = tipo
        self.estado = _EstadoFalso(estado_nombre)
        self.creado_por_id = creado_por_id
        self.responsable_principal_id = responsable_principal_id
        self.responsables_secundarios = secundarios or []
        self.asignado_por_id = asignado_por_id
        self.fecha_limite = fecha_limite


class TestPuedeVer:
    def test_director_ve_cualquier_tarea(self):
        tarea = _TareaFalsa("personal", "SIN_COMENZAR", creado_por_id=999)
        assert tareas_router._puede_ver(tarea, _UsuarioFalso(1, "director")) is True

    def test_creador_ve_su_propia_tarea(self):
        tarea = _TareaFalsa("personal", "SIN_COMENZAR", creado_por_id=5)
        assert tareas_router._puede_ver(tarea, _UsuarioFalso(5, "docente")) is True

    def test_responsable_secundario_ve_la_tarea(self):
        tarea = _TareaFalsa(
            "institucional", "SIN_COMENZAR", creado_por_id=1, responsable_principal_id=2,
            secundarios=[_ResponsableSecundarioFalso(7)],
        )
        assert tareas_router._puede_ver(tarea, _UsuarioFalso(7, "docente")) is True

    def test_docente_ajeno_no_ve_tarea_de_otro(self):
        tarea = _TareaFalsa("personal", "SIN_COMENZAR", creado_por_id=5, responsable_principal_id=5)
        assert tareas_router._puede_ver(tarea, _UsuarioFalso(999, "docente")) is False


class TestVerificarPermisoEditar:
    """Regla vigente (pedido explicito del usuario): solo quien asigno
    la tarea puede editarla, y solo antes de su fecha limite. El
    Director conserva su override total, igual que en el resto del
    modulo. Para tareas personales (nunca pasaron por /asignar) el
    creador cumple el rol de "asignador"."""

    def test_director_puede_editar_cualquier_estado(self):
        tarea = _TareaFalsa("institucional", "TERMINADA")
        tareas_router._verificar_permiso_editar(tarea, _UsuarioFalso(1, "director"))  # no debe lanzar

    def test_secretario_no_puede_editar_tarea_cerrada(self):
        tarea = _TareaFalsa("institucional", "TERMINADA", asignado_por_id=1)
        with pytest.raises(HTTPException):
            tareas_router._verificar_permiso_editar(tarea, _UsuarioFalso(1, "secretario"))

    def test_asignador_puede_editar_tarea_abierta_antes_de_vencer(self):
        manana = date.today() + timedelta(days=1)
        tarea = _TareaFalsa("institucional", "EN_PROCESO", asignado_por_id=1, fecha_limite=manana)
        tareas_router._verificar_permiso_editar(tarea, _UsuarioFalso(1, "secretario"))  # no debe lanzar

    def test_quien_no_asigno_la_tarea_no_puede_editarla(self):
        tarea = _TareaFalsa("institucional", "EN_PROCESO", asignado_por_id=1)
        with pytest.raises(HTTPException):
            tareas_router._verificar_permiso_editar(tarea, _UsuarioFalso(999, "secretario"))

    def test_no_se_puede_editar_una_tarea_ya_vencida(self):
        ayer = date.today() - timedelta(days=1)
        tarea = _TareaFalsa("institucional", "EN_PROCESO", asignado_por_id=1, fecha_limite=ayer)
        with pytest.raises(HTTPException):
            tareas_router._verificar_permiso_editar(tarea, _UsuarioFalso(1, "secretario"))

    def test_docente_no_puede_editar_tarea_institucional_asignada_por_otro(self):
        tarea = _TareaFalsa("institucional", "SIN_COMENZAR", creado_por_id=1, asignado_por_id=1)
        with pytest.raises(HTTPException):
            tareas_router._verificar_permiso_editar(tarea, _UsuarioFalso(5, "docente"))

    def test_docente_no_puede_editar_tarea_personal_ajena(self):
        tarea = _TareaFalsa("personal", "SIN_COMENZAR", creado_por_id=5)
        with pytest.raises(HTTPException):
            tareas_router._verificar_permiso_editar(tarea, _UsuarioFalso(999, "docente"))

    def test_docente_puede_editar_su_propia_tarea_personal_abierta(self):
        tarea = _TareaFalsa("personal", "SIN_COMENZAR", creado_por_id=5)
        tareas_router._verificar_permiso_editar(tarea, _UsuarioFalso(5, "docente"))  # no debe lanzar


class TestCrearSoloPersonalParaQuienNoAsigna:
    def test_docente_no_puede_crear_institucional(self, db_session):
        programa = _crear_programa(db_session)
        docente = _crear_usuario(db_session, "docente", programa.id)
        datos = TareaCreate(titulo="Intento institucional", tipo="institucional", prioridad_id=1)
        with pytest.raises(HTTPException) as exc_info:
            tareas_router.crear(datos, db_session, docente)
        assert exc_info.value.status_code == 403

    def test_docente_puede_crear_personal(self, db_session):
        programa = _crear_programa(db_session)
        docente = _crear_usuario(db_session, "docente", programa.id)
        from db.repository import listar_prioridades_tarea
        prioridad_id = listar_prioridades_tarea(db_session)[0].id
        datos = TareaCreate(titulo="Tarea personal", tipo="personal", prioridad_id=prioridad_id)
        resultado = tareas_router.crear(datos, db_session, docente)
        assert resultado.tipo == "personal"

    def test_secretaria_programa_puede_crear_institucional_como_borrador(self, db_session):
        programa = _crear_programa(db_session)
        secretaria = _crear_usuario(db_session, "secretaria_programa", programa.id)
        from db.repository import listar_prioridades_tarea
        prioridad_id = listar_prioridades_tarea(db_session)[0].id
        datos = TareaCreate(titulo="Borrador institucional", tipo="institucional", prioridad_id=prioridad_id)
        resultado = tareas_router.crear(datos, db_session, secretaria)
        assert resultado.estado_nombre == "BORRADOR"


def _prioridad_id(session) -> int:
    return listar_prioridades_tarea(session)[0].id


class TestIniciarTerminarCancelarPermisos:
    def _tarea(self, session, programa, director, **extra):
        return crear_tarea(
            session, titulo="Tarea de router", tipo="institucional",
            prioridad_id=_prioridad_id(session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", **extra,
        )

    def test_responsable_puede_iniciar_su_tarea(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(db_session, programa, director, responsable_principal_id=docente.id)

        resultado = tareas_router.iniciar(tarea.id, db_session, docente)
        assert resultado.estado_nombre == "EN_PROCESO"

    def test_docente_ajeno_no_puede_iniciar(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        otro = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(db_session, programa, director, responsable_principal_id=docente.id)

        with pytest.raises(HTTPException) as exc_info:
            tareas_router.iniciar(tarea.id, db_session, otro)
        assert exc_info.value.status_code == 403

    def test_terminar_con_requiere_aprobacion_envia_a_revision_al_responsable(self, db_session):
        """El responsable SIEMPRE tiene una manera de informar que
        termino: si la tarea requiere aprobacion, terminar() no la
        cierra directo (eso lo hace el 400/403 de antes) sino que la
        deja en PENDIENTE_REVISION a la espera de que Director/
        Secretario la apruebe o la devuelva."""
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(
            db_session, programa, director, responsable_principal_id=docente.id, requiere_aprobacion=True,
        )
        tareas_router.iniciar(tarea.id, db_session, docente)

        resultado = tareas_router.terminar(tarea.id, db_session, docente)
        assert resultado.estado_nombre == "PENDIENTE_REVISION"

    def test_ajeno_no_puede_terminar_ni_enviar_a_revision(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        otro = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(
            db_session, programa, director, responsable_principal_id=docente.id, requiere_aprobacion=True,
        )
        tareas_router.iniciar(tarea.id, db_session, docente)

        with pytest.raises(HTTPException) as exc_info:
            tareas_router.terminar(tarea.id, db_session, otro)
        assert exc_info.value.status_code == 403

    def test_aprobar_cierra_una_pendiente_de_revision(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(
            db_session, programa, director, responsable_principal_id=docente.id, requiere_aprobacion=True,
        )
        tareas_router.iniciar(tarea.id, db_session, docente)
        tareas_router.terminar(tarea.id, db_session, docente)

        resultado = tareas_router.aprobar(tarea.id, db_session, director)
        assert resultado.estado_nombre == "TERMINADA"

    def test_devolver_regresa_a_devuelta_observaciones_y_notifica_motivo(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(
            db_session, programa, director, responsable_principal_id=docente.id, requiere_aprobacion=True,
        )
        tareas_router.iniciar(tarea.id, db_session, docente)
        tareas_router.terminar(tarea.id, db_session, docente)

        resultado = tareas_router.devolver(tarea.id, DevolverTareaIn(motivo="Falta el anexo 2"), db_session, director)
        assert resultado.estado_nombre == "DEVUELTA_OBSERVACIONES"

        notificaciones = listar_notificaciones(db_session, docente.id)
        assert any("Falta el anexo 2" in n.mensaje for n in notificaciones)

    def test_docente_puede_reiniciar_una_tarea_devuelta(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(
            db_session, programa, director, responsable_principal_id=docente.id, requiere_aprobacion=True,
        )
        tareas_router.iniciar(tarea.id, db_session, docente)
        tareas_router.terminar(tarea.id, db_session, docente)
        tareas_router.devolver(tarea.id, DevolverTareaIn(motivo="motivo"), db_session, director)

        resultado = tareas_router.iniciar(tarea.id, db_session, docente)
        assert resultado.estado_nombre == "EN_PROCESO"

    def test_terminar_con_requiere_aprobacion_lo_permite_al_director(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(
            db_session, programa, director, responsable_principal_id=docente.id, requiere_aprobacion=True,
        )
        tareas_router.iniciar(tarea.id, db_session, docente)

        resultado = tareas_router.terminar(tarea.id, db_session, director)
        assert resultado.estado_nombre == "TERMINADA"

    def test_terminar_sin_requiere_aprobacion_lo_permite_al_responsable(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(
            db_session, programa, director, responsable_principal_id=docente.id, requiere_aprobacion=False,
        )
        tareas_router.iniciar(tarea.id, db_session, docente)

        resultado = tareas_router.terminar(tarea.id, db_session, docente)
        assert resultado.estado_nombre == "TERMINADA"

    def test_docente_puede_cancelar_su_propia_tarea_personal(self, db_session):
        programa = _crear_programa(db_session)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Personal a cancelar", tipo="personal",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=docente.id, creador_rol="docente",
        )
        resultado = tareas_router.cancelar(tarea.id, CancelarTareaIn(motivo="Ya no aplica"), db_session, docente)
        assert resultado.estado_nombre == "CANCELADA"

    def test_docente_no_puede_cancelar_tarea_institucional(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(db_session, programa, director, responsable_principal_id=docente.id)

        with pytest.raises(HTTPException) as exc_info:
            tareas_router.cancelar(tarea.id, CancelarTareaIn(motivo="No aplica"), db_session, docente)
        assert exc_info.value.status_code == 403

    def test_indicadores_refleja_las_tareas_visibles_del_usuario(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        self._tarea(db_session, programa, director)

        resultado = tareas_router.indicadores(db_session, director)
        assert resultado.total == 1

    def test_iniciar_en_nombre_del_responsable_le_notifica_a_el(self, db_session):
        """Si el Director inicia/termina una tarea EN NOMBRE del
        responsable (el caso mas comun), el responsable debe enterarse
        -- no solo el creador/asignador, que aqui coinciden con el
        propio actor y quedarian excluidos de si mismos."""
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea(db_session, programa, director, responsable_principal_id=docente.id)

        tareas_router.iniciar(tarea.id, db_session, director)

        notificaciones = listar_notificaciones(db_session, docente.id)
        assert len(notificaciones) == 1
        assert "inició" in notificaciones[0].mensaje


class TestEvidenciasPermisos:
    def _tarea_con_evidencia(self, session, programa, director, docente):
        return crear_tarea(
            session, titulo="Requiere evidencia", tipo="institucional",
            prioridad_id=next(iter(listar_prioridades_tarea(session))).id, programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", responsable_principal_id=docente.id,
            requiere_evidencia=True,
        )

    def test_responsable_puede_subir_evidencia_si_la_tarea_la_requiere(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea_con_evidencia(db_session, programa, director, docente)

        resultado = tareas_router.subir_evidencia(
            tarea.id, _ArchivoFalso("soporte.pdf", b"%PDF-1.4 contenido de prueba"), db_session, docente,
        )
        try:
            assert resultado.nombre_archivo == "soporte.pdf"
            listadas = tareas_router.listar_evidencias(tarea.id, db_session, docente)
            assert len(listadas) == 1
        finally:
            evidencia = tareas_router.evidencia_tarea_por_id(db_session, resultado.id)
            if evidencia is not None:
                eliminar_archivo(evidencia.ruta_archivo)

    def test_no_se_puede_subir_evidencia_si_la_tarea_no_la_requiere(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Sin evidencia", tipo="institucional",
            prioridad_id=next(iter(listar_prioridades_tarea(db_session))).id, programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", responsable_principal_id=docente.id,
            requiere_evidencia=False,
        )
        with pytest.raises(HTTPException) as exc_info:
            tareas_router.subir_evidencia(tarea.id, _ArchivoFalso("x.pdf", b"%PDF-1.4 x"), db_session, docente)
        assert exc_info.value.status_code == 400

    def test_docente_ajeno_no_puede_subir_evidencia(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        otro = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea_con_evidencia(db_session, programa, director, docente)

        with pytest.raises(HTTPException) as exc_info:
            tareas_router.subir_evidencia(tarea.id, _ArchivoFalso("x.pdf", b"%PDF-1.4 x"), db_session, otro)
        assert exc_info.value.status_code == 403

    def test_uploader_puede_borrar_su_propia_evidencia(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea_con_evidencia(db_session, programa, director, docente)
        subida = tareas_router.subir_evidencia(
            tarea.id, _ArchivoFalso("soporte.pdf", b"%PDF-1.4 contenido"), db_session, docente,
        )

        resultado = tareas_router.borrar_evidencia(tarea.id, subida.id, db_session, docente)
        assert resultado == {"ok": True}
        assert tareas_router.evidencia_tarea_por_id(db_session, subida.id) is None

    def test_otro_docente_no_puede_borrar_evidencia_ajena(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        otro = _crear_usuario(db_session, "docente", programa.id)
        tarea = self._tarea_con_evidencia(db_session, programa, director, docente)
        subida = tareas_router.subir_evidencia(
            tarea.id, _ArchivoFalso("soporte.pdf", b"%PDF-1.4 contenido"), db_session, docente,
        )
        try:
            with pytest.raises(HTTPException) as exc_info:
                tareas_router.borrar_evidencia(tarea.id, subida.id, db_session, otro)
            assert exc_info.value.status_code == 403
        finally:
            evidencia = tareas_router.evidencia_tarea_por_id(db_session, subida.id)
            if evidencia is not None:
                eliminar_archivo(evidencia.ruta_archivo)


class TestReactivarPermisos:
    def test_secretaria_programa_puede_reactivar_una_vencida(self, db_session):
        """La reactivacion la puede hacer cualquier rol administrativo,
        incluida la Secretaria del Programa -- solo el Docente queda
        afuera (eso se aplica via requiere_roles en el endpoint, no
        verificable con una llamada directa como esta; ver
        tests/test_deps_rbac.py para la verificacion generica de roles)."""
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        secretaria = _crear_usuario(db_session, "secretaria_programa", programa.id)
        ayer = date.today() - timedelta(days=1)
        tarea = crear_tarea(
            db_session, titulo="Vencida para reactivar", tipo="institucional",
            prioridad_id=listar_prioridades_tarea(db_session)[0].id, programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", fecha_limite=ayer,
        )
        # Forzar la marca automatica de vencida antes de reactivar.
        assert tareas_router.tarea_por_id(db_session, tarea.id).estado.nombre == "VENCIDA"

        nueva_fecha = date.today() + timedelta(days=5)
        resultado = tareas_router.reactivar(
            tarea.id, ReactivarTareaIn(nueva_fecha_limite=nueva_fecha), db_session, secretaria,
        )
        assert resultado.estado_nombre == "SIN_COMENZAR"
        assert str(resultado.fecha_limite) == str(nueva_fecha)
