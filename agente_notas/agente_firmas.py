# -*- coding: utf-8 -*-
"""Agente de verificacion de firmas en los documentos que un docente sube
en la sesion "Entrega de documentos". Analiza cada archivo apenas se
sube y devuelve un veredicto que ayuda al Director, Secretario
Academico y Secretaria del Programa a decidir si aprueban o rechazan la
entrega -- NO reemplaza su criterio, sobre todo para firmas manuscritas
escaneadas, que no se pueden verificar de forma confiable por software.

Niveles de deteccion (PDF y Excel se analizan con la MISMA logica de
fondo, solo cambia de donde se extrae el texto/las imagenes), de mas a
menos confiable:
  1. Firma digital (certificado) embebida en el archivo -- alta confianza.
     PDF: campo de formulario tipo /Sig. Excel (.xlsx): carpeta
     "_xmlsignatures" dentro del paquete OOXML.
  2. El texto del documento menciona "firma"/"firmado" junto al nombre
     del docente -- confianza media (una firma escrita a maquina, o una
     leyenda junto a una firma escaneada). En Excel, el texto es el
     contenido de TODAS las celdas de TODAS las hojas.
  3. El archivo trae imagenes incrustadas (posible firma/sello
     escaneado, p.ej. pegada en una celda o en el PDF) pero nada de lo
     anterior -- indeterminado, requiere revision humana.
  4. Nada de lo anterior -- probablemente no firmado.
  5. Imagen suelta (jpg/png) -- no se puede verificar automaticamente
     una firma manuscrita en una imagen -- indeterminado, requiere
     revision humana.
"""
import unicodedata
import zipfile
from io import BytesIO

import pdfplumber
from openpyxl import load_workbook
from pypdf import PdfReader

PALABRAS_FIRMA = ("firma", "firmado", "firmó", "firmo", "suscrito", "suscribe", "suscrita")


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def _menciona_firma_y_nombre(texto_normalizado: str, nombre_docente: str) -> bool:
    menciona_firma = any(palabra in texto_normalizado for palabra in PALABRAS_FIRMA)
    partes_nombre = [p for p in _normalizar(nombre_docente).split() if len(p) > 3]
    menciona_nombre = any(parte in texto_normalizado for parte in partes_nombre) if partes_nombre else False
    return menciona_firma and menciona_nombre


# --- PDF ----------------------------------------------------------------

def _tiene_firma_digital_pdf(contenido: bytes) -> bool:
    try:
        reader = PdfReader(BytesIO(contenido))
        campos = reader.get_fields() or {}
        return any(campo.get("/FT") == "/Sig" for campo in campos.values())
    except Exception:
        return False


def _texto_pdf(contenido: bytes) -> str:
    try:
        with pdfplumber.open(BytesIO(contenido)) as pdf:
            return "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)
    except Exception:
        return ""


def _tiene_imagenes_pdf(contenido: bytes) -> bool:
    try:
        reader = PdfReader(BytesIO(contenido))
        for pagina in reader.pages:
            recursos = pagina.get("/Resources") or {}
            xobjects = recursos.get("/XObject")
            if not xobjects:
                continue
            for objeto in xobjects.values():
                if objeto.get_object().get("/Subtype") == "/Image":
                    return True
    except Exception:
        pass
    return False


def _analizar_pdf(contenido: bytes, nombre_docente: str) -> dict:
    if _tiene_firma_digital_pdf(contenido):
        return {
            "firma_detectada": True,
            "confianza": "alta",
            "detalle": "Firma digital (certificado) detectada en el PDF.",
        }

    texto = _normalizar(_texto_pdf(contenido))
    if _menciona_firma_y_nombre(texto, nombre_docente):
        return {
            "firma_detectada": True,
            "confianza": "media",
            "detalle": "El texto del documento menciona 'firma' junto al nombre del docente.",
        }

    if _tiene_imagenes_pdf(contenido):
        return {
            "firma_detectada": None,
            "confianza": "baja",
            "detalle": (
                "El PDF contiene imágenes (posible firma o sello escaneado) — no se puede confirmar "
                "automáticamente una firma manuscrita, requiere revisión manual."
            ),
        }

    return {
        "firma_detectada": False,
        "confianza": "media",
        "detalle": "No se detectó firma digital, texto de firma, ni imágenes en el documento.",
    }


