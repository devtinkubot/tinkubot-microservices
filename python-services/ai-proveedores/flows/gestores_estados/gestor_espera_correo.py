"""Manejador del estado awaiting_email."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios


def manejar_espera_correo(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo correo electrónico.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con el correo.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    correo = limpiar_espacios(texto_mensaje)
    if correo.lower() in {"omitir", "na", "n/a", "ninguno", "ninguna"}:
        correo = None
    elif "@" not in correo or "." not in correo:
        return {
            "success": True,
            "response": (
                "*El correo no parece valido. Envialo nuevamente o escribe 'omitir'.*"
            ),
        }

    flujo["email"] = correo
    flujo["state"] = "awaiting_social_media"
    return {
        "success": True,
        "response": (
            "*Tienes alguna red social (Instagram o Facebook) para mostrar tu trabajo? "
            "Envia el enlace o escribe 'omitir'.*"
        ),
    }
