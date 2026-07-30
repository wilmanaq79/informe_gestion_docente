# -*- coding: utf-8 -*-
"""Pruebas unitarias del agente de verificacion de firmas
(agente_notas/agente_firmas.py). No requieren base de datos: los PDF y
Excel de prueba se generan en memoria con reportlab/openpyxl."""
import io

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from PIL import Image as PILImage
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from agente_notas.agente_firmas import (
    _contiene_palabra,
    _nombre_coincide_fuerte,
    _normalizar,
    analizar_documento,
    resumen_entrega,
)

NOMBRE_DOCENTE = "Wilman Andres Quinonez"


def _imagen_pil(ancho: int, alto: int) -> PILImage.Image:
    return PILImage.new("RGB", (ancho, alto), color="black")


def _pdf_con_texto(lineas: list) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = 750
    for linea in lineas:
        c.drawString(50, y, linea)
        y -= 20
    c.save()
    return buffer.getvalue()


def _xlsx_con_filas(filas: list) -> bytes:
    wb = Workbook()
    ws = wb.active
    for fila in filas:
        ws.append(fila)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _pdf_con_imagen(ancho: int, alto: int, lineas: list | None = None) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = 750
    for linea in lineas or []:
        c.drawString(50, y, linea)
        y -= 20
    img_buffer = io.BytesIO()
    _imagen_pil(ancho, alto).save(img_buffer, format="PNG")
    img_buffer.seek(0)
    c.drawImage(ImageReader(img_buffer), 50, 400, width=max(ancho, 1), height=max(alto, 1))
    c.save()
    return buffer.getvalue()


