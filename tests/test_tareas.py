# -*- coding: utf-8 -*-
"""Pruebas del modulo de tareas -- Fase 1 (ver
docs/especificacionModuloTareas.md): catalogos, creacion con el estado
inicial correcto segun el rol del creador, visibilidad de listar_tareas
por rol, asignacion y publicacion de borradores, y la actualizacion
automatica al estado VENCIDA."""
import uuid
from datetime import date, timedelta

import pytest

from db.models import Programa
from db.repository import (
    _estado_tarea_por_nombre,
    agregar_evidencia_tarea,
    aprobar_tarea,
    asignar_tarea,
    cancelar_tarea,
    crear_tarea,
    crear_usuario,
    devolver_tarea,
    eliminar_evidencia_tarea,
    enviar_a_revision_tarea,
    evidencia_tarea_por_id,
    indicadores_tareas,
    iniciar_tarea,
    listar_categorias_tarea,
    listar_estados_tarea,
    listar_evidencias_tarea,
    listar_prioridades_tarea,
    listar_roles,
    listar_tareas,
    publicar_tarea,
    reactivar_tarea,
    tarea_por_id,
    terminar_tarea,
)


def _rol_id(session, nombre: str) -> int:
    return next(r.id for r in listar_roles(session) if r.nombre == nombre)


def _crear_programa(session) -> Programa:
    programa = Programa(nombre=f"PYTEST Programa {uuid.uuid4().hex[:6]}", codigo=f"pytest-{uuid.uuid4().hex[:8]}")
    session.add(programa)
    session.flush()
    return programa


def _crear_usuario(session, rol_nombre: str, programa_id: int):
    return crear_usuario(
        session, f"PYTEST {rol_nombre}", None, None, f"__pytest_tareas_{uuid.uuid4().hex[:10]}__",
        "hash", _rol_id(session, rol_nombre), programa_id=programa_id,
    )


def _prioridad_id(session) -> int:
    return listar_prioridades_tarea(session)[0].id


class TestCatalogos:
    def test_catalogos_sembrados_por_la_migracion(self, db_session):
        assert {p.nombre for p in listar_prioridades_tarea(db_session)} == {"BAJA", "MEDIA", "ALTA", "CRITICA"}
        assert "SIN_COMENZAR" in {e.nombre for e in listar_estados_tarea(db_session)}
        assert len(listar_categorias_tarea(db_session)) >= 20

    def test_estados_tienen_icono_y_color(self, db_session):
        estados = {e.nombre: e for e in listar_estados_tarea(db_session)}
        assert "VENCIDA" in estados
        for estado in estados.values():
            assert estado.icono, f"{estado.nombre} no tiene icono"
            assert estado.color, f"{estado.nombre} no tiene color"


class TestCrearTarea:
    def test_director_crea_institucional_nace_sin_comenzar(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Preparar autoevaluación", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        assert tarea.estado.nombre == "SIN_COMENZAR"
        assert tarea.tipo == "institucional"

    def test_secretaria_programa_crea_nace_borrador(self, db_session):
        programa = _crear_programa(db_session)
        secretaria = _crear_usuario(db_session, "secretaria_programa", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Actualizar actas", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=secretaria.id, creador_rol="secretaria_programa",
        )
        assert tarea.estado.nombre == "BORRADOR"

    def test_docente_crea_siempre_personal_y_es_su_propio_responsable(self, db_session):
        programa = _crear_programa(db_session)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Revisar notas", tipo="institucional",  # se ignora, forzado a personal
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=docente.id, creador_rol="docente",
        )
        assert tarea.tipo == "personal"
        assert tarea.responsable_principal_id == docente.id
        assert tarea.estado.nombre == "SIN_COMENZAR"


