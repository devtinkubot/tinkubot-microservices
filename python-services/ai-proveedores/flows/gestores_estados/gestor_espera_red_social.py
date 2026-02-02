"""Manejador del estado awaiting_social_media."""

from typing import Any, Dict, Optional

from flows.validadores.validador_entrada import parsear_entrada_red_social


def manejar_espera_red_social(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo red social.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con la red social.

    Returns:
        Respuesta con éxito y siguiente pregunta.
    """
    red_social_parseada = parsear_entrada_red_social(texto_mensaje)
    flujo["social_media_url"] = red_social_parseada["url"]
    flujo["social_media_type"] = red_social_parseada["type"]

    flujo["state"] = "awaiting_dni_front_photo"
    return {
        "success": True,
        "messages": [
            {
                "response": (
                    "*Perfecto. Ahora necesito la foto de la Cédula (parte frontal). "
                    "Envia la imagen como adjunto.*"
                )
            }
        ],
    }
