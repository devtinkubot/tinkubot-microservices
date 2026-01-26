"""Manejador del estado awaiting_experience."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import (
    extraer_anios_experiencia as parsear_anios_experiencia,
)


def manejar_espera_experiencia(
    flow: Dict[str, Any], message_text: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo años de experiencia.

    Args:
        flow: Diccionario del flujo conversacional.
        message_text: Mensaje del usuario con los años.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    years = parsear_anios_experiencia(message_text)
    if years is None:
        return {
            "success": True,
            "response": "*Necesito un numero de años de experiencia (ej: 5).*",
        }

    flow["experience_years"] = years
    flow["state"] = "awaiting_email"
    return {
        "success": True,
        "response": "*Escribe tu correo electrónico o escribe \"omitir\" si no deseas agregarlo.*",
    }