class TestVisibilidadListarTareas:
    def test_director_ve_todas_las_del_programa(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        crear_tarea(
            db_session, titulo="Tarea de docente", tipo="personal",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=docente.id, creador_rol="docente",
        )
        tareas = listar_tareas(db_session, director)
        assert len(tareas) == 1

    def test_docente_no_ve_tareas_personales_de_otro_docente(self, db_session):
        programa = _crear_programa(db_session)
        docente_a = _crear_usuario(db_session, "docente", programa.id)
        docente_b = _crear_usuario(db_session, "docente", programa.id)
        crear_tarea(
            db_session, titulo="Tarea de B", tipo="personal",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=docente_b.id, creador_rol="docente",
        )
        assert listar_tareas(db_session, docente_a) == []
        assert len(listar_tareas(db_session, docente_b)) == 1

    def test_docente_ve_tarea_institucional_asignada_a_el(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Tarea institucional", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        asignar_tarea(db_session, tarea.id, docente.id, director.id)
        tareas_docente = listar_tareas(db_session, docente)
        assert len(tareas_docente) == 1
        assert tareas_docente[0].id == tarea.id

    def test_secretaria_programa_ve_las_que_creo_y_las_asignadas(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        secretaria = _crear_usuario(db_session, "secretaria_programa", programa.id)
        borrador = crear_tarea(
            db_session, titulo="Borrador propio", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=secretaria.id, creador_rol="secretaria_programa",
        )
        asignada = crear_tarea(
            db_session, titulo="Asignada a secretaria", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        asignar_tarea(db_session, asignada.id, secretaria.id, director.id)

        ids_visibles = {t.id for t in listar_tareas(db_session, secretaria)}
        assert ids_visibles == {borrador.id, asignada.id}


class TestAsignarYPublicar:
    def test_asignar_fija_responsable_y_asignador(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Por asignar", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        actualizada = asignar_tarea(db_session, tarea.id, docente.id, director.id)
        assert actualizada.responsable_principal_id == docente.id
        assert actualizada.asignado_por_id == director.id

    def test_no_se_puede_asignar_una_tarea_terminada(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Ya terminada", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", responsable_principal_id=docente.id,
        )
        iniciar_tarea(db_session, tarea.id)
        terminar_tarea(db_session, tarea.id)
        with pytest.raises(ValueError):
            asignar_tarea(db_session, tarea.id, docente.id, director.id)

    def test_no_se_puede_asignar_una_tarea_cancelada(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Ya cancelada", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        cancelar_tarea(db_session, tarea.id, "motivo")
        with pytest.raises(ValueError):
            asignar_tarea(db_session, tarea.id, docente.id, director.id)

    def test_publicar_borrador_pasa_a_sin_comenzar(self, db_session):
        programa = _crear_programa(db_session)
        secretaria = _crear_usuario(db_session, "secretaria_programa", programa.id)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Borrador a publicar", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=secretaria.id, creador_rol="secretaria_programa",
        )
        assert tarea.estado.nombre == "BORRADOR"
        publicada = publicar_tarea(db_session, tarea.id, director.id)
        assert publicada.estado.nombre == "SIN_COMENZAR"
        assert publicada.asignado_por_id == director.id

    def test_publicar_una_tarea_que_no_esta_en_borrador_falla(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Ya publicada", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        with pytest.raises(ValueError):
            publicar_tarea(db_session, tarea.id, director.id)


class TestTareaPorId:
    def test_devuelve_none_si_no_existe(self, db_session):
        assert tarea_por_id(db_session, 999999999) is None


class TestAutoVencida:
    """El estado VENCIDA no es una condicion aparte del estado operativo
    (a diferencia de como se penso originalmente en la especificacion) --
    es un estado real que el sistema asigna solo cuando se supera
    fecha_limite y la tarea no ha sido finalizada/cancelada, sin
    necesitar un job periodico (ver db.repository._marcar_tareas_vencidas,
    llamada desde listar_tareas/tarea_por_id)."""

    def _tarea_con_fecha_limite(self, session, programa, creador, fecha_limite):
        return crear_tarea(
            session, titulo="Tarea con fecha límite", tipo="institucional",
            prioridad_id=_prioridad_id(session), programa_id=programa.id,
            creado_por_id=creador.id, creador_rol="director", fecha_limite=fecha_limite,
        )

    def test_se_marca_vencida_al_listar(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        ayer = date.today() - timedelta(days=1)
        tarea = self._tarea_con_fecha_limite(db_session, programa, director, ayer)
        assert tarea.estado.nombre == "SIN_COMENZAR"

        listadas = listar_tareas(db_session, director)
        assert listadas[0].estado.nombre == "VENCIDA"

    def test_se_marca_vencida_al_consultar_por_id(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        ayer = date.today() - timedelta(days=1)
        tarea = self._tarea_con_fecha_limite(db_session, programa, director, ayer)

        actualizada = tarea_por_id(db_session, tarea.id)
        assert actualizada.estado.nombre == "VENCIDA"

    def test_no_se_marca_vencida_si_la_fecha_limite_no_ha_pasado(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        mañana = date.today() + timedelta(days=1)
        tarea = self._tarea_con_fecha_limite(db_session, programa, director, mañana)

        actualizada = tarea_por_id(db_session, tarea.id)
        assert actualizada.estado.nombre == "SIN_COMENZAR"

    def test_no_se_marca_vencida_si_no_tiene_fecha_limite(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Sin fecha límite", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        actualizada = tarea_por_id(db_session, tarea.id)
        assert actualizada.estado.nombre == "SIN_COMENZAR"

    def test_borrador_no_se_marca_vencido_aunque_pase_la_fecha(self, db_session):
        programa = _crear_programa(db_session)
        secretaria = _crear_usuario(db_session, "secretaria_programa", programa.id)
        ayer = date.today() - timedelta(days=1)
        tarea = crear_tarea(
            db_session, titulo="Borrador con fecha vencida", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=secretaria.id, creador_rol="secretaria_programa", fecha_limite=ayer,
        )
        assert tarea.estado.nombre == "BORRADOR"

        actualizada = tarea_por_id(db_session, tarea.id)
        assert actualizada.estado.nombre == "BORRADOR"

    def test_tarea_terminada_no_se_marca_vencida(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        ayer = date.today() - timedelta(days=1)
        tarea = self._tarea_con_fecha_limite(db_session, programa, director, ayer)

        # Fase 1 todavia no expone un endpoint para terminar una tarea
        # (llega en Fase 2 con las transiciones) -- se fuerza el estado
        # directamente para probar la exencion.
        tarea.estado_id = _estado_tarea_por_nombre(db_session, "TERMINADA").id
        db_session.commit()

        actualizada = tarea_por_id(db_session, tarea.id)
        assert actualizada.estado.nombre == "TERMINADA"


class TestReactivarTarea:
    def _tarea_vencida(self, session, programa, director, **extra):
        ayer = date.today() - timedelta(days=1)
        tarea = crear_tarea(
            session, titulo="Tarea vencida", tipo="institucional",
            prioridad_id=_prioridad_id(session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", fecha_limite=ayer, **extra,
        )
        # Forzar la marca VENCIDA (normalmente la asigna automaticamente
        # listar_tareas/tarea_por_id -- se llama explicitamente aqui para
        # no depender de ese efecto secundario en un test que ya prueba
        # otra cosa).
        return tarea_por_id(session, tarea.id)

    def test_reactivar_una_tarea_nunca_iniciada_vuelve_a_sin_comenzar(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_vencida(db_session, programa, director)
        assert tarea.estado.nombre == "VENCIDA"

        nueva_fecha = date.today() + timedelta(days=5)
        actualizada = reactivar_tarea(db_session, tarea.id, nueva_fecha)
        assert actualizada.estado.nombre == "SIN_COMENZAR"
        assert actualizada.fecha_limite == nueva_fecha

    def test_reactivar_una_tarea_ya_iniciada_vuelve_a_en_proceso(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_vencida(db_session, programa, director, fecha_inicio=date.today() - timedelta(days=3))
        assert tarea.estado.nombre == "VENCIDA"

        actualizada = reactivar_tarea(db_session, tarea.id, date.today() + timedelta(days=5))
        assert actualizada.estado.nombre == "EN_PROCESO"

    def test_reactivar_exige_fecha_limite_futura(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_vencida(db_session, programa, director)
        with pytest.raises(ValueError):
            reactivar_tarea(db_session, tarea.id, date.today() - timedelta(days=1))

    def test_reactivar_una_tarea_que_no_esta_vencida_falla(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = crear_tarea(
            db_session, titulo="No vencida", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        with pytest.raises(ValueError):
            reactivar_tarea(db_session, tarea.id, date.today() + timedelta(days=5))


class TestIniciarTerminarCancelar:
    def _tarea_sin_comenzar(self, session, programa, director, **extra):
        return crear_tarea(
            session, titulo="Tarea de transición", tipo="institucional",
            prioridad_id=_prioridad_id(session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", **extra,
        )

    def test_iniciar_pasa_a_en_proceso_y_fija_fecha_inicio(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_sin_comenzar(db_session, programa, director)
        assert tarea.fecha_inicio is None

        actualizada = iniciar_tarea(db_session, tarea.id)
        assert actualizada.estado.nombre == "EN_PROCESO"
        assert actualizada.fecha_inicio == date.today()

    def test_iniciar_no_sobreescribe_fecha_inicio_existente(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        antes = date.today() - timedelta(days=5)
        tarea = self._tarea_sin_comenzar(db_session, programa, director, fecha_inicio=antes)

        actualizada = iniciar_tarea(db_session, tarea.id)
        assert actualizada.fecha_inicio == antes

    def test_iniciar_una_tarea_ya_en_proceso_falla(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_sin_comenzar(db_session, programa, director)
        iniciar_tarea(db_session, tarea.id)
        with pytest.raises(ValueError):
            iniciar_tarea(db_session, tarea.id)

    def test_terminar_pasa_a_terminada_con_avance_100(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_sin_comenzar(db_session, programa, director)
        iniciar_tarea(db_session, tarea.id)

        actualizada = terminar_tarea(db_session, tarea.id)
        assert actualizada.estado.nombre == "TERMINADA"
        assert actualizada.porcentaje_avance == 100
        assert actualizada.fecha_fin_real is not None

    def test_terminar_una_tarea_sin_comenzar_falla(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_sin_comenzar(db_session, programa, director)
        with pytest.raises(ValueError):
            terminar_tarea(db_session, tarea.id)

    def test_cancelar_registra_motivo(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_sin_comenzar(db_session, programa, director)

        actualizada = cancelar_tarea(db_session, tarea.id, "Ya no aplica")
        assert actualizada.estado.nombre == "CANCELADA"
        assert actualizada.motivo_cancelacion == "Ya no aplica"

    def test_cancelar_una_tarea_terminada_falla(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_sin_comenzar(db_session, programa, director)
        iniciar_tarea(db_session, tarea.id)
        terminar_tarea(db_session, tarea.id)
        with pytest.raises(ValueError):
            cancelar_tarea(db_session, tarea.id, "motivo")


class TestIndicadoresTareas:
    def test_totales_y_porcentaje_de_cumplimiento(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        t1 = crear_tarea(
            db_session, titulo="T1", tipo="institucional", prioridad_id=_prioridad_id(db_session),
            programa_id=programa.id, creado_por_id=director.id, creador_rol="director",
        )
        t2 = crear_tarea(
            db_session, titulo="T2", tipo="institucional", prioridad_id=_prioridad_id(db_session),
            programa_id=programa.id, creado_por_id=director.id, creador_rol="director",
        )
        iniciar_tarea(db_session, t1.id)
        terminar_tarea(db_session, t1.id)
        cancelar_tarea(db_session, t2.id, "motivo")

        indicadores = indicadores_tareas(db_session, director)
        assert indicadores["total"] == 2
        assert indicadores["por_estado"]["TERMINADA"] == 1
        assert indicadores["por_estado"]["CANCELADA"] == 1
        # validas = total - canceladas - borradores = 1; terminadas = 1 -> 100%
        assert indicadores["cumplimiento_pct"] == 100.0

    def test_proximas_a_vencer_dentro_de_3_dias(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        crear_tarea(
            db_session, titulo="Vence pronto", tipo="institucional", prioridad_id=_prioridad_id(db_session),
            programa_id=programa.id, creado_por_id=director.id, creador_rol="director",
            fecha_limite=date.today() + timedelta(days=2),
        )
        crear_tarea(
            db_session, titulo="Vence lejos", tipo="institucional", prioridad_id=_prioridad_id(db_session),
            programa_id=programa.id, creado_por_id=director.id, creador_rol="director",
            fecha_limite=date.today() + timedelta(days=10),
        )
        indicadores = indicadores_tareas(db_session, director)
        assert indicadores["proximas_a_vencer"] == 1

    def test_proximas_a_vencer_detalle_trae_la_tarea_con_dias_restantes(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        docente = _crear_usuario(db_session, "docente", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Vence pronto", tipo="institucional", prioridad_id=_prioridad_id(db_session),
            programa_id=programa.id, creado_por_id=director.id, creador_rol="director",
            fecha_limite=date.today() + timedelta(days=2), responsable_principal_id=docente.id,
        )
        indicadores = indicadores_tareas(db_session, director)
        detalle = indicadores["proximas_a_vencer_detalle"]
        assert len(detalle) == 1
        assert detalle[0]["id"] == tarea.id
        assert detalle[0]["codigo"] == f"TAR-{tarea.id:06d}"
        assert detalle[0]["dias_restantes"] == 2
        assert detalle[0]["responsable_principal_nombre"] == docente.nombre_completo


class TestRevisionAprobacion:
    def _tarea_en_proceso(self, session, programa, director, **extra):
        tarea = crear_tarea(
            session, titulo="Tarea con revision", tipo="institucional",
            prioridad_id=_prioridad_id(session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", **extra,
        )
        return iniciar_tarea(session, tarea.id)

    def test_enviar_a_revision_deja_pendiente_revision(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_en_proceso(db_session, programa, director)

        actualizada = enviar_a_revision_tarea(db_session, tarea.id)
        assert actualizada.estado.nombre == "PENDIENTE_REVISION"
        assert actualizada.porcentaje_avance == 100

    def test_enviar_a_revision_de_una_tarea_no_en_proceso_falla(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Sin iniciar", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director",
        )
        with pytest.raises(ValueError):
            enviar_a_revision_tarea(db_session, tarea.id)

    def test_aprobar_pasa_a_terminada(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_en_proceso(db_session, programa, director)
        enviar_a_revision_tarea(db_session, tarea.id)

        actualizada = aprobar_tarea(db_session, tarea.id)
        assert actualizada.estado.nombre == "TERMINADA"
        assert actualizada.fecha_fin_real is not None

    def test_aprobar_una_tarea_que_no_esta_pendiente_revision_falla(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_en_proceso(db_session, programa, director)
        with pytest.raises(ValueError):
            aprobar_tarea(db_session, tarea.id)

    def test_devolver_pasa_a_devuelta_observaciones(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_en_proceso(db_session, programa, director)
        enviar_a_revision_tarea(db_session, tarea.id)

        actualizada = devolver_tarea(db_session, tarea.id)
        assert actualizada.estado.nombre == "DEVUELTA_OBSERVACIONES"

    def test_devolver_una_tarea_que_no_esta_pendiente_revision_falla(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = self._tarea_en_proceso(db_session, programa, director)
        with pytest.raises(ValueError):
            devolver_tarea(db_session, tarea.id)


class TestEvidenciasTarea:
    def test_agregar_y_listar_evidencia(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Con evidencia", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", requiere_evidencia=True,
        )
        evidencia = agregar_evidencia_tarea(
            db_session, tarea.id, "soporte.pdf", "evidencias_tareas/tarea_1/soporte.pdf", 1234, director.id,
        )
        assert evidencia.id is not None
        listadas = listar_evidencias_tarea(db_session, tarea.id)
        assert len(listadas) == 1
        assert listadas[0].nombre_archivo == "soporte.pdf"

    def test_eliminar_evidencia_devuelve_la_ruta_y_borra_el_registro(self, db_session):
        programa = _crear_programa(db_session)
        director = _crear_usuario(db_session, "director", programa.id)
        tarea = crear_tarea(
            db_session, titulo="Con evidencia", tipo="institucional",
            prioridad_id=_prioridad_id(db_session), programa_id=programa.id,
            creado_por_id=director.id, creador_rol="director", requiere_evidencia=True,
        )
        evidencia = agregar_evidencia_tarea(
            db_session, tarea.id, "soporte.pdf", "evidencias_tareas/tarea_1/soporte.pdf", 1234, director.id,
        )
        ruta = eliminar_evidencia_tarea(db_session, evidencia.id)
        assert ruta == "evidencias_tareas/tarea_1/soporte.pdf"
        assert evidencia_tarea_por_id(db_session, evidencia.id) is None

    def test_eliminar_evidencia_inexistente_devuelve_none(self, db_session):
        assert eliminar_evidencia_tarea(db_session, 999999999) is None
