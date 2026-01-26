"""Manejador del estado awaiting_profession."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios


def manejar_espera_profesion(
    flow: Dict[str, Any], message_text: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo profesión.

    Args:
        flow: Diccionario del flujo conversacional.
        message_text: Mensaje del usuario con la profesión.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    profession = limpiar_espacios(message_text)
    if len(profession) < 2:
        return {
            "success": True,
            "response": (
                '*Indica tu profesión u oficio. Ejemplos: "Carpintero", '
                '"Ingeniero Electrico", "Abogado".*'
            ),
        }
    if len(profession) > 150:
        return {
            "success": True,
            "response": (
                "*Tu profesión debe ser breve (máximo 150 caracteres).* "
                "Envía una versión resumida (ej: 'Ingeniera en marketing' o 'Contratación pública')."
            ),
        }

    flow["profession"] = profession
    flow["state"] = "awaiting_specialty"
    return {
        "success": True,
        "response": (
            "*¿Qué servicios ofreces dentro de tu profesión?* "
            "Sepáralos con comas (ej: instalación eléctrica, mantenimiento industrial)."
        ),
    }
