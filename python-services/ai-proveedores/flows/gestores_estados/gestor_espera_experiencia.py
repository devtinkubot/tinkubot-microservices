"""Manejador del estado awaiting_experience."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import (
    extraer_anios_experiencia as parsear_anios_experiencia,
)


def manejar_espera_experiencia(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo años de experiencia.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con los años.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    anios = parsear_anios_experiencia(texto_mensaje)
    if anios is None:
        return {
            "success": True,
            "messages": [{"response": "*Necesito un numero de años de experiencia (ej: 5).*"}],
        }

    flujo["experience_years"] = anios
    flujo["state"] = "awaiting_email"
    return {
        "success": True,
        "messages": [
            {
                "response": "*Escribe tu correo electrónico o escribe \"omitir\" si no deseas agregarlo.*"
            }
        ],
    }
