"""Envío de correo del sistema (notificaciones de entregas aprobadas).

Configuración por variables de entorno (ver .env.example):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_TLS

Si el SMTP no está configurado, o el envío falla, las funciones de este
módulo NUNCA lanzan una excepción hacia quien las llama -- una entrega ya
aprobada y guardada en la base de datos no debe deshacerse ni fallar
solo porque no se pudo enviar el correo de aviso."""
import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _config_smtp() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "usuario": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "remitente": os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER"),
        "usar_tls": os.environ.get("SMTP_USE_TLS", "true").lower() != "false",
    }


def enviar_correo(destinatarios: list[str], asunto: str, cuerpo: str) -> None:
    """Envía un correo de texto plano vía SMTP. Lanza RuntimeError si no
    hay destinatarios validos, si el SMTP no está configurado, o si el
    envío falla -- quien llama decide qué hacer con ese error (ver
    notificar_entrega_aprobada más abajo, que lo atrapa)."""
    destinatarios_validos = sorted({d.strip() for d in destinatarios if d and d.strip()})
    if not destinatarios_validos:
        raise RuntimeError("No hay destinatarios con correo registrado.")

    config = _config_smtp()
    if not config["host"] or not config["remitente"]:
        raise RuntimeError("SMTP no está configurado (falta SMTP_HOST/SMTP_FROM en el .env).")

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = config["remitente"]
    mensaje["To"] = ", ".join(destinatarios_validos)
    mensaje.set_content(cuerpo)

    with smtplib.SMTP(config["host"], config["port"], timeout=15) as servidor:
        if config["usar_tls"]:
            servidor.starttls()
        if config["usuario"] and config["password"]:
            servidor.login(config["usuario"], config["password"])
        servidor.send_message(mensaje)


def notificar_entrega_aprobada(
    docente_nombre: str,
    docente_email: str | None,
    periodo_nombre: str,
    corte_nombre: str,
    revisor_nombre: str,
    destinatarios_adicionales: list[str],
) -> tuple[bool, str | None]:
    """Avisa por correo al Director, al Secretario Académico y al propio
    docente que su entrega documental fue aprobada. Devuelve (enviado,
    error) -- nunca lanza excepción."""
    destinatarios = [d for d in [docente_email, *destinatarios_adicionales] if d]
    asunto = f"Entrega aprobada — {docente_nombre} ({periodo_nombre}, {corte_nombre})"
    cuerpo = (
        f"La entrega documental de {docente_nombre} correspondiente a {periodo_nombre}, {corte_nombre} "
        f"fue revisada y APROBADA por {revisor_nombre}.\n\n"
        "Se confirmó que las listas de asistencia, las notas y el informe de gestión docente fueron "
        "entregados y están firmados.\n\n"
        "Este es un mensaje automático del Sistema de Gestión y Autoevaluación Docente — "
        "Universidad del Pacífico. Por favor no responda a este correo."
    )
    try:
        enviar_correo(destinatarios, asunto, cuerpo)
        return True, None
    except Exception as exc:
        logger.warning("No se pudo enviar la notificación de entrega aprobada: %s", exc)
        return False, str(exc)


def notificar_recuperacion_password(
    destinatario_email: str | None, destinatario_nombre: str, enlace: str
) -> tuple[bool, str | None]:
    """Envía el enlace para restablecer la contraseña. Devuelve (enviado,
    error) -- nunca lanza excepción, igual que notificar_entrega_aprobada."""
    asunto = "Recuperación de contraseña — Sistema de Gestión Docente"
    cuerpo = (
        f"Hola {destinatario_nombre},\n\n"
        "Recibimos una solicitud para restablecer tu contraseña en el Sistema de Gestión y "
        "Autoevaluación Docente. Usa el siguiente enlace para elegir una nueva:\n\n"
        f"{enlace}\n\n"
        "Este enlace expira en 30 minutos y solo puede usarse una vez. Si tú no solicitaste este "
        "cambio, puedes ignorar este correo — tu contraseña actual sigue siendo válida.\n\n"
        "Este es un mensaje automático del Sistema de Gestión y Autoevaluación Docente — "
        "Universidad del Pacífico. Por favor no responda a este correo."
    )
    try:
        enviar_correo([destinatario_email] if destinatario_email else [], asunto, cuerpo)
        return True, None
    except Exception as exc:
        logger.warning("No se pudo enviar el correo de recuperación de contraseña: %s", exc)
        return False, str(exc)
