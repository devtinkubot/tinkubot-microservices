"""Manejador del estado awaiting_city."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios


def manejar_espera_ciudad(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo ciudad.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con la ciudad.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    ciudad = limpiar_espacios(texto_mensaje)
    if len(ciudad) < 2:
        return {
            "success": True,
            "response": "*Indicame tu ciudad (ej: Quito, Guayaquil, Cuenca).*",
        }

    flujo["city"] = ciudad
    flujo["state"] = "awaiting_name"
    return {
        "success": True,
        "response": "*¿Cuál es tu nombre completo?*",
    }
