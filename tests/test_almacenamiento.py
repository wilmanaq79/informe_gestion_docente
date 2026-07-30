# -*- coding: utf-8 -*-
"""Pruebas unitarias del almacenamiento de archivos
(agente_notas/almacenamiento.py): whitelist de extensiones, limite de
tamano, proteccion contra path traversal, y el Content-Disposition/tipo
seguro para servir descargas. No requieren base de datos."""
import pytest

from agente_notas.almacenamiento import (
    ArchivoInvalido,
    EXTENSIONES_POR_TIPO_INSTITUCIONAL,
    EXTENSIONES_POR_TIPO_REPOSITORIO,
    TAMANO_MAXIMO_BYTES,
    _sanitizar,
    nombre_seguro_para_header,
    ruta_absoluta_segura,
    tipo_y_disposicion,
    validar_archivo_subido,
)


class TestWhitelistExtensiones:
    @pytest.mark.parametrize(
        "nombre", ["informe.pdf", "notas.xlsx", "foto.jpg", "foto.jpeg", "foto.png", "acuerdo.doc", "acuerdo.docx"]
    )
    def test_extensiones_permitidas_no_fallan(self, nombre):
        validar_archivo_subido(nombre, b"contenido")  # no debe lanzar

    @pytest.mark.parametrize("nombre", ["malicioso.html", "script.svg", "cosa.exe", "sin_extension"])
    def test_extensiones_no_permitidas_se_rechazan(self, nombre):
        with pytest.raises(ArchivoInvalido):
            validar_archivo_subido(nombre, b"contenido")


class TestExtensionesPorTipoRepositorio:
    """El repositorio de asignaturas (silabo/programa, por materia)
    exige una extension mas estricta POR TIPO de archivo (subconjunto
    de la whitelist general)."""

    @pytest.mark.parametrize("tipo", ["silabo", "programa"])
    def test_silabo_y_programa_aceptan_pdf_doc_o_docx(self, tipo):
        for nombre in ("archivo.pdf", "archivo.doc", "archivo.docx"):
            validar_archivo_subido(nombre, b"x", EXTENSIONES_POR_TIPO_REPOSITORIO[tipo])
        with pytest.raises(ArchivoInvalido):
            validar_archivo_subido("archivo.xlsx", b"x", EXTENSIONES_POR_TIPO_REPOSITORIO[tipo])


class TestExtensionesPorTipoInstitucional:
    """Los formatos institucionales (uno por programa academico
    completo, no por materia) tambien exigen una extension estricta
    POR TIPO -- p.ej. el formato de gestion y autoevaluacion docente
    debe ser .xlsx, no .doc, aunque .doc este permitido en general."""

    @pytest.mark.parametrize("tipo", ["gestion_docente", "lista_asistencia"])
    def test_gestion_docente_y_lista_asistencia_solo_aceptan_xlsx(self, tipo):
        validar_archivo_subido("plantilla.xlsx", b"x", EXTENSIONES_POR_TIPO_INSTITUCIONAL[tipo])
        with pytest.raises(ArchivoInvalido):
            validar_archivo_subido("plantilla.doc", b"x", EXTENSIONES_POR_TIPO_INSTITUCIONAL[tipo])

    @pytest.mark.parametrize("tipo", ["acuerdo_pedagogico", "plan_actividades"])
    def test_acuerdo_y_plan_solo_aceptan_doc_o_docx(self, tipo):
        validar_archivo_subido("formato.doc", b"x", EXTENSIONES_POR_TIPO_INSTITUCIONAL[tipo])
        validar_archivo_subido("formato.docx", b"x", EXTENSIONES_POR_TIPO_INSTITUCIONAL[tipo])
        with pytest.raises(ArchivoInvalido):
            validar_archivo_subido("formato.xlsx", b"x", EXTENSIONES_POR_TIPO_INSTITUCIONAL[tipo])


class TestLimiteTamano:
    def test_archivo_dentro_del_limite_no_falla(self):
        validar_archivo_subido("ok.pdf", b"A" * 1024)

    def test_archivo_que_excede_el_limite_se_rechaza(self):
        with pytest.raises(ArchivoInvalido):
            validar_archivo_subido("grande.pdf", b"A" * (TAMANO_MAXIMO_BYTES + 1))


class TestSanitizarNombre:
    def test_quita_acentos(self):
        assert _sanitizar("Notas_Gestión_Docente.xlsx") == "Notas_Gestion_Docente.xlsx"

    def test_reemplaza_espacios_y_caracteres_especiales_por_guion_bajo(self):
        assert _sanitizar("informe final (v2).pdf") == "informe_final_v2_.pdf"

    def test_nombre_vacio_no_produce_string_vacio(self):
        assert _sanitizar("???") == "archivo"


class TestPathTraversal:
    def test_ruta_que_intenta_escapar_el_directorio_se_rechaza(self):
        assert ruta_absoluta_segura("../../../../etc/passwd") is None

    def test_ruta_absoluta_fuera_del_proyecto_se_rechaza(self):
        assert ruta_absoluta_segura("C:/Windows/System32/config/SAM") is None

    def test_ruta_inexistente_dentro_del_directorio_permitido_devuelve_none(self):
        assert ruta_absoluta_segura("entregas_docentes/no_existe/archivo.pdf") is None


class TestTipoYDisposicion:
    @pytest.mark.parametrize(
        "nombre,tipo_esperado",
        [("x.pdf", "application/pdf"), ("x.jpg", "image/jpeg"), ("x.jpeg", "image/jpeg"), ("x.png", "image/png")],
    )
    def test_tipos_seguros_se_muestran_inline(self, nombre, tipo_esperado):
        media_type, disposicion = tipo_y_disposicion(nombre)
        assert media_type == tipo_esperado
        assert disposicion == "inline"

    @pytest.mark.parametrize("nombre", ["x.xlsx", "x.html", "x.svg", "x.exe"])
    def test_cualquier_otro_tipo_se_fuerza_a_descarga_binaria(self, nombre):
        # Defensa en profundidad: aunque la whitelist de subida ya bloquea
        # .html/.svg, esta segunda barrera protege incluso archivos
        # guardados antes de que existiera esa validacion.
        media_type, disposicion = tipo_y_disposicion(nombre)
        assert media_type == "application/octet-stream"
        assert disposicion == "attachment"

    def test_nombre_seguro_para_header_quita_comillas(self):
        assert nombre_seguro_para_header('foo".pdf') == "foo.pdf"
