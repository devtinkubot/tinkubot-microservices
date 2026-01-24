"""Manejador del estado awaiting_email."""

from typing import Any, Dict, Optional

from flows.validators.normalizar_texto import normalizar_texto


def manejar_espera_correo(
    flow: Dict[str, Any], message_text: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo correo electrónico.

    Args:
        flow: Diccionario del flujo conversacional.
        message_text: Mensaje del usuario con el correo.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    email = normalizar_texto(message_text)
    if email.lower() in {"omitir", "na", "n/a", "ninguno", "ninguna"}:
        email = None
    elif "@" not in email or "." not in email:
        return {
            "success": True,
            "response": (
                "*El correo no parece valido. Envialo nuevamente o escribe 'omitir'.*"
            ),
        }

    flow["email"] = email
    flow["state"] = "awaiting_social_media"
    return {
        "success": True,
        "response": (
            "*Tienes alguna red social (Instagram o Facebook) para mostrar tu trabajo? "
            "Envia el enlace o escribe 'omitir'.*"
        ),
    }
