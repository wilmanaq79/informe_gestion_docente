# -*- coding: utf-8 -*-
"""Agente de verificacion de firmas en los documentos que un docente sube
en la sesion "Entrega de documentos". Analiza cada archivo apenas se
sube y devuelve un veredicto que ayuda al Director, Secretario
Academico y Secretaria del Programa a decidir si aprueban o rechazan la
entrega -- NO reemplaza su criterio, sobre todo para firmas manuscritas
escaneadas, que no se pueden verificar de forma confiable por software.

Niveles de deteccion, de mas a menos confiable:
  1. Firma digital (certificado) embebida en el PDF -- alta confianza.
  2. El texto del PDF menciona "firma"/"firmado" junto al nombre del
     docente -- confianza media (una firma escrita a maquina, o una
     leyenda junto a una firma escaneada).
  3. El PDF trae imagenes incrustadas (posible firma/sello escaneado)
     pero nada de lo anterior -- indeterminado, requiere revision
     humana.
  4. Nada de lo anterior -- probablemente no firmado.
  5. Imagen suelta (jpg/png) o Excel -- no se puede verificar
     automaticamente una firma manuscrita en una imagen, ni aplica en un
     Excel -- indeterminado, requiere revision humana.
"""
import unicodedata
from io import BytesIO

import pdfplumber
from pypdf import PdfReader

PALABRAS_FIRMA = ("firma", "firmado", "firmó", "firmo", "suscrito", "suscribe", "suscrita")


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


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


def analizar_documento(nombre_archivo: str, contenido: bytes, nombre_docente: str) -> dict:
    """Devuelve {'firma_detectada': True/False/None, 'confianza':
    'alta'/'media'/'baja', 'detalle': str}. None en firma_detectada
    significa indeterminado -- ni confirmado ni descartado, requiere que
    un humano lo revise (típicamente firmas manuscritas escaneadas)."""
    extension = nombre_archivo.lower().rsplit(".", 1)[-1] if "." in nombre_archivo else ""

    if extension == "pdf":
        if _tiene_firma_digital_pdf(contenido):
            return {
                "firma_detectada": True,
                "confianza": "alta",
                "detalle": "Firma digital (certificado) detectada en el PDF.",
            }

        texto = _normalizar(_texto_pdf(contenido))
        menciona_firma = any(palabra in texto for palabra in PALABRAS_FIRMA)
        partes_nombre = [p for p in _normalizar(nombre_docente).split() if len(p) > 3]
        menciona_nombre = any(parte in texto for parte in partes_nombre) if partes_nombre else False

        if menciona_firma and menciona_nombre:
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

    if extension in ("jpg", "jpeg", "png"):
        return {
            "firma_detectada": None,
            "confianza": "baja",
            "detalle": "Es una imagen — no se puede confirmar automáticamente una firma manuscrita, requiere revisión manual.",
        }

    if extension in ("xlsx", "xls"):
        return {
            "firma_detectada": None,
            "confianza": "baja",
            "detalle": "Los archivos de Excel no llevan firma — la verificación automática no aplica para este tipo de archivo.",
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
