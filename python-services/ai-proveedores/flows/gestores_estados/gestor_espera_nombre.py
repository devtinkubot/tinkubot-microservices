"""Manejador del estado awaiting_name."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios
from templates.registro import solicitar_foto_dni_frontal


def manejar_espera_nombre(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo nombre.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con el nombre.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    nombre = limpiar_espacios(texto_mensaje)
    if len(nombre) < 2:
        return {
            "success": True,
            "messages": [{"response": "*Por favor, enviame tu nombre completo.*"}],
        }

    flujo["name"] = nombre
    flujo["state"] = "awaiting_dni_front_photo"
    return {
        "success": True,
        "messages": [
            {"response": solicitar_foto_dni_frontal()}
        ],
    }