def _xlsx_con_imagen(ancho: int, alto: int, filas: list | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    for fila in filas or []:
        ws.append(fila)
    # openpyxl.drawing.image.Image necesita un objeto con .fp (como el que
    # deja PILImage.open sobre un archivo/buffer) -- una Image.new() recien
    # creada no lo tiene, por eso se guarda y se reabre desde un buffer.
    img_buffer = io.BytesIO()
    _imagen_pil(ancho, alto).save(img_buffer, format="PNG")
    img_buffer.seek(0)
    ws.add_image(XLImage(PILImage.open(img_buffer)), "A1")
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


class TestNormalizacion:
    def test_normalizar_quita_acentos_y_pasa_a_minusculas(self):
        assert _normalizar("Quiñónez") == "quinonez"

    def test_contiene_palabra_es_palabra_completa_no_substring(self):
        # "firma" no debe encontrarse dentro de "confirma"/"confirmado":
        # bug latente que existia antes de la coincidencia por palabra completa.
        assert _contiene_palabra(_normalizar("se confirma la asistencia"), "firma") is False
        assert _contiene_palabra(_normalizar("firma del docente"), "firma") is True

    def test_nombre_coincide_fuerte_exige_dos_partes(self):
        # Una sola parte del nombre (un nombre de pila comun, p.ej. "Andres")
        # no debe bastar para considerar que el nombre completo aparece.
        texto = _normalizar("ANGULO ANGULO YIDIER ANDRES")
        assert _nombre_coincide_fuerte(texto, NOMBRE_DOCENTE) is False
        texto_fuerte = _normalizar("firma: wilman andres quinonez")
        assert _nombre_coincide_fuerte(texto_fuerte, NOMBRE_DOCENTE) is True


class TestAnalizarPdf:
    def test_pdf_con_firma_y_nombre_se_marca_firmado(self):
        pdf = _pdf_con_texto(["Informe de gestion docente", f"Firma del docente: {NOMBRE_DOCENTE}"])
        v = analizar_documento("informe.pdf", pdf, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is True
        assert v["confianza"] == "media"

    def test_pdf_sin_mencion_de_firma_no_se_marca_firmado(self):
        pdf = _pdf_con_texto(["Lista de asistencia", "Estudiante 1", "Estudiante 2"])
        v = analizar_documento("asistencia.pdf", pdf, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is False

    def test_pdf_con_firma_pero_nombre_de_otra_persona_no_basta(self):
        # Reproduce el falso positivo real: un estudiante con el mismo
        # nombre de pila comun ("Andres") que el docente, en una lista de
        # asistencia con la etiqueta de plantilla "Firma docente" al
        # final, NO debe marcarse como firmado.
        pdf = _pdf_con_texto(["Lista de asistencia", "ANGULO ANGULO YIDIER ANDRES", "Firma docente"])
        v = analizar_documento("asistencia.pdf", pdf, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is False

    def test_pdf_academusoft_con_encabezado_docente_y_firma_vacia_no_se_marca_firmado(self):
        # Bug real reportado: un reporte de notas de Academusoft trae un
        # encabezado de mera identificacion ("Identificación Docente:
        # NOMBRE") y, mas abajo, el renglon real de firma en blanco
        # ("Firma Del Docente: ______"). El encabezado de identificacion
        # NO debe hacer pasar el documento como firmado cuando el
        # renglon de firma real esta vacio.
        pdf = _pdf_con_texto(
            [
                "Identificacion Docente",
                f"CC. 94444846 {NOMBRE_DOCENTE.upper()}",
                "Materia Grupo",
                "IS0810-ELECTIVA PROFESIONAL II IS08N1-W.QUINONEZ",
                "Firma Del Docente: _______________________________",
                "NOTA : Favor no adicionar estudiantes a la lista.",
            ]
        )
        v = analizar_documento("notas.pdf", pdf, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is False

    def test_pdf_academusoft_con_firma_realmente_completada_se_marca_firmado(self):
        # Contraprueba: si ese mismo renglon de firma SI trae el nombre
        # completo (firma digitada/transcrita), debe marcarse firmado.
        pdf = _pdf_con_texto(
            [
                "Identificacion Docente",
                f"CC. 94444846 {NOMBRE_DOCENTE.upper()}",
                f"Firma Del Docente: {NOMBRE_DOCENTE}",
            ]
        )
        v = analizar_documento("notas.pdf", pdf, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is True


class TestAnalizarXlsx:
    def test_xlsx_con_firma_y_nombre_se_marca_firmado(self):
        xlsx = _xlsx_con_filas([["Firma docente:", NOMBRE_DOCENTE]])
        v = analizar_documento("informe.xlsx", xlsx, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is True

    def test_xlsx_campo_docente_completado_sin_palabra_firma(self):
        # Contexto 2 pedido por el usuario: un campo "Docente: ____"
        # completado, SIN la palabra "firma" en ningun lado, tambien debe
        # contar como firmado.
        xlsx = _xlsx_con_filas([["Docente:", NOMBRE_DOCENTE]])
        v = analizar_documento("informe.xlsx", xlsx, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is True

    def test_xlsx_campo_docente_vacio_no_se_marca_firmado(self):
        xlsx = _xlsx_con_filas([["Docente:"]])
        v = analizar_documento("informe.xlsx", xlsx, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is False

    def test_xlsx_lista_asistencia_con_nombre_comun_no_es_falso_positivo(self):
        # Mismo bug real que en PDF, pero en Excel: la fila del estudiante
        # con "Andres" y la fila-etiqueta "Firma docente" estan separadas.
        xlsx = _xlsx_con_filas(
            [
                ["No", "Nombre"],
                [1, "ANGULO ANGULO YIDIER ANDRES"],
                ["Firma docente"],
            ]
        )
        v = analizar_documento("asistencia.xlsx", xlsx, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is False


class TestImagenesPorTamano:
    """Reproduce el caso real reportado: un icono/logo de membrete
    (14x14 px) no debe disparar 'requiere revision manual', pero una
    imagen de tamaño creible para ser una firma pegada (169x74 px,
    tamaño real observado) SI debe seguir disparandolo -- eso no es un
    bug, es la limitacion honesta y documentada del agente: una imagen
    pegada no se puede verificar por software, necesita ojo humano."""

    def test_pdf_con_icono_diminuto_no_dispara_revision_manual(self):
        pdf = _pdf_con_imagen(14, 14, lineas=["Lista de asistencia"])
        v = analizar_documento("asistencia.pdf", pdf, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is False

    def test_pdf_con_imagen_de_tamano_real_si_requiere_revision_manual(self):
        pdf = _pdf_con_imagen(169, 74, lineas=["Firma Del Docente"])
        v = analizar_documento("asistencia.pdf", pdf, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is None
        assert v["confianza"] == "baja"

    def test_xlsx_con_icono_diminuto_no_dispara_revision_manual(self):
        xlsx = _xlsx_con_imagen(14, 14, filas=[["Lista de asistencia"]])
        v = analizar_documento("asistencia.xlsx", xlsx, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is False

    def test_xlsx_con_imagen_de_tamano_real_si_requiere_revision_manual(self):
        xlsx = _xlsx_con_imagen(169, 74, filas=[["Firma Del Docente"]])
        v = analizar_documento("asistencia.xlsx", xlsx, NOMBRE_DOCENTE)
        assert v["firma_detectada"] is None
        assert v["confianza"] == "baja"


class TestTiposNoSoportados:
    def test_imagen_es_indeterminada(self):
        v = analizar_documento("foto.png", b"contenido-cualquiera", NOMBRE_DOCENTE)
        assert v["firma_detectada"] is None

    def test_extension_desconocida_es_indeterminada(self):
        v = analizar_documento("archivo.docx", b"contenido-cualquiera", NOMBRE_DOCENTE)
        assert v["firma_detectada"] is None


class _DocumentoFalso:
    def __init__(self, firma_detectada):
        self.firma_detectada = firma_detectada
        self.nombre_archivo = "x"
        self.tipo_documento = "otro"


class TestResumenEntrega:
    def test_todos_firmados(self):
        docs = [_DocumentoFalso(True), _DocumentoFalso(True)]
        resumen = resumen_entrega(docs)
        assert resumen["todos_firmados"] is True
        assert resumen["documentos_pendientes"] == []

    def test_alguno_sin_firmar(self):
        docs = [_DocumentoFalso(True), _DocumentoFalso(False), _DocumentoFalso(None)]
        resumen = resumen_entrega(docs)
        assert resumen["todos_firmados"] is False
        assert len(resumen["documentos_pendientes"]) == 2

    def test_sin_documentos_no_esta_todos_firmados(self):
        assert resumen_entrega([])["todos_firmados"] is False