# --- Excel (.xlsx) --------------------------------------------------------
# Un .xlsx es en realidad un archivo .zip: se puede inspeccionar su
# contenido interno sin depender de que openpyxl "entienda" cada detalle.

def _tiene_firma_digital_xlsx(contenido: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(contenido)) as z:
            return any(nombre.startswith("_xmlsignatures") for nombre in z.namelist())
    except Exception:
        return False


def _tiene_imagenes_xlsx(contenido: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(contenido)) as z:
            return any(nombre.startswith("xl/media/") for nombre in z.namelist())
    except Exception:
        return False


def _texto_xlsx(contenido: bytes) -> str:
    """Concatena el valor de TODAS las celdas de TODAS las hojas (más
    los comentarios de celda, donde a veces se anota "Firmado por..."),
    para poder aplicar la misma búsqueda de palabras que en el PDF."""
    try:
        wb = load_workbook(BytesIO(contenido), data_only=True)
    except Exception:
        return ""

    partes = []
    try:
        for hoja in wb.worksheets:
            for fila in hoja.iter_rows():
                for celda in fila:
                    if celda.value is not None:
                        partes.append(str(celda.value))
                    if celda.comment is not None and celda.comment.text:
                        partes.append(celda.comment.text)
    finally:
        wb.close()
    return "\n".join(partes)


def _analizar_xlsx(contenido: bytes, nombre_docente: str) -> dict:
    if _tiene_firma_digital_xlsx(contenido):
        return {
            "firma_detectada": True,
            "confianza": "alta",
            "detalle": "Firma digital (certificado) detectada en el archivo de Excel.",
        }

    texto = _normalizar(_texto_xlsx(contenido))
    if _menciona_firma_y_nombre(texto, nombre_docente):
        return {
            "firma_detectada": True,
            "confianza": "media",
            "detalle": "Alguna celda (o comentario) del Excel menciona 'firma' junto al nombre del docente.",
        }

    if _tiene_imagenes_xlsx(contenido):
        return {
            "firma_detectada": None,
            "confianza": "baja",
            "detalle": (
                "El Excel tiene una imagen incrustada (posible firma o sello pegado en una celda) — "
                "no se puede confirmar automáticamente una firma manuscrita, requiere revisión manual."
            ),
        }

    return {
        "firma_detectada": False,
        "confianza": "media",
        "detalle": (
            "No se encontró ninguna celda con 'firma' junto al nombre del docente, ni una imagen incrustada, "
            "en el archivo de Excel. Si el docente firmó en una hoja aparte, adjúntala también o pega la firma "
            "escaneada en una celda del archivo."
        ),
    }


# --- Punto de entrada ------------------------------------------------------

def analizar_documento(nombre_archivo: str, contenido: bytes, nombre_docente: str) -> dict:
    """Devuelve {'firma_detectada': True/False/None, 'confianza':
    'alta'/'media'/'baja', 'detalle': str}. None en firma_detectada
    significa indeterminado -- ni confirmado ni descartado, requiere que
    un humano lo revise (típicamente firmas manuscritas escaneadas)."""
    extension = nombre_archivo.lower().rsplit(".", 1)[-1] if "." in nombre_archivo else ""

    if extension == "pdf":
        return _analizar_pdf(contenido, nombre_docente)

    if extension == "xlsx":
        return _analizar_xlsx(contenido, nombre_docente)

    if extension in ("jpg", "jpeg", "png"):
        return {
            "firma_detectada": None,
            "confianza": "baja",
            "detalle": "Es una imagen — no se puede confirmar automáticamente una firma manuscrita, requiere revisión manual.",
        }

    return {
        "firma_detectada": None,
        "confianza": "baja",
        "detalle": f"Tipo de archivo '.{extension}' no soportado para verificación automática de firma.",
    }


def resumen_entrega(documentos) -> dict:
    """documentos: lista de objetos con .firma_detectada (bool|None),
    .tipo_documento (str) y .nombre_archivo (str) -- normalmente
    entrega.documentos. Devuelve un resumen agregado para mostrar de un
    vistazo si la entrega completa cumple con las firmas."""
    pendientes = [d for d in documentos if d.firma_detectada is not True]
    return {
        "todos_firmados": len(documentos) > 0 and len(pendientes) == 0,
        "documentos_pendientes": pendientes,
    }
