"""Manejador del estado awaiting_city."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios


def manejar_espera_ciudad(
    flow: Dict[str, Any], message_text: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo ciudad.

    Args:
        flow: Diccionario del flujo conversacional.
        message_text: Mensaje del usuario con la ciudad.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    city = limpiar_espacios(message_text)
    if len(city) < 2:
        return {
            "success": True,
            "response": "*Indicame tu ciudad (ej: Quito, Guayaquil, Cuenca).*",
        }

    flow["city"] = city
    flow["state"] = "awaiting_name"
    return {
        "success": True,
        "response": "*¿Cuál es tu nombre completo?*",
    }
