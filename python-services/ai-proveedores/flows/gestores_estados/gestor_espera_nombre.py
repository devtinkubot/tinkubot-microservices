"""Manejador del estado awaiting_name."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios


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
    name = limpiar_espacios(message_text)
    if len(name) < 2:
        return {
            "success": True,
            "response": "*Por favor, enviame tu nombre completo.*",
        }

    flow["name"] = name
    # Fase 4: Eliminada referencia a awaiting_profession - salto directo a awaiting_specialty
    flow["state"] = "awaiting_specialty"
    return {
        "success": True,
        "response": (
            "*¿Qué servicios ofreces?* Sepáralos con comas "
            "(ej: instalación eléctrica, mantenimiento industrial, consultoría)."
        ),
    }
