"""Manejador del estado awaiting_social_media."""

from typing import Any, Dict, Optional

from flows.validators.validaciones_entrada import parsear_entrada_red_social


def manejar_espera_red_social(
    flow: Dict[str, Any], message_text: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo red social.

    Args:
        flow: Diccionario del flujo conversacional.
        message_text: Mensaje del usuario con la red social.

    Returns:
        Respuesta con éxito y siguiente pregunta.
    """
    parsed = parsear_entrada_red_social(message_text)
    flow["social_media_url"] = parsed["url"]
    flow["social_media_type"] = parsed["type"]

    flow["state"] = "awaiting_dni_front_photo"
    return {
        "success": True,
        "response": (
            "*Perfecto. Ahora necesito la foto de la Cédula (parte frontal). "
            "Envia la imagen como adjunto.*"
        ),
    }
