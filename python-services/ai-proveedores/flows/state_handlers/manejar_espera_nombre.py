"""Manejador del estado awaiting_name."""

from typing import Any, Dict, Optional

from flows.validators.normalizar_texto import normalizar_texto


def manejar_espera_nombre(
    flow: Dict[str, Any], message_text: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo nombre.

    Args:
        flow: Diccionario del flujo conversacional.
        message_text: Mensaje del usuario con el nombre.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    name = normalizar_texto(message_text)
    if len(name) < 2:
        return {
            "success": True,
            "response": "*Por favor, enviame tu nombre completo.*",
        }

    flow["name"] = name
    flow["state"] = "awaiting_profession"
    return {
        "success": True,
        "response": (
            '*¿Cuál es tu profesión u oficio? Escribe el título, por ejemplo: '
            '"Carpintero", "Ingeniero Electrico", "Abogado".*'
        ),
    }
